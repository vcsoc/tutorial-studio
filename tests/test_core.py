"""Unit/negative tests; these do not substitute for real neural/media acceptance."""

import json
from pathlib import Path
import sys

import pytest

from tutorial_studio import assets
from tutorial_studio.cli import initialize, main
from tutorial_studio.manifest import asset_path, load_manifest
from tutorial_studio.narration import sentences, spoken_text
from tutorial_studio.render import command, frame, render, stamp


def manifest(tmp_path, **changes):
    value = {"schema_version": 1, "title": "Demo", "voice": "bf_emma", "scenes": [{"title": "Start", "card": "A real workflow", "narration": "Hello. This is a tutorial."}]}
    value.update(changes)
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(value))
    return p


def test_manifest_defaults(tmp_path):
    data, root = load_manifest(manifest(tmp_path))
    assert data["speed"] == 0.94 and root == tmp_path


@pytest.mark.parametrize("changes", [
    {"schema_version": 2}, {"voice": "unknown"}, {"speed": 0}, {"speed": True},
    {"speed": float("nan")}, {"speed": float("inf")}, {"scenes": []},
    {"title": ""}, {"execute": "malicious command"}, {"pronunciations": []},
    {"scenes": [{"title": "A", "card": "B", "image": "x.png", "narration": "C"}]},
    {"scenes": [{"title": "A", "card": "B", "narration": ""}]},
    {"scenes": [{"title": "A", "card": "B", "narration": "C", "run": "echo"}]},
])
def test_invalid_manifests_fail(tmp_path, changes):
    with pytest.raises((ValueError, OSError)):
        load_manifest(manifest(tmp_path, **changes))


def test_asset_confinement(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-private.txt")
    outside.write_text("private")
    (tmp_path / "escape.png").symlink_to(outside)
    try:
        for value in [str(outside), "../" + outside.name, "escape.png"]:
            with pytest.raises(ValueError):
                asset_path(tmp_path, value)
    finally:
        outside.unlink()


def test_init_preserves_existing_file(tmp_path):
    p = tmp_path / "manifest.json"
    initialize(p)
    original = p.read_bytes()
    with pytest.raises(FileExistsError):
        initialize(p)
    assert p.read_bytes() == original


def test_scene_cards_render_and_overflow_fails(tmp_path):
    frame({"title": "A real tutorial", "card": "Step one\nStep two"}, tmp_path, tmp_path / "card.png")
    from PIL import Image
    with Image.open(tmp_path / "card.png") as image:
        assert image.size == (1920, 1080)
    with pytest.raises(ValueError, match="split into more scenes"):
        frame({"title": "Too much", "card": "a\n" * 100}, tmp_path, tmp_path / "overflow.png")


def test_no_implicit_model_download(tmp_path):
    with pytest.raises(PermissionError):
        assets.setup_models(tmp_path / "models")
    assert not (tmp_path / "models").exists()
    with pytest.raises(ValueError):
        assets.verify_models(tmp_path)


def test_altered_model_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "ASSETS", {"tiny": ("remote", "not-the-hash", 4)})
    (tmp_path / "tiny").write_bytes(b"test")
    with pytest.raises(ValueError):
        assets.verify_models(tmp_path)


def test_render_preserves_existing_output(tmp_path):
    p = manifest(tmp_path)
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep").write_text("untouched")
    with pytest.raises(FileExistsError):
        render(p, output)
    assert (output / "keep").read_text() == "untouched"


def test_sentence_alignment_and_pronunciation():
    assert sentences("Welcome. Next step! Ready?") == ["Welcome.", "Next step!", "Ready?"]
    assert spoken_text("Kortex and KortexTools", {"Kortex": "Cortex"}) == "Cortex and KortexTools"
    assert stamp(61.234) == "00:01:01,234"


def test_process_failure_and_timeout():
    with pytest.raises(RuntimeError, match="failed"):
        command([sys.executable, "-c", "raise SystemExit(7)"])
    import subprocess
    with pytest.raises(subprocess.TimeoutExpired):
        command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)


def test_cli_capture_requires_approval(tmp_path, capsys):
    assert main(["capture", str(tmp_path / "plan.json"), "--output", str(tmp_path / "output")]) == 1
    assert "approve-browser" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()
