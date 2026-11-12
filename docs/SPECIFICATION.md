# Tutorial Studio 0.1 - Implementation Contract

Private local framework, separate from Kortex. No public license or publication is authorized.

## Goals

- Reusable JSON scene manifests for any software project, independent of its language or build system.
- Offline Kokoro ONNX neural narration, with English and clearly labeled native-language international previews, explicit asset installation, SHA-256 verification, no voice cloning and no remote narration upload.
- Render screenshot or instructional-card scenes into H.264/AAC MP4 with subtitles tagged for the selected voice language, chapters, transcript, provenance and full media-decode validation.
- Optional, explicitly approved local browser capture from an already-running loopback app. No repository scripts or arbitrary shell commands executed by a manifest. Browser network traffic confined to its approved origin.
- Pi package with an interactive slash command and an approval-gated model tool. No child jobs or resources launched on extension load.
- Preserve existing outputs: fresh directories, never overwrite an original tutorial. Cache invalidation by text/model/voice/speed hashes.

## Acceptance

Real local neural inference and audio duration/signal checks; complete render/decode of a multi-scene fixture; imported Kortex tutorial integration; input/output/path/approval/cancellation failure tests; actual Pi extension load plus command registration and doctor execution. Voice elegance requires owner listening approval, not a fabricated automated score.

## Boundaries

Not a screen-recording editor, autonomous app launcher, remote/cloud TTS client, package publisher, or cross-platform production claim. Initial scenes use still captures; optional browser capture performs approved explicit actions, not arbitrary JavaScript. Captions are aligned to synthesized sentence audio, not word-level forced alignment. Third-party licenses remain their own; recorded hashes are integrity pins after initial authorized acquisition, not independent upstream authenticity certification.
