"""Real model inference/cache acceptance; skip only when explicitly unprovisioned."""

import json

import numpy as np
import pytest
import soundfile as sf

from tutorial_studio.assets import DEFAULT_MODELS, verify_models
from tutorial_studio.narration import Narrator


@pytest.mark.skipif(not (DEFAULT_MODELS / "model.onnx").is_file(), reason="Owner-approved local model has not been provisioned")
def test_real_neural_speech_sentence_timings_and_cache(tmp_path):
    verify_models()
    narrator = Narrator(cache=tmp_path / "cache")
    text = "Welcome to the local tutorial. Your project stays on this machine."
    wav, receipt = narrator.synthesize(text, voice="bf_emma", speed=0.94)
    samples, rate = sf.read(wav)
    assert rate == 24000 and samples.ndim == 1
    assert 2 < len(samples) / rate < 30
    assert np.isfinite(samples).all() and np.max(np.abs(samples)) > 0.01
    assert len(receipt["timings"]) == 2
    assert receipt["timings"][0]["end"] < receipt["timings"][1]["start"]
    assert receipt["timings"][-1]["end"] <= receipt["duration"]
    before = wav.stat().st_mtime_ns
    second = Narrator(cache=tmp_path / "cache")
    again, cached = second.synthesize(text, voice="bf_emma", speed=0.94)
    assert second.engine is None, "Verified cached speech must not initialize the model"
    assert again == wav and cached == receipt and wav.stat().st_mtime_ns == before
    # A corrupt cache blob must not be mistaken for a successful cached voice.
    wav.write_bytes(b"corrupt")
    repaired, fresh = narrator.synthesize(text, voice="bf_emma", speed=0.94)
    assert sf.info(repaired).frames > 1000
    assert fresh["wav_sha256"] != "corrupt"
    json.loads((tmp_path / "cache" / (fresh["cache_key"] + ".json")).read_text())
