"""Local neural speech with sentence-level timing and content-addressed cache."""

import hashlib
import json
import re
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .assets import DEFAULT_MODELS, ROOT, sha256, verify_models
from .manifest import VOICES


def sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n+", text.strip()) if part.strip()]


def spoken_text(text, pronunciations):
    for key in sorted(pronunciations, key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(key) + r"(?!\w)", lambda _: pronunciations[key], text)
    return text


class Narrator:
    def __init__(self, models=DEFAULT_MODELS, cache=None):
        self.models = Path(models)
        self.hashes = verify_models(models)
        self.cache = Path(cache or ROOT / ".cache" / "speech")
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.engine = None

    def _engine(self):
        if self.engine is None:
            import onnxruntime as ort
            from kokoro_onnx import Kokoro

            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(str(self.models / "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
            self.engine = Kokoro.from_session(session, str(self.models / "voices.bin"))
        return self.engine

    def synthesize(self, text, voice="bf_emma", speed=0.94, pronunciations=None):
        if voice not in VOICES or not 0.75 <= speed <= 1.25:
            raise ValueError("Invalid voice or speech speed")
        if not isinstance(text, str) or not text.strip() or len(text) > 5000:
            raise ValueError("Narration must contain 1 to 5000 characters")
        pronunciations = pronunciations or {}
        key = hashlib.sha256(json.dumps({"text": text, "voice": voice, "speed": speed, "pronunciations": pronunciations, "models": self.hashes, "pipeline": "kokoro-onnx-0.6.1-sentence-pcm-v1"}, sort_keys=True).encode()).hexdigest()
        wav, metadata = self.cache / f"{key}.wav", self.cache / f"{key}.json"
        if wav.is_file() and metadata.is_file():
            try:
                data = json.loads(metadata.read_text())
                if data["wav_sha256"] == sha256(wav):
                    return wav, data
            except (ValueError, KeyError):
                pass
        clips, timings, cursor = [], [], 0.0
        engine = self._engine()
        rate = 24000
        for sentence in sentences(text):
            samples, actual_rate = engine.create(spoken_text(sentence, pronunciations), voice=voice, speed=speed, lang=VOICES[voice][2])
            samples = np.asarray(samples, dtype=np.float32)
            if actual_rate != rate or samples.ndim != 1 or not 240 <= len(samples) <= rate * 180 or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 0.001:
                raise ValueError("Neural synthesis returned invalid or silent audio")
            duration = len(samples) / rate
            timings.append({"start": cursor, "end": cursor + duration, "text": sentence})
            pause = np.zeros(round(rate * 0.23), dtype=np.float32)
            clips.extend([samples, pause])
            cursor += duration + len(pause) / rate
            if cursor > 300:
                raise ValueError("Scene narration exceeds 5 minutes")
        audio = np.concatenate(clips)
        data = {"voice": voice, "speed": speed, "sample_rate": rate, "duration": len(audio) / rate, "timings": timings, "model_hashes": self.hashes, "cache_key": key, "alignment": "synthesized sentence boundaries; no word-level forced alignment"}
        with tempfile.TemporaryDirectory(dir=self.cache) as temporary:
            tmp = Path(temporary) / "speech.wav"
            sf.write(tmp, audio, rate, subtype="PCM_16")
            data["wav_sha256"] = sha256(tmp)
            tmp.replace(wav)
            meta = Path(temporary) / "speech.json"
            meta.write_text(json.dumps(data, indent=2) + "\n")
            meta.replace(metadata)
        return wav, data
