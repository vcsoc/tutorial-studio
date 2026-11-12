"""Explicitly provisioned, pinned local model assets; inference never downloads."""

import hashlib
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS = ROOT / ".models" / "kokoro-v1"
SOURCE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
ASSETS = {
    "model.onnx": ("kokoro-v1.0.onnx", "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5", 325532387),
    "voices.bin": ("voices-v1.0.bin", "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d", 28214398),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_models(directory=DEFAULT_MODELS):
    directory = Path(directory)
    result = {}
    for name, (_, expected, size) in ASSETS.items():
        file = directory / name
        if file.is_symlink() or not file.is_file() or file.stat().st_size != size or sha256(file) != expected:
            raise ValueError(f"Missing or altered model asset: {file}. Explicitly run setup-model --approve-download.")
        result[name] = expected
    return result


def setup_models(directory=DEFAULT_MODELS, approved=False):
    if not approved:
        raise PermissionError("Model download requires --approve-download (about 354 MB, GitHub release assets)")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, (remote, expected, size) in ASSETS.items():
        target = directory / name
        if target.exists() or target.is_symlink():
            if target.is_symlink() or target.stat().st_size != size or sha256(target) != expected:
                raise ValueError(f"Refusing to overwrite existing mismatched asset: {target}")
            continue
        temp = target.with_suffix(target.suffix + ".download")
        created = False
        try:
            request = urllib.request.Request(SOURCE + remote, headers={"User-Agent": "private-tutorial-studio/0.1"})
            with temp.open("xb") as stream:
                created = True
                with urllib.request.urlopen(request, timeout=90) as response:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > size:
                            raise ValueError("Model download exceeded pinned size")
                        stream.write(chunk)
            if total != size or sha256(temp) != expected:
                raise ValueError("Model download integrity check failed")
            os.chmod(temp, 0o600)
            temp.rename(target)
        finally:
            if created and temp.exists():
                temp.unlink()
    receipt = {"source": SOURCE, "files": verify_models(directory), "trust": "SHA-256 pins recorded at initial owner-authorized acquisition; not independent upstream authentication"}
    (directory / "assets.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
