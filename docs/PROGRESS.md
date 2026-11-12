# Progress And Acceptance

## Scope

Owner approved a local neural narrator download plus a reusable framework/Pi extension. The framework is implemented independently at `/Users/chris/projects/vcsoc/tutorial-studio`. Existing Kortex source, implementation workers, registrations and the original tutorial MP4 were not modified by this task. No push, publication or cloud narration occurred.

## Implemented

- Bounded, inert scene manifests with instructional cards or confined local image assets.
- Verified local Kokoro ONNX inference, 23 offered voice presets, pronunciation rules, measured sentence timings and content-addressed audio cache with blob integrity checks.
- 1080p H.264/AAC renderer, loudness normalization, selectable English captions, chapters, transcript, self-contained rerenderable manifest, model/image/audio/video hashes and incomplete/complete receipts.
- Explicitly approved local browser capture from an already-running numeric-loopback app. New browser context; same-origin HTTP confinement; service-worker/websocket blocking; password/env-input masks; no arbitrary JS/commands, app launcher or implicit browser download.
- Pi `/tutorial` command and `tutorial_studio` tool with interactive mutation approval, no noninteractive approval bypass, argv execution, bounded output, fresh-file protection and no startup background processes.
- Global loader installed at `~/.pi/agent/extensions/tutorial-studio.ts`; CLI wrapper at `~/.local/bin/tutorial-studio`. Owner must run `/reload` or start a new session to expose it in the current Pi session.

## Checks Actually Executed

Environment: Apple Silicon macOS; Python 3.13.13; Kokoro ONNX 0.6.1; ONNX Runtime 1.31.1; existing FFmpeg and trusted Chromium.

- Python suite: **27 passed, zero skips**. Includes actual local neural inference/non-silence/timing/cache reuse/corrupt-cache recovery, manifest/output/asset/download-staging negative cases, subprocess timeout, and actual Pi RPC tests for both the package entry and installed global loader.
- Pi RPC acceptance confirms `/tutorial` registration, parses a real doctor response with `render_ready: true` and exact model asset keys, tests declined mutation leaves no file, and tests approved initialization writes a real valid template. No LLM run or subagent was started by these tests.
- Node suite: **9 passed, zero skips**, including real isolated-browser capture against a local test application, existing-output refusal, and an off-origin fetch blocked before it reaches a separate local HTTP server. Other cases cover literal argv construction, invalid plans/paths and loopback restrictions.
- `npm audit --audit-level=low`: **zero reported vulnerabilities** for the browser dependency tree. Not a full Python/native dependency/legal audit.
- Python source compilation: passed.
- End-to-end neural media render: **22.08 seconds**, two scenes, 1920x1080 H.264, AAC, English subtitle track, two chapters; complete audio/video decode passes. Receipt: `output/smoke-001/receipt.json`. Summary retained in `docs/evidence/render-smoke.json`. This validates the real pipeline, not narrator elegance.
- Model and voices match both pinned sizes and SHA-256 hashes. `tutorial-studio doctor` reports ready. See `docs/PROVENANCE.md`.
- Three real neural voice previews generated: Emma 12.7 seconds, Isabella 13.6 seconds, George 15.3 seconds. Listening gallery at `/Users/chris/Movies/Kortex-Tutorial-VCtz3t/neural-previews/voice-preview.html`.
- Existing Kortex tutorial successfully imported into a self-contained, validated **13-scene** manifest at `/Users/chris/Movies/Kortex-Tutorial-VCtz3t/neural-project/manifest.json`; original files preserved.

Logs and bounded receipts: `docs/evidence/`. GitNexus impact checks were attempted for edits but the fresh standalone code has no graph index; source inspection and executable tests were used instead. No graph safety proof is claimed.

## Expanded International Voice Gallery

Owner requested more voices and international samples. Added one shared 23-voice catalog for Python, Pi tool validation and the interactive narrator picker. The gallery now includes 15 English voices (8 British, 7 American) and 8 native-language voices (French, Spanish, Italian, Brazilian Portuguese, Hindi), with seven locale labels. Locale is a synthesis setting, not a verified nationality or guarantee of an English accent.

- All 23 real samples synthesized or retrieved from hash-verified speech cache using the already-installed model; no additional model/dependency download.
- The original three WAV files are preserved; the original HTML page is backed up by its hash. The full Kortex tutorial remains unchanged.
- Added reusable `tutorial-studio gallery --output DIRECTORY` and approval-gated `/tutorial gallery`. Native-language previews use language-appropriate default text. Rendering now tags captions with the selected voice language rather than always English.
- Actual Chromium gallery check: all 23 audio elements loaded nonzero duration metadata; English filter shows 15; India filter shows 2; choosing Michael displays `am_michael`; desktop and 390px mobile checks pass without horizontal overflow. Receipt: `neural-previews/gallery-browser-validation.json` beside the tutorial. Voice selection buttons only display an ID, never start rendering.
- Latest Python suite: **30 passed, zero skips**. Latest Node/browser suite: **11 passed, zero skips**. Includes shared-catalog parity, real installed voice-pack membership and HTML escaping checks.
- Real French and renewed English media smoke renders complete with full decode; subtitle tags verified as `fra` and `eng`. Outputs: `output/smoke-french-001` and `output/smoke-expanded-english`. These are framework tests, not a replacement Kortex tutorial.
- Human evaluation of naturalness, accent and translation remains pending; no automated aesthetic or native-speaker quality approval claimed.

## Pending Owner Checkpoint

Owner must listen and choose a narrator from the expanded gallery before the full Kortex narration render, as promised. **The original full tutorial has not yet been re-narrated.** The renderer, migrated manifest, assets and voice cache are ready; the README contains the exact render command for the chosen voice.

## Limits

Initial private implementation, not production certification. Acceptance is on macOS only. Rendered scenes are narrated stills, not continuous screen recordings. Captions follow actual synthesized sentence boundaries, not forced word alignment. No app sandbox/DLP guarantee, whole-OS no-network proof, full dependency/license audit, public redistribution, cloned identity, pretrained speech-quality benchmark, or human voice approval is claimed. Initial asset hashes are integrity pins after authorized acquisition, not independent upstream signatures. Generic project tutorial authoring still requires agent source investigation, permissions and reviewed narration/screenshots.
