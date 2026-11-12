"""One shared, local voice catalog for the CLI, Pi extension and listening gallery."""

import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("voices.json").read_text(encoding="utf-8"))
_samples = {}
for voice in CATALOG:
    if voice.get("sample"):
        _samples[voice["language"]] = voice["sample"]
for voice in CATALOG:
    voice.setdefault("sample", _samples[voice["language"]])
BY_ID = {voice["id"]: voice for voice in CATALOG}
VOICES = {voice["id"]: (voice["name"], voice["description"], voice["lang"]) for voice in CATALOG}
