# Tutorial Studio

Private, local-first tutorial production framework and Pi extension. Built independently of Kortex so the same workflow works across projects.

## What It Does

- Synthesizes narration locally with Kokoro-82M ONNX instead of basic macOS speech.
- Offers 23 local voices: 8 British English, 7 American English, and 8 native-language French, Spanish, Italian, Brazilian Portuguese and Hindi voices.
- Converts inert JSON scene manifests into 1080p H.264/AAC MP4s with selectable captions, chapters and a transcript. Subtitle language metadata follows the chosen voice; supply narration in that language.
- Uses existing screenshots or creates instructional cards. These are narrated still scenes, **not continuous mouse-action recordings**.
- Optionally captures an already-running, explicitly approved loopback web app with Playwright.
- Writes model/audio/image hashes and a full-decode validation receipt; caches speech by text, model, voice, pace and pronunciation rules.
- Preserves existing files by requiring fresh render directories and new preview filenames.

No cloud TTS, voice cloning, remote provider keys, automatic project execution, app launching, browser/model downloads during rendering, or publishing. Voice quality still needs human listening approval.

## This Machine

```sh
STUDIO=/Users/chris/projects/vcsoc/tutorial-studio/.venv/bin/tutorial-studio
"$STUDIO" doctor
"$STUDIO" voices
```

Global Pi loader: `~/.pi/agent/extensions/tutorial-studio.ts`. Run `/reload` in Pi to discover it, or start another Pi session. The extension is not hot-loaded into the agent's current tool inventory just by writing the file.

## Install On Another Machine

Use owner-authorized access to this private framework directory; no public distribution has been approved. Tested on Apple Silicon macOS, not certified on Windows/Linux.

Prerequisites: trusted Python 3.10-3.13 (3.13 tested), FFmpeg/ffprobe, and optionally Node.js plus an existing Chromium executable for browser capture. Do not run another project's setup scripts merely to produce documentation.

```sh
cd /path/to/tutorial-studio
uv venv --python 3.13
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
# Only if you want browser capture:
npm ci --ignore-scripts --legacy-peer-deps

# Explicit one-time model acquisition, about 354 MB:
.venv/bin/tutorial-studio setup-model --approve-download
.venv/bin/tutorial-studio doctor
```

`setup-model` obtains the model and voice arrays from the named kokoro-onnx GitHub release and verifies pinned size/SHA-256. Rendering refuses missing/changed assets instead of downloading a substitute. Those pins were recorded at initial authorized acquisition; they are not an independent upstream signature. See `docs/PROVENANCE.md`.

## Consumer Use Is Read-Only

Agents using Tutorial Studio to build another project's tutorial may use its documented tools and CLI, but must treat the framework installation, extension and global loader/registrations as read-only infrastructure. A tutorial request does not authorize framework maintenance.

- Do not edit, delete, move, patch or upgrade framework/extension source, documentation, progress logs, tests, configuration, dependencies or model assets. Do not commit or push changes to this repository from consumer sessions.
- Keep tutorial manifests, screenshots, narration scripts, drafts, previews, render outputs, receipts and project-specific progress notes in the consuming project or an explicitly approved external workspace, not this checkout.
- Normal runtime cache writes by the framework are expected; they are not permission for agents to modify framework internals.
- If a feature is missing or a command fails, report the issue and request maintenance here rather than patching the installed tool from another project.
- Exception: the owner may explicitly request framework/extension changes while working directly in the Tutorial Studio project. Merely reading framework files or running its CLI from the installation directory does not qualify.

These are agent instructions, not an operating-system filesystem sandbox.

## Pi Usage

```text
/tutorial
/tutorial doctor
/tutorial voices
/tutorial init /absolute/path/to/my-tutorial/manifest.json
/tutorial validate /absolute/path/to/my-tutorial/manifest.json
/tutorial preview
/tutorial gallery
/tutorial render /absolute/path/to/my-tutorial/manifest.json
/tutorial capture /absolute/path/to/reviewed-capture-plan.json
```

`/tutorial` opens a menu. Preview asks for a voice and new WAV path. Render asks for a fresh output directory. Every mutating operation asks for interactive confirmation. Model download is intentionally a separate explicit CLI setup action, not an implicit extension action.

