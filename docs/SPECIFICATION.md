# Tutorial Studio 0.1 - Implementation Contract

Private local framework, separate from Kortex. No public license or publication is authorized.

## Goals

- Reusable JSON scene manifests for any software project, independent of its language or build system.
- Offline Kokoro ONNX neural narration, with English and clearly labeled native-language international previews, explicit asset installation, SHA-256 verification, no voice cloning and no remote narration upload.
- Render screenshot or instructional-card scenes into H.264/AAC MP4 with subtitles tagged for the selected voice language, chapters, transcript, provenance and full media-decode validation.
- Optional, explicitly approved local browser capture from an already-running loopback app. No repository scripts or arbitrary shell commands executed by a manifest. Browser network traffic confined to its approved origin.
- Pi package with an interactive slash command and an approval-gated model tool. No child jobs or resources launched on extension load.
- Preserve existing outputs: fresh directories, never overwrite an original tutorial. Cache invalidation by text/model/voice/speed hashes.

## Browser Studio Editing

The browser editor uses the same inert scene manifest and an external workspace. Optional scene fields `breadcrumb` (1-120 characters) and `content_image` (a validated relative image path) extend schema version 1 without breaking older manifests. A `content_image` requires a card, whose text may be empty when the image is present. It renders below the text; a full-scene `image` remains mutually exclusive with the card. Inline text editing never executes or saves pasted HTML. Completed render manifests retain a flattened self-contained visual and drop the original `content_image` reference.

The admin interface follows the neutral Waypoint/Waypass visual language and offers light/dark themes. The UI theme does not change video artwork. Studio voice-library previews use a common English introduction and a playback Stop toggle; this is not a claim of native English support for every voice.

The content toolbar's screen capture is distinct from the CLI's loopback Playwright capture: it uses a user-initiated browser screen/window/tab permission picker, captures exactly one still, stops all media tracks, and requires review/explicit insertion before writing it into the workspace. It performs no scripted interactions with the captured application. Unsupported or denied capture leaves the scene unchanged. Images/captures contain user-selected pixels, so private-data review remains the user's responsibility.

## Acceptance

Real local neural inference and audio duration/signal checks; complete render/decode of a multi-scene fixture; imported Kortex tutorial integration; input/output/path/approval/cancellation failure tests; actual Pi extension load plus command registration and doctor execution. Voice elegance requires owner listening approval, not a fabricated automated score.

## Boundaries

Not a screen-recording editor, autonomous app launcher, remote/cloud TTS client, package publisher, or cross-platform production claim. Initial scenes use still captures; optional browser capture performs approved explicit actions, not arbitrary JavaScript. Captions are aligned to synthesized sentence audio, not word-level forced alignment. Third-party licenses remain their own; recorded hashes are integrity pins after initial authorized acquisition, not independent upstream authenticity certification.
