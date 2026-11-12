# Local Neural Narration Provenance

Owner explicitly approved the local model download and framework/extension implementation in this session. Nothing was uploaded. No model is implicitly fetched at inference time.

## Assets

Source release: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

| Local file | Upstream release filename | Bytes | SHA-256 |
|---|---|---:|---|
| model.onnx | kokoro-v1.0.onnx | 325532387 | 7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5 |
| voices.bin | voices-v1.0.bin | 28214398 | bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d |

These hashes were independently computed after the initial authorized HTTPS download. The GitHub release API supplied no digest for these assets. They pin subsequent bytes but do not constitute upstream signing or independent supply-chain certification. The model/voice arrays are loaded as ONNX/NumPy data, not pickled Python objects. Runtime package model downloads are not used.

The upstream Kokoro-82M model card declares Apache-2.0. A source copy of that card is retained at `third-party/Kokoro-model-card.md`, pinned to Hugging Face model repository revision `f3ff3571791e39611d31c381e3a41a3af07b4987`. A separate model LICENSE file was not available at that revision. No independent voice-data provenance or legal approval is claimed.

## Runtime

- kokoro-onnx 0.6.1: MIT; upstream notice retained at `third-party/kokoro-onnx-LICENSE.txt`.
- ONNX Runtime 1.31.1: local CPU execution, configured to four intra-op threads and one inter-op thread.
- espeakng-loader/phonemizer: local phonemization dependencies; upstream GPL-related obligations require review before any redistribution.
- Full Python environment version inventory is in `requirements.lock`; npm integrity pins are in `package-lock.json`.
- FFmpeg is an existing owner-installed executable; the framework does not redistribute it or claim its build/license configuration has been audited.

## Privacy And Scope

Model acquisition and dependency installation use network access explicitly. Narration uses local assets and has no remote narration endpoint. Browser capture confines application requests to the explicitly selected numeric loopback origin; external app dependencies are unsupported rather than silently enabled. These controls are not a whole-operating-system sandbox or a guarantee that an application cannot expose private content in screenshots.

First-party framework remains private. `package.json` is private; there is no public package, GitHub upload, tag, release, public license grant or publication authorization. The existing Kortex proprietary policy is not changed. Private use evidence is not legal or production release approval.
