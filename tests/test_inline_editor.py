"""Inline editor fields remain inert, portable and present in final rendered visuals."""

import base64
import copy
import io
import json

from PIL import Image, ImageChops
import pytest

from tutorial_studio.manifest import load_manifest
from tutorial_studio.render import frame
from tutorial_studio.studio import Studio


def inline_manifest(tmp_path):
    image = Image.new("RGB", (320, 180), "#ee2233")
    image.save(tmp_path / "screenshot.png")
    data = {"schema_version": 1, "title": "Inline editing", "voice": "af_heart", "scenes": [{
        "title": "Editable title", "breadcrumb": "START HERE", "card": "Editable content.",
        "narration": "Here is the screenshot.", "content_image": "screenshot.png",
    }]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    return path, data


def test_inline_fields_validate_and_import_without_changing_original(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    path, data = inline_manifest(source)
    original = path.read_bytes()
    assert load_manifest(path)[0]["scenes"][0]["breadcrumb"] == "START HERE"
    studio = Studio(tmp_path / "workspace", path)
    scene = studio.draft["scenes"][0]
    assert scene["card"] == "Editable content."
    assert scene["content_image"].startswith("assets/")
    assert (studio.workspace / scene["content_image"]).exists()
    assert path.read_bytes() == original
    assert data["scenes"][0]["content_image"] == "screenshot.png"
    data["scenes"][0]["card"] = ""
    path.write_text(json.dumps(data))
    assert load_manifest(path)[0]["scenes"][0]["card"] == ""


@pytest.mark.parametrize("mutation", [
    {"breadcrumb": "x" * 121}, {"breadcrumb": "\x00bad"},
    {"content_image": "../screenshot.png"}, {"content_image": "/etc/passwd"},
    {"image": "screenshot.png", "card": None},
])
def test_inline_fields_reject_unbounded_or_unsafe_values(tmp_path, mutation):
    path, data = inline_manifest(tmp_path)
    data["scenes"][0].update(mutation)
    if mutation.get("card") is None and "card" in mutation:
        data["scenes"][0].pop("card")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_frame_contains_custom_breadcrumb_and_inline_image(tmp_path):
    _, data = inline_manifest(tmp_path)
    scene = data["scenes"][0]
    frame(scene, tmp_path, tmp_path / "custom.png", number=3)
    automatic = copy.deepcopy(scene)
    automatic.pop("breadcrumb")
    frame(automatic, tmp_path, tmp_path / "automatic.png", number=3)
    with Image.open(tmp_path / "custom.png") as custom, Image.open(tmp_path / "automatic.png") as other:
        assert custom.size == (1920, 1080)
        assert ImageChops.difference(custom.crop((90, 50, 1800, 122)), other.crop((90, 50, 1800, 122))).getbbox()
        assert custom.getpixel((960, 800)) == (238, 34, 51)
    scene["card"] = "\n".join(["Too much text"] * 30)
    with pytest.raises(ValueError, match="Card text exceeds"):
        frame(scene, tmp_path, tmp_path / "overflow.png")


def test_screen_capture_image_is_inert_pixel_data(tmp_path):
    studio = Studio(tmp_path / "workspace")
    image = Image.new("RGB", (1920, 1080), "#2a536a")
    data = io.BytesIO()
    image.save(data, format="PNG")
    result = studio.image(base64.b64encode(data.getvalue()).decode())
    with Image.open(studio.workspace / result["image"]) as saved:
        assert saved.size == (1920, 1080)
        assert saved.getpixel((100, 100)) == (42, 83, 106)
