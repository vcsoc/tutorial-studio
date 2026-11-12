"""Render inert scene assets and verified local speech, never project commands."""

import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .assets import sha256
from .manifest import asset_path, load_manifest
from .narration import Narrator
from .voices import BY_ID


def command(argv, timeout=900):
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        if process.returncode:
            raise RuntimeError(f"{argv[0]} failed ({process.returncode}): {stderr[-4000:]}")
        return stdout
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
        raise


def probe(path):
    return json.loads(command(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-show_chapters", "-of", "json", str(path)]))


def stamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def font(size, mono=False):
    names = (["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"] if mono else ["/System/Library/Fonts/Supplemental/Georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"])
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def frame(scene, root, destination, number=1):
    if "image" in scene:
        with Image.open(asset_path(root, scene["image"])) as source:
            if source.width * source.height > 25_000_000:
                raise ValueError("Image exceeds 25 megapixels")
            image = ImageOps.pad(source.convert("RGB"), (1920, 1080), color="#101c1b")
    else:
        image = Image.new("RGB", (1920, 1080), "#101c1b")
        draw = ImageDraw.Draw(image)
        breadcrumb = scene.get("breadcrumb", f"SCENE {number:02}")
        for index, line in enumerate(textwrap.wrap("TUTORIAL STUDIO / " + breadcrumb, 120)):
            draw.text((90, 65 + index * 28), line, font=font(23, True), fill="#e6bd76")
        y = 130
        for line in textwrap.wrap(scene["title"], 55):
            draw.text((90, y), line, font=font(49), fill="#f3ead8")
            y += 63
        y += 35
        for paragraph in scene["card"].splitlines():
            for line in textwrap.wrap(paragraph, 100, replace_whitespace=False) or [""]:
                if y > (580 if "content_image" in scene else 940):
                    raise ValueError("Card text exceeds frame; shorten it or split into more scenes")
                draw.text((100, y), line, font=font(27, True), fill="#d2eadb")
                y += 38
        if "content_image" in scene:
            top = y + 20
            height = 960 - top
            if height < 220:
                raise ValueError("Not enough room for the inline image; shorten the card or title")
            with Image.open(asset_path(root, scene["content_image"])) as source:
                if source.width * source.height > 25_000_000:
                    raise ValueError("Image exceeds 25 megapixels")
                inset = ImageOps.contain(source.convert("RGB"), (1720, height))
                image.paste(inset, ((1920 - inset.width) // 2, top + (height - inset.height) // 2))
        if scene.get("note"):
            draw.text((90, 1010), scene["note"][:120], font=font(21), fill="#e6bd76")
    image.save(destination)


def validate_video(path, decode=True):
    data = probe(path)
    streams = data.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    if len(videos) != 1 or videos[0].get("codec_name") != "h264" or videos[0].get("width") != 1920 or videos[0].get("height") != 1080:
        raise ValueError("Expected one 1920x1080 H.264 video stream")
    if not any(s.get("codec_type") == "audio" and s.get("codec_name") == "aac" for s in streams):
        raise ValueError("Missing AAC narration")
    if not any(s.get("codec_type") == "subtitle" for s in streams):
        raise ValueError("Missing subtitle track")
    duration = float(data.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid video duration")
    if decode:
        command(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"], timeout=1800)
    return {"duration_seconds": duration, "bytes": Path(path).stat().st_size, "sha256": sha256(path), "chapters": len(data.get("chapters", [])), "full_audio_video_decode": decode, "probe": data}


def render(manifest, output, models=None, voice=None, narrator=None):
    data, root = load_manifest(manifest)
    if voice is not None:
        from .manifest import VOICES
        if voice not in VOICES:
            raise ValueError("Unknown voice")
        data["voice"] = voice
    for tool in ["ffmpeg", "ffprobe"]:
        if not shutil.which(tool):
            raise ValueError(f"Missing required tool: {tool}")
    # Validate and snapshot every visual before expensive speech generation.
    output = Path(output).expanduser().absolute()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    visuals = output / "visuals"
    visuals.mkdir(mode=0o700)
    work = output / "segments"
    work.mkdir(mode=0o700)
    receipt = {"status": "incomplete", "title": data["title"], "voice": data["voice"], "speed": data["speed"], "capture_style": "narrated still scenes", "scenes": []}
    receipt_path = output / "receipt.json"
    try:
        for i, scene in enumerate(data["scenes"], 1):
            frame(scene, root, visuals / f"{i:03}.png", number=i)
        if narrator is None:
            narrator = Narrator(**({"models": models} if models else {}))
        subtitles, chapters = [], [";FFMETADATA1", "title=" + data["title"].replace("\n", " ").replace("=", "-").replace(";", ",").replace("#", "")]
        transcript = ["# " + data["title"], "", "Local neural narration. Captions follow synthesized sentence boundaries.", ""]
        start = 0.0
        for i, scene in enumerate(data["scenes"], 1):
            print(f"Narrating/rendering scene {i}/{len(data['scenes'])}: {scene['title']}", flush=True)
            wav, speech = narrator.synthesize(scene["narration"], data["voice"], data["speed"], data["pronunciations"])
            shutil.copyfile(wav, work / f"{i:03}.wav")
            duration = speech["duration"] + 1.05
            segment = work / f"{i:03}.mp4"
            command(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "24", "-i", str(visuals / f"{i:03}.png"), "-i", str(work / f"{i:03}.wav"), "-t", str(duration), "-vf", "fade=t=in:st=0:d=0.3", "-af", "adelay=350,loudnorm=I=-18:TP=-2:LRA=7,apad", "-ar", "48000", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(segment)])
            encoded = float(probe(segment)["format"]["duration"])
            for timing in speech["timings"]:
                line = "\n".join(textwrap.wrap(timing["text"], 84))
                subtitles.append(f"{len(subtitles)+1}\n{stamp(start+0.35+timing['start'])} --> {stamp(start+0.35+timing['end'])}\n{line}\n")
            title = scene["title"].replace("\n", " ").replace("=", "-").replace(";", ",").replace("#", "").replace("\\", "/")
            chapters += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(start*1000)}", f"END={round((start+encoded)*1000)}", "title=" + title]
            transcript += [f"## {stamp(start).split(',')[0]} - {scene['title']}", "", scene["narration"], ""]
            receipt["scenes"].append({"title": scene["title"], "start": start, "duration": encoded, "image_sha256": sha256(visuals / f"{i:03}.png"), "speech": speech})
            start += encoded
            if start > 3600:
                raise ValueError("Tutorial exceeds one hour")
        (output / "captions.srt").write_text("\n".join(subtitles), encoding="utf-8")
        (output / "chapters.ffmeta").write_text("\n".join(chapters) + "\n", encoding="utf-8")
        (output / "TRANSCRIPT.md").write_text("\n".join(transcript), encoding="utf-8")
        (output / "manifest.json").write_text(json.dumps(data, indent=2) + "\n")
        (work / "concat.txt").write_text("".join(f"file '{i:03}.mp4'\n" for i in range(1, len(data["scenes"]) + 1)))
        video = output / "tutorial.mp4"
        language = BY_ID[data["voice"]]["lang"].split("-")[0]
        subtitle_tag = {"en": "eng", "fr": "fra", "es": "spa", "it": "ita", "pt": "por", "hi": "hin"}.get(language, "und")
        receipt["subtitle_language"] = subtitle_tag
        command(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(work / "concat.txt"), "-i", str(output / "captions.srt"), "-i", str(output / "chapters.ffmeta"), "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0", "-map_metadata", "2", "-map_chapters", "2", "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=" + subtitle_tag, "-movflags", "+faststart", str(video)])
        receipt["validation"] = validate_video(video)
        if receipt["validation"]["chapters"] != len(data["scenes"]):
            raise ValueError("Final video chapter count mismatch")
        receipt["status"] = "complete"
        # Keep the saved manifest self-contained and rerenderable.
        for i, scene in enumerate(data["scenes"], 1):
            scene.pop("card", None)
            scene.pop("content_image", None)
            scene["image"] = f"visuals/{i:03}.png"
        (output / "manifest.json").write_text(json.dumps(data, indent=2) + "\n")
        return receipt
    except BaseException as error:
        receipt["error"] = str(error)[:2000]
        raise
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
