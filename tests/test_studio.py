"""Editor persistence and real HTTP boundaries; no model downloads or target app execution."""

import base64
import copy
import io
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image
import pytest

from tutorial_studio.assets import ROOT
from tutorial_studio.studio import Conflict, Studio, StudioServer


def manifest():
    return {"schema_version": 1, "title": "Editor test", "voice": "af_heart", "speed": 0.94, "pronunciations": {}, "scenes": [{"title": "Welcome", "narration": "Welcome to the editor.", "card": "A simple card"}]}


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 36), "#235344").save(buffer, format="PNG")
    return buffer.getvalue()


def test_empty_incomplete_drafts_and_revision_conflicts(tmp_path):
    studio = Studio(tmp_path / "workspace")
    assert studio.state()["draft"]["scenes"] == []
    empty = copy.deepcopy(studio.draft)
    empty["title"] = ""
    assert studio.save(empty, 0)["revision"] == 1
    value = manifest()
    value["scenes"][0]["narration"] = ""
    studio.save(value, 1)
    assert Studio(studio.workspace).draft == value
    with pytest.raises(Conflict):
        studio.save(manifest(), 1)
    with pytest.raises(ValueError, match="narration"):
        studio.start_job("render", {"revision": 2})
    assert studio.job is None


def test_workspace_rejects_installation_and_symlinks(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        Studio(ROOT / "output" / "editor")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "draft.json").symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ValueError, match="symlink"):
        Studio(workspace)


def test_import_copies_images_and_never_edits_original(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    image = source / "screenshot.png"
    image.write_bytes(png())
    original = manifest()
    original["scenes"][0].pop("card")
    original["scenes"][0]["image"] = "screenshot.png"
    path = source / "manifest.json"
    path.write_text(json.dumps(original))
    before = path.read_bytes()
    studio = Studio(tmp_path / "workspace", path)
    relative = studio.draft["scenes"][0]["image"]
    assert relative.startswith("assets/")
    assert (studio.workspace / relative).is_file()
    studio.draft["title"] = "Changed"
    studio.save(studio.draft, studio.revision)
    assert path.read_bytes() == before
    assert image.read_bytes() == png()
    # Existing drafts take precedence over the optional import argument.
    assert Studio(studio.workspace, path).draft["title"] == "Changed"


def test_images_and_drafts_are_inert_and_bounded(tmp_path):
    studio = Studio(tmp_path / "workspace")
    result = studio.image(base64.b64encode(png()).decode())
    assert (studio.workspace / result["image"]).exists()
    with pytest.raises((ValueError, OSError)):
        studio.image(base64.b64encode(b"<script>bad()</script>").decode())
    for update in ({"execute": "touch bad"}, {"scenes": [{}]}, {"voice": "unknown"}, {"speed": False}):
        data = manifest()
        data.update(update)
        with pytest.raises((ValueError, TypeError)):
            studio.save(data, 0)
    data = manifest()
    data["scenes"][0] = {"title": "Escape", "narration": "No.", "image": "../outside.png"}
    with pytest.raises(ValueError):
        studio.save(data, 0)


@pytest.fixture
def server(tmp_path):
    server = StudioServer(Studio(tmp_path / "workspace"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.studio.close()
    server.server_close()
    thread.join(timeout=5)


def call(server, path, data=None, token=True, headers=None):
    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers["Authorization"] = "Bearer " + server.token
    request_headers.update(headers or {})
    request = Request(server.origin + path, data=None if data is None else json.dumps(data).encode(), headers=request_headers)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read(), response.headers
    except HTTPError as error:
        return error.code, error.read(), error.headers


def test_http_auth_origin_host_and_static_policy(server):
    code, body, headers = call(server, "/", token=False)
    assert code == 200 and b"Make it make sense" in body
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "no-referrer"
    assert call(server, "/api/state", token=False)[0] == 403
    assert call(server, "/api/state", headers={"Origin": "https://evil.example"})[0] == 403
    assert call(server, "/api/state", headers={"Host": "evil.example"})[0] == 403
    assert call(server, "/api/state?token=" + server.token, token=False)[0] == 403
    assert call(server, "/api/state")[0] == 200
    assert call(server, "/api/save", {"draft": manifest(), "revision": 0}, token=False)[0] == 403
    assert call(server, "/api/save", {"draft": manifest(), "revision": 0}, headers={"Content-Type": "text/plain"})[0] == 400
    assert call(server, "/studio.js", token=False)[0] == 200


def test_http_draft_conflicts_upload_and_media_boundaries(server):
    status, body, _ = call(server, "/api/save", {"draft": manifest(), "revision": 0})
    assert status == 200 and json.loads(body)["revision"] == 1
    assert call(server, "/api/save", {"draft": manifest(), "revision": 0})[0] == 409
    assert call(server, "/api/render", {"revision": 0})[0] == 409
    status, body, _ = call(server, "/api/image", {"data": base64.b64encode(png()).decode()})
    assert status == 200
    image = json.loads(body)["image"]
    assert call(server, "/" + image, token=False)[0] == 403
    assert call(server, "/" + image + "?token=" + server.token, token=False)[0] == 200
    assert call(server, "/assets/../draft.json")[0] == 400
    assert call(server, "/media/unknown/tutorial.mp4")[0] == 400
    assert call(server, "/api/preview", {"voice": "not-a-voice"})[0] == 400
    assert call(server, "/api/preview", {"voice": "af_heart", "speed": True})[0] == 400


def test_media_ranges_and_single_workspace_owner(server):
    with pytest.raises(ValueError, match="already open"):
        StudioServer(Studio(server.studio.workspace))
    directory = server.studio.workspace / "sample"
    directory.mkdir()
    (directory / "preview.wav").write_bytes(b"0123456789")
    server.studio.jobs["sample"] = {"status": "complete", "kind": "preview"}
    status, body, headers = call(server, "/media/sample/preview.wav", headers={"Range": "bytes=2-5"})
    assert status == 206 and body == b"2345"
    assert headers["Content-Range"] == "bytes 2-5/10"
    assert call(server, "/media/sample/preview.wav", headers={"Range": "bytes=-3"})[1] == b"789"
    assert call(server, "/media/sample/preview.wav", headers={"Range": "bytes=900-"})[0] == 416
    assert call(server, "/media/sample/operation.log")[0] == 400


def test_live_job_blocks_duplicate_launch_and_is_cancelled(tmp_path):
    import subprocess
    import sys

    studio = Studio(tmp_path / "workspace")
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    studio.process = process
    studio.job = {"status": "running"}
    try:
        with pytest.raises(Conflict, match="finish"):
            studio.start_job("preview", {"voice": "af_heart"})
    finally:
        studio.close()
    assert process.poll() is not None
    with pytest.raises(Conflict, match="shutting down"):
        studio.start_job("preview", {"voice": "af_heart"})