On another machine, register the local Pi package once with `pi install /absolute/path/to/tutorial-studio`, then run `/reload`. Use either that package registration or a global loader, not both; this machine already has the global loader installed.

The `tutorial_studio` model tool exposes the same actions. It requires interactive approval for mutations, including capture. In noninteractive automation, invoke the CLI deliberately; there is no hidden approval-bypass tool parameter. All CLI invocations use argument arrays, not shell interpolation. The extension starts no background resources on load.

Reusable agent request:

> Create a private tutorial for this project using Tutorial Studio. Read the framework README first. Inspect the real documented workflows, create a short storyboard, and write a scene manifest using verified commands and actual application screenshots. Never claim a command succeeded unless it ran. Do not execute project code, start services or capture sensitive data without approval. Make a neural voice preview and wait for my voice approval before rendering the full video. Produce MP4, captions, transcript and a validation receipt. Do not publish anything. Use Tutorial Studio as read-only infrastructure: do not modify its framework, extension, loader, dependencies, documentation or progress logs. Keep all tutorial artifacts and project notes in this project's workspace or an approved external output directory. Report framework issues for maintenance in the Tutorial Studio project; do not fix them from this consumer session.

## Voice Preview First

```sh
.venv/bin/tutorial-studio preview \
  --voice bf_emma --speed 0.94 \
  --output /absolute/new-path/emma.wav
```

Use `tutorial-studio voices` for the full shared catalog; Pi and the CLI use the same IDs. Slower speed numbers produce a more measured pace (allowed 0.75-1.25). Preview the pronunciation of product names. Built-in narrator behavior comes from the neural voice; there is no false claim of human or cloned narration.

Generate or expand an offline listening gallery with real samples:

```sh
.venv/bin/tutorial-studio gallery --output /absolute/path/to/voice-previews
```

This is also available as `/tutorial gallery`. Unlike full renders, a gallery directory can already exist: existing audio is retained, conflicting audio names receive a hash suffix, and the old `voice-preview.html` is backed up before replacement. The gallery includes language/locale filters, sample text, and buttons that display the selected voice ID without starting a render. Preview defaults use the voice's own language; `--text` can provide a custom sample.

English candidates: Emma, Isabella, George, Alice, Lily, Daniel, Fable, Lewis, Heart, Bella, Nicole, Sarah, Michael, Fenrir and Adam. International samples: Siwis (French), Dora/Alex (Spanish), Sara/Nicola (Italian), Dora (Brazilian Portuguese), Alpha/Psi (Hindi). Locale labels indicate synthesis language settings, not verified speaker nationality. International voices are **not advertised as English accents**. A non-English tutorial requires a reviewed translation and suitable visuals/fonts; selecting a voice does not translate narration.

## Author A Project Tutorial

```sh
.venv/bin/tutorial-studio init /absolute/path/tutorial/manifest.json \
  --title 'My Project: Getting Started'
```

Edit the generated template with accurate narration and visuals:

```json
{
  "schema_version": 1,
  "title": "My Project: Getting Started",
  "voice": "bf_emma",
  "speed": 0.94,
  "pronunciations": {"Kortex": "Cortex"},
  "scenes": [
    {
      "title": "What you will learn",
      "card": "1. Prepare the project\n2. Perform a real workflow\n3. Check the result",
      "narration": "Welcome. We will walk through the project and complete a real workflow."
    },
    {
      "title": "Explore the interface",
      "image": "screenshots/explore.png",
      "narration": "Select the project, then choose a symbol to inspect its dependencies."
    }
  ]
}
```

Images must be within the manifest directory, referenced with relative paths. Absolute paths, `..` escapes, unsupported actions, unknown fields, oversized inputs, and missing assets fail validation. Cards are instructional graphics, not evidence that their displayed commands ran. Store real command receipts separately when needed. No manifest field executes arbitrary shell commands or JavaScript.

```sh
.venv/bin/tutorial-studio validate /absolute/path/tutorial/manifest.json
.venv/bin/tutorial-studio render /absolute/path/tutorial/manifest.json \
  --output /absolute/new-path/tutorial-emma
```

