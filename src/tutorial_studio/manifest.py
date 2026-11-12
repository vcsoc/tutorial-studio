"""Bounded, inert tutorial manifests. No executable steps or remote URLs."""

import json
import math
from pathlib import Path

from .voices import VOICES


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("JSON input exceeds 2 MB")
    return json.loads(path.read_text(encoding="utf-8"))


def asset_path(root, value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Invalid asset path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Assets must be relative paths within the manifest directory")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Asset escapes manifest directory or is not a regular file")
    if path.stat().st_size > 32_000_000:
        raise ValueError("Image asset exceeds 32 MB")
    return path


def text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text, at most {limit} characters")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{name} contains control characters")
    return value


def load_manifest(path):
    path = Path(path).resolve(strict=True)
    data = read_json(path)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Expected manifest schema_version 1")
    allowed = {"schema_version", "title", "voice", "speed", "scenes", "pronunciations"}
    if set(data) - allowed:
        raise ValueError("Unknown manifest fields: " + str(sorted(set(data) - allowed)))
    text(data.get("title"), "title", 180)
    voice = data.get("voice", "bf_emma")
    if voice not in VOICES:
        raise ValueError("Unknown voice; run tutorial-studio voices")
    speed = data.get("speed", 0.94)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or not 0.75 <= speed <= 1.25:
        raise ValueError("speed must be a finite number between 0.75 and 1.25")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 100:
        raise ValueError("Manifest requires 1 to 100 scenes")
    total = 0
    for scene in scenes:
        if not isinstance(scene, dict) or set(scene) - {"title", "narration", "image", "card", "note"}:
            raise ValueError("Invalid scene fields")
        text(scene.get("title"), "scene title", 180)
        total += len(text(scene.get("narration"), "narration", 5000))
        if ("image" in scene) == ("card" in scene):
            raise ValueError("Each scene needs exactly one image or card")
        if "image" in scene:
            asset_path(path.parent, scene["image"])
        else:
            text(scene["card"], "card", 2000)
        if "note" in scene:
            text(scene["note"], "note", 400)
    if total > 50_000:
        raise ValueError("Total narration exceeds 50,000 characters")
    pronunciations = data.get("pronunciations", {})
    if not isinstance(pronunciations, dict) or len(pronunciations) > 100:
        raise ValueError("Invalid pronunciations map")
    for key, value in pronunciations.items():
        text(key, "pronunciation key", 80)
        text(value, "pronunciation value", 100)
    data.setdefault("voice", voice)
    data.setdefault("speed", speed)
    data.setdefault("pronunciations", {})
    return data, path.parent
