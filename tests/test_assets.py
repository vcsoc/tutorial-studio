from tutorial_studio import assets
import pytest


def test_existing_download_staging_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "ASSETS", {"tiny": ("unused", "unused", 4)})
    pending = tmp_path / "tiny.download"
    pending.write_bytes(b"user-owned-staging")
    with pytest.raises(FileExistsError):
        assets.setup_models(tmp_path, approved=True)
    assert pending.read_bytes() == b"user-owned-staging"