Outputs: `tutorial.mp4`, `captions.srt`, `TRANSCRIPT.md`, `receipt.json`, a self-contained `manifest.json`, normalized visuals, and retained speech/segment files. `receipt.json` remains `incomplete` on failures; success is recorded only after final stream/size/chapter checks and a full video/audio decode. Captions use measured synthesized sentence boundaries, not word-level forced alignment. FFmpeg normalizes narration loudness; it does not measure aesthetic voice quality.

Use `--voice bm_george` on render to override the manifest without editing it. Existing output directories are refused, including incomplete ones: pick a fresh path and inspect the retained failure receipt. Speech caches let retries reuse verified synthesis.

## Capture Real Web Screens

First start the application yourself after reviewing its instructions and obtaining any needed execution approval. The framework does **not** start or build the target app.

Set an existing trusted browser path:

```sh
export TUTORIAL_CHROMIUM_EXECUTABLE='/absolute/path/to/Chromium'
```

Example `capture-plan.json`:

```json
{
  "schema_version": 1,
  "url": "http://127.0.0.1:7337",
  "mask": [".private-customer-name"],
  "steps": [
    {"action": "fill", "selector": "input[aria-label='Bearer token']", "env": "MY_DEMO_TOKEN"},
    {"action": "click", "selector": "button:text-is('Connect')"},
    {"action": "wait", "selector": "select[aria-label='Repository']"},
    {"action": "screenshot", "name": "connected.png"}
  ]
}
```

```sh
.venv/bin/tutorial-studio capture /absolute/path/capture-plan.json \
  --output /absolute/new-path/screenshots --approve-browser
```

Supported actions: click, fill, press, wait-for-visible, scroll-into-view, screenshot. Capture uses a fresh profile, numeric loopback addresses only, same-origin HTTP requests only, blocked service workers/websockets, no downloads, and no arbitrary evaluate/script action. Initial URL queries/fragments/credentials are refused. Secrets can come from environment variables and are masked in screenshots along with password fields. There is **no general DLP guarantee**: applications may echo a secret or show other private data elsewhere. Review the plan and screenshots; use synthetic projects/accounts. Clicking or filling can mutate application state.

Remote capture and off-origin integrations are deliberately unsupported. Screenshots are refused if off-origin requests are observed. Screenshots already written before a later failure must not be treated as a completed capture; success requires `capture-receipt.json`.

## Kortex Tutorial Migration

The existing Kortex tutorial has been imported without altering the original:

```text
/Users/chris/Movies/Kortex-Tutorial-VCtz3t/neural-project/manifest.json
```

After choosing the narrator:

```sh
.venv/bin/tutorial-studio render \
  /Users/chris/Movies/Kortex-Tutorial-VCtz3t/neural-project/manifest.json \
  --voice bf_emma \
  --output /Users/chris/Movies/Kortex-Tutorial-Neural-Emma
```

The one-time compatibility command is `import-legacy SOURCE_SCENES_JSON NEW_DIRECTORY`; it copies the original numbered screenshots into a self-contained Kortex manifest. The generic framework does not otherwise depend on Kortex or its checkout.

## Validation

```sh
.venv/bin/python -m pytest -q
TUTORIAL_CHROMIUM_EXECUTABLE='/absolute/path/to/Chromium' npm test
.venv/bin/tutorial-studio verify-video /absolute/path/tutorial.mp4
```

Python acceptance includes actual Pi RPC load/doctor/approval checks (no LLM requests), actual local model inference and cache integrity when assets are provisioned, plus input/failure tests. Browser acceptance uses a real isolated local page and verifies off-origin traffic never reaches a second local server. Missing prerequisites cause explicit test skips; do not report skipped tests as passes. Media integration evidence is in `docs/PROGRESS.md`.

Limitations: first private implementation, macOS-only acceptance; no human approval of narrator quality until the owner listens; no live recording/video-scene import, forced word alignment, arbitrary command runner, service manager, autonomous cross-project documentation, hosted publishing, comprehensive sandbox/DLP, or production certification.
