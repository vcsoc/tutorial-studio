"""Loopback-only editor. Content stays in an explicit workspace, never the installation."""

import base64
import copy
import hashlib
import hmac
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import webbrowser

from PIL import Image

from .assets import ROOT
from .manifest import asset_path, load_manifest, read_json
from .voices import BY_ID, CATALOG

STATIC = Path(__file__).with_name("web")
MAX_BODY = 12_000_000
PREVIEW_TEXT = "Welcome to Tutorial Studio. Let's get your tutorial underway with my voice as the narrator."


class Conflict(ValueError):
    pass


class Studio:
    def __init__(self, workspace, manifest=None, models=None):
        self.workspace = Path(workspace).expanduser().resolve()
        if self.workspace.is_relative_to(ROOT) or ROOT.is_relative_to(self.workspace):
            raise ValueError("Choose a workspace outside the Tutorial Studio installation")
        self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("draft.json", "assets", "previews", "renders"):
            target = self.workspace / name
            if target.is_symlink():
                raise ValueError("Workspace entries must not be symlinks")
        self.models = models
        self.lock = threading.RLock()
        self.job = None
        self.jobs = {}
        self.process = None
        self.closing = False
        self.revision = 0
        self.draft = {"schema_version": 1, "title": "Untitled tutorial", "voice": "af_heart", "speed": 0.94, "pronunciations": {}, "scenes": []}
        self.draft_path = self.workspace / "draft.json"
        if self.draft_path.exists():
            self.draft = self.check_draft(read_json(self.draft_path))
        elif manifest:
            data, source = load_manifest(manifest)
            data = copy.deepcopy(data)
            (self.workspace / "assets").mkdir(exist_ok=True)
            for scene in data["scenes"]:
                if "image" in scene:
                    original = asset_path(source, scene["image"])
                    scene["image"] = self.image(base64.b64encode(original.read_bytes()).decode())["image"]
            self.draft = data
            self.save(data, 0)

    def check_draft(self, data, complete=False):
        if not isinstance(data, dict) or not isinstance(data.get("scenes"), list) or len(data["scenes"]) > 100:
            raise ValueError("Draft requires a list of at most 100 scenes")
        original = copy.deepcopy(data)
        original.setdefault("voice", "bf_emma")
        original.setdefault("speed", 0.94)
        original.setdefault("pronunciations", {})
        candidate = copy.deepcopy(original)
        # A draft may be empty or have unfinished text; renders use strict validation.
        if not complete:
            if candidate.get("title") == "":
                candidate["title"] = "Untitled"
            for scene in candidate["scenes"]:
                if not isinstance(scene, dict):
                    raise ValueError("Invalid scene")
                for key in ("title", "narration", "card", "note"):
                    if scene.get(key) == "":
                        scene[key] = "Draft"
            if not candidate["scenes"]:
                candidate["scenes"] = [{"title": "Draft", "narration": "Draft", "card": "Draft"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", dir=self.workspace, delete=False) as stream:
            temp = Path(stream.name)
            json.dump(candidate, stream)
        try:
            load_manifest(temp)
        finally:
            temp.unlink()
        return original

    def save(self, data, revision):
        with self.lock:
            if revision != self.revision:
                raise Conflict("Draft changed in another tab. Reload before saving.")
            data = self.check_draft(data)
            with tempfile.NamedTemporaryFile(mode="w", dir=self.workspace, delete=False) as stream:
                temp = Path(stream.name)
                json.dump(data, stream, indent=2)
                stream.write("\n")
            try:
                temp.replace(self.draft_path)
            finally:
                temp.unlink(missing_ok=True)
            self.draft = data
            self.revision += 1
            return self.state()

    def state(self):
        with self.lock:
            job = copy.deepcopy(self.job)
            if job and job["status"] == "running":
                log = self.workspace / job["id"] / "operation.log"
                if log.exists():
                    with log.open("rb") as stream:
                        stream.seek(max(0, log.stat().st_size - 12000))
                        job["progress"] = stream.read(12000).decode("utf-8", errors="replace")
            return {"draft": copy.deepcopy(self.draft), "revision": self.revision, "voices": CATALOG, "workspace": str(self.workspace), "job": job}

    def image(self, encoded):
        if not isinstance(encoded, str) or len(encoded) > 11_000_000:
            raise ValueError("Image must be at most 8 MB")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 8_000_000:
            raise ValueError("Image must be at most 8 MB")
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 25_000_000 or image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Use a PNG, JPEG or WebP image under 25 megapixels")
            image.load()
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG")
        content = output.getvalue()
        directory = self.workspace / "assets"
        directory.mkdir(exist_ok=True)
        name = hashlib.sha256(content).hexdigest() + ".png"
        target = directory / name
        if not target.exists():
            with target.open("xb") as stream:
                stream.write(content)
        return {"image": "assets/" + name}

    def start_job(self, kind, payload):
        with self.lock:
            if self.closing:
                raise Conflict("Studio is shutting down")
            if self.job and self.job["status"] == "running":
                raise Conflict("Wait for the current operation to finish")
            identifier = secrets.token_hex(12)
            directory = self.workspace / identifier
            directory.mkdir(mode=0o700)
            args = [sys.executable, "-m", "tutorial_studio.cli"]
            if self.models:
                args += ["--models", str(self.models)]
            if kind == "render":
                if payload.get("revision") != self.revision:
                    raise Conflict("Save the current draft before rendering")
                data = self.check_draft(self.draft, complete=True)
                manifest = self.workspace / (identifier + ".json")
                manifest.write_text(json.dumps(data, indent=2) + "\n")
                args += ["render", str(manifest), "--output", str(directory / "video")]
            elif kind == "preview":
                voice = payload.get("voice")
                if voice not in BY_ID:
                    raise ValueError("Unknown voice")
                narration = payload.get("text") or PREVIEW_TEXT
                if not isinstance(narration, str) or not narration.strip() or len(narration) > 5000:
                    raise ValueError("Preview text must contain 1 to 5000 characters")
                speed = payload.get("speed", 0.94)
                if isinstance(speed, bool) or not isinstance(speed, (float, int)) or not 0.75 <= speed <= 1.25:
                    raise ValueError("Invalid speed")
                if payload.get("text"):
                    from .narration import spoken_text
                    narration = spoken_text(narration, self.draft.get("pronunciations", {}))
                args += ["preview", "--voice", voice, "--speed", str(speed), "--text", narration, "--output", str(directory / "preview.wav")]
            else:
                raise ValueError("Unknown operation")
            job = {"id": identifier, "kind": kind, "status": "running", "voice": payload.get("voice", self.draft["voice"])}
            self.job = job
            self.jobs[identifier] = job
            try:
                with (directory / "operation.log").open("wb") as log:
                    self.process = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            except OSError:
                job["status"] = "failed"
                job["error"] = "Could not launch the local operation"
                raise
            process = self.process
            threading.Thread(target=self.finish_job, args=(process, job, directory), daemon=True).start()
            return copy.deepcopy(job)

    def finish_job(self, process, job, directory):
        code = process.wait()
        with self.lock:
            job["status"] = "complete" if code == 0 else "failed"
            if code == 0:
                try:
                    job["media"] = f"/media/{job['id']}/" + ("tutorial.mp4" if job["kind"] == "render" else "preview.wav")
                    if job["kind"] == "render":
                        receipt = read_json(directory / "video" / "receipt.json")
                        if receipt["status"] != "complete" or not receipt["validation"]["full_audio_video_decode"]:
                            raise ValueError("Render did not pass final validation")
                        job["validation"] = {k: receipt["validation"][k] for k in ("duration_seconds", "chapters", "full_audio_video_decode")}
                except (OSError, ValueError, KeyError, TypeError) as error:
                    job["status"] = "failed"
                    job["error"] = f"Could not verify the operation receipt: {error}"
                    job.pop("media", None)
            else:
                with (directory / "operation.log").open("rb") as stream:
                    stream.seek(max(0, (directory / "operation.log").stat().st_size - 4000))
                    job["error"] = stream.read(4000).decode("utf-8", errors="replace")
            self.process = None

    def close(self):
        with self.lock:
            self.closing = True
            process = self.process
        if process and process.poll() is None:
            import signal
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=8)
            except ProcessLookupError:
                process.wait()
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, studio, port=0):
        import fcntl

        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("Port must be between 0 and 65535")
        self.studio = studio
        self.token = secrets.token_urlsafe(32)
        lock_path = studio.workspace / ".studio.lock"
        if lock_path.is_symlink():
            raise ValueError("Workspace lock must not be a symlink")
        self.workspace_lock = lock_path.open("a")
        try:
            fcntl.flock(self.workspace_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            super().__init__(("127.0.0.1", port), Handler)
        except OSError as error:
            self.workspace_lock.close()
            raise ValueError("Workspace is already open in another studio, or the port is unavailable") from error
        self.origin = f"http://127.0.0.1:{self.server_port}"

    def server_close(self):
        super().server_close()
        self.workspace_lock.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Do not log access tokens or private tutorial content.

    def reply(self, code, content, mime="application/json"):
        if mime == "application/json":
            content = json.dumps(content).encode()
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(content)

    def authorize(self, media=False):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            raise PermissionError("Invalid Host")
        if self.headers.get("Origin", self.server.origin) != self.server.origin:
            raise PermissionError("Cross-origin access refused")
        provided = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if media and not provided:
            provided = parse_qs(urlsplit(self.path).query).get("token", [""])[0]
        if not hmac.compare_digest(provided.encode(), self.server.token.encode()):
            raise PermissionError("Studio authorization required; reopen the launch URL")

    def do_GET(self):
        try:
            # Host/origin checks also protect unauthenticated static resources.
            if self.headers.get("Host") != self.server.origin.removeprefix("http://") or self.headers.get("Origin", self.server.origin) != self.server.origin:
                raise PermissionError("Invalid Host or Origin")
            path = urlsplit(self.path).path
            if path in ("/", "/studio.js", "/studio.css"):
                name = "index.html" if path == "/" else path[1:]
                return self.reply(200, (STATIC / name).read_bytes(), mimetypes.guess_type(name)[0])
            self.authorize(media=path.startswith(("/media/", "/assets/")))
            if path == "/api/state":
                return self.reply(200, self.server.studio.state())
            if path.startswith("/assets/"):
                target = asset_path(self.server.studio.workspace, path[1:])
                return self.reply(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "media":
                _, identifier, filename = parts
                job = self.server.studio.jobs.get(identifier)
                if not job or job["status"] != "complete":
                    raise ValueError("Media is not ready")
                allowed = {"preview.wav"} if job["kind"] == "preview" else {"tutorial.mp4", "captions.srt", "TRANSCRIPT.md", "receipt.json", "manifest.json"}
                if filename not in allowed:
                    raise ValueError("Unknown artifact")
                target = self.server.studio.workspace / identifier
                target = target / filename if job["kind"] == "preview" else target / "video" / filename
                # Stream video instead of buffering an entire tutorial in memory.
                size = target.stat().st_size
                start, end = 0, size - 1
                requested = self.headers.get("Range")
                if requested:
                    try:
                        unit, bounds = requested.split("=", 1)
                        left, right = bounds.split("-", 1)
                        if unit != "bytes" or "," in bounds:
                            raise ValueError
                        if left:
                            start = int(left)
                            end = min(int(right), end) if right else end
                        else:
                            length = int(right)
                            if length <= 0:
                                raise ValueError
                            start = max(0, size - length)
                        if not 0 <= start <= end < size:
                            raise ValueError
                    except ValueError:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                self.send_response(206 if requested else 200)
                self.send_header("Content-Type", mimetypes.guess_type(filename)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Accept-Ranges", "bytes")
                if requested:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with target.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            self.reply(404, {"error": "Not found"})
        except PermissionError as error:
            self.reply(403, {"error": str(error)})
        except (ValueError, OSError) as error:
            self.reply(400, {"error": str(error)})

    def do_POST(self):
        try:
            self.authorize()
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError("Expected application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("Request body must be between 1 byte and 12 MB")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            studio = self.server.studio
            path = urlsplit(self.path).path
            if path == "/api/save":
                result = studio.save(payload.get("draft"), payload.get("revision"))
            elif path == "/api/image":
                result = studio.image(payload.get("data"))
            elif path in ("/api/render", "/api/preview"):
                result = studio.start_job(path.rsplit("/", 1)[1], payload)
            else:
                return self.reply(404, {"error": "Not found"})
            self.reply(200, result)
        except PermissionError as error:
            self.reply(403, {"error": str(error)})
        except Conflict as error:
            self.reply(409, {"error": str(error)})
        except (ValueError, OSError, TypeError, KeyError) as error:
            self.reply(400, {"error": str(error)})


def serve(workspace, manifest=None, models=None, port=0, open_browser=True):
    studio = Studio(workspace, manifest, models)
    server = StudioServer(studio, port)
    url = server.origin + "/#token=" + server.token
    print(json.dumps({"studio_url": url, "workspace": str(studio.workspace)}), flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        studio.close()
        server.server_close()
