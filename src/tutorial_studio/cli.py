"""Explicit CLI actions; no implicit downloads, app execution or uploads."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import signal
import sys

from .assets import DEFAULT_MODELS, ROOT, setup_models, verify_models
from .manifest import VOICES, load_manifest, read_json
from .voices import BY_ID


def emit(value):
    print(json.dumps(value, indent=2), flush=True)


def doctor(models):
    checks = {tool: shutil.which(tool) for tool in ["ffmpeg", "ffprobe", "node"]}
    packages = {}
    for package in ["kokoro-onnx", "onnxruntime", "soundfile", "Pillow"]:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    try:
        assets = verify_models(models)
        error = None
    except (ValueError, OSError) as failure:
        assets, error = None, str(failure)
    return {"framework": str(ROOT), "python": sys.executable, "tools": checks, "packages": packages, "model_hashes": assets, "model_error": error, "render_ready": bool(checks['ffmpeg'] and checks['ffprobe'] and assets and all(packages.values())), "network_during_narration": False}


def initialize(path, title="My Project Tutorial"):
    path = Path(path).expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"schema_version": 1, "title": title, "voice": "bf_emma", "speed": 0.94, "pronunciations": {}, "scenes": [
        {"title": "Welcome", "card": "YOUR PROJECT\n\nWhat it does\nWho it is for\nWhat you will learn", "narration": "Welcome. This walkthrough introduces the project and shows how to get started. Replace this narration with verified, project-specific instructions."},
        {"title": "Your first workflow", "card": "1. Check prerequisites\n2. Follow the documented setup\n3. Perform a real workflow\n4. Verify the result", "narration": "Start with the documented prerequisites. Follow the setup instructions, perform a real workflow, and verify the result. Use screenshots captured from the actual application."},
    ]}
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    return {"manifest": str(path), "status": "template created; edit before rendering"}


def import_legacy(source, destination):
    source = Path(source).resolve(strict=True)
    data = read_json(source)
    if not isinstance(data, list) or not 1 <= len(data) <= 100:
        raise ValueError("Expected 1 to 100 original tutorial scenes")
    numbers = [scene.get("number") for scene in data]
    if any(type(n) is not int or not 1 <= n <= 100 for n in numbers) or len(set(numbers)) != len(numbers):
        raise ValueError("Legacy scene numbers must be unique integers from 1 to 100")
    manifest = {"schema_version": 1, "title": "Kortex: Project to HTTP Graph Viewer", "voice": "bf_emma", "speed": 0.94, "pronunciations": {"Kortex": "Cortex", "kortex": "cortex"}, "scenes": []}
    from .manifest import asset_path
    for scene in data:
        asset_path(source.parent, f"scene-{scene['number']:02}.png")
        manifest["scenes"].append({"title": scene["title"], "narration": scene["narration"], "image": f"scene-{scene['number']:02}.png"})
    destination = Path(destination).expanduser().absolute()
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for scene in manifest["scenes"]:
        shutil.copyfile(source.parent / scene["image"], destination / scene["image"])
    target = destination / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    load_manifest(target)
    return {"manifest": str(target), "scenes": len(data), "original_preserved": True}


def preview(output, models, voice, speed, narration):
    from .narration import Narrator
    if voice not in VOICES:
        raise ValueError("Unknown voice")
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != ".wav":
        raise ValueError("Preview output must end in .wav")
    narrator = Narrator(models=models)
    wav, receipt = narrator.synthesize(narration, voice, speed, {"Kortex": "Cortex"})
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with output.open("xb") as target, wav.open("rb") as source:
        shutil.copyfileobj(source, target)
    return {"audio": str(output), "speech": receipt}


def main(argv=None):
    def cancelled(_signum, _frame):
        raise KeyboardInterrupt("Tutorial operation cancelled")
    signal.signal(signal.SIGTERM, cancelled)
    parser = argparse.ArgumentParser(prog="tutorial-studio", description="Private local neural tutorial production")
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor")
    sub.add_parser("voices")
    studio = sub.add_parser("studio", help="Open the local browser editor")
    studio.add_argument("--workspace", required=True, type=Path)
    studio.add_argument("--manifest", type=Path, help="Import into a new workspace; original is never edited")
    studio.add_argument("--port", type=int, default=0)
    studio.add_argument("--no-browser", action="store_true")
    gallery = sub.add_parser("gallery")
    gallery.add_argument("--output", required=True, type=Path)
    setup = sub.add_parser("setup-model")
    setup.add_argument("--approve-download", action="store_true")
    init = sub.add_parser("init")
    init.add_argument("manifest", type=Path)
    init.add_argument("--title", default="My Project Tutorial")
    legacy = sub.add_parser("import-legacy")
    legacy.add_argument("source", type=Path)
    legacy.add_argument("output", type=Path)
    validation = sub.add_parser("validate")
    validation.add_argument("manifest", type=Path)
    audio = sub.add_parser("preview")
    audio.add_argument("--output", required=True, type=Path)
    audio.add_argument("--voice", choices=VOICES, default="bf_emma")
    audio.add_argument("--speed", type=float, default=0.94)
    audio.add_argument("--text", help="Custom narration; otherwise use a sample in the selected voice's language")
    video = sub.add_parser("render")
    video.add_argument("manifest", type=Path)
    video.add_argument("--output", required=True, type=Path)
    video.add_argument("--voice", choices=VOICES)
    capture = sub.add_parser("capture")
    capture.add_argument("plan", type=Path)
    capture.add_argument("--output", required=True, type=Path)
    capture.add_argument("--approve-browser", action="store_true")
    media = sub.add_parser("verify-video")
    media.add_argument("video", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "studio":
            from .studio import serve
            serve(args.workspace, manifest=args.manifest, models=args.models, port=args.port, open_browser=not args.no_browser)
            return 0
        if args.action == "doctor":
            result = doctor(args.models)
        elif args.action == "voices":
            result = {name: {"name": v[0], "description": v[1]} for name, v in VOICES.items()}
        elif args.action == "gallery":
            from .gallery import build_gallery
            result = build_gallery(args.output, models=args.models)
        elif args.action == "setup-model":
            result = setup_models(args.models, args.approve_download)
        elif args.action == "init":
            result = initialize(args.manifest, args.title)
        elif args.action == "import-legacy":
            result = import_legacy(args.source, args.output)
        elif args.action == "validate":
            data, _ = load_manifest(args.manifest)
            result = {"valid": True, "title": data["title"], "scenes": len(data["scenes"]), "voice": data["voice"]}
        elif args.action == "preview":
            result = preview(args.output, args.models, args.voice, args.speed, args.text or BY_ID[args.voice]["sample"])
        elif args.action == "render":
            from .render import render
            result = render(args.manifest, args.output, models=args.models, voice=args.voice)
        elif args.action == "verify-video":
            from .render import validate_video
            result = validate_video(args.video)
        else:
            if not args.approve_browser:
                raise PermissionError("Capture requires --approve-browser; only an already-running local app is allowed")
            from .render import command
            result = json.loads(command(["node", str(ROOT / "browser" / "capture.mjs"), str(args.plan.resolve()), str(args.output.expanduser().absolute())]))
        emit(result)
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"error": "Tutorial operation cancelled"}), file=sys.stderr)
        return 130
    except (ValueError, OSError, RuntimeError, PermissionError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
