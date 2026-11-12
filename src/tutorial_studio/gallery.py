"""Build a reusable, offline listening gallery with real local speech samples."""

import html
import json
from pathlib import Path
import shutil

from .assets import sha256
from .narration import Narrator
from .voices import CATALOG

STYLE = """
:root{--ink:#183a32;--paper:#f6f0e2;--muted:#607268;--line:#d4d8c8;--gold:#98712f}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:radial-gradient(ellipse at 5% 0%,#dce8d3,transparent 55%),linear-gradient(125deg,var(--paper),#fbf8ef);min-height:100vh;font-family:Georgia,'Times New Roman',serif}.page{max-width:1180px;margin:auto;padding:65px 32px}.eyebrow{font:13px/1.5 Menlo,monospace;letter-spacing:3px;color:var(--gold);text-transform:uppercase}h1{font-size:clamp(42px,7vw,78px);font-weight:normal;line-height:1.04;letter-spacing:-2px;margin:25px 0}p{font-size:18px;line-height:1.6;max-width:850px;color:var(--muted)}.notice{padding:18px 22px;border-left:3px solid var(--gold);background:#fff8df}.filters{display:flex;gap:15px;flex-wrap:wrap;margin:30px 0;align-items:center}select{font:16px Georgia,serif;padding:12px 35px 12px 12px;color:var(--ink);border:1px solid var(--line);background:#fff9ed;border-radius:4px;max-width:100%}.choices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:28px 0}.voice{min-width:0;padding:27px 22px;border:1px solid var(--line);background:#ffffff99;border-radius:5px;animation:reveal .5s both}.voice[hidden]{display:none}.number{font:12px Menlo,monospace;color:var(--gold)}h2{font-size:32px;font-weight:normal;margin:20px 0 8px}.description{font-size:16px;margin:0 0 15px}.locale{display:block;font:12px/1.6 Menlo,monospace;color:var(--muted);margin-bottom:20px}audio{width:100%;max-width:100%}details{margin-top:17px;font-size:15px;line-height:1.7}summary{cursor:pointer;color:var(--gold)}.sample{font-size:15px;line-height:1.7;overflow-wrap:anywhere}.copy{font:13px Menlo,monospace;border:1px solid var(--line);padding:10px 12px;background:#eef2e6;color:var(--ink);cursor:pointer;margin-top:12px;min-height:42px}.copy:hover,.copy:focus{border-color:var(--gold)}.status{min-height:24px;font-size:14px}footer{font:12px/1.8 Menlo,monospace;color:var(--muted);border-top:1px solid var(--line);padding-top:24px}@keyframes reveal{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}@media(max-width:850px){.choices{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.page{padding:35px 18px}.choices{grid-template-columns:1fr}h1{letter-spacing:-1px}.filters{align-items:stretch;flex-direction:column}}@media(prefers-reduced-motion:reduce){.voice{animation:none}}
"""
SCRIPT = """
const cards=[...document.querySelectorAll('.voice')];
const language=document.querySelector('#language');
const locale=document.querySelector('#locale');
const count=document.querySelector('#count');
function filter(){let visible=0;for(const card of cards){card.hidden=(language.value!=='all'&&card.dataset.language!==language.value)||(locale.value!=='all'&&card.dataset.locale!==locale.value);if(!card.hidden)visible++;else card.querySelector('audio').pause();}count.textContent=visible+' of '+cards.length+' voices';}
language.addEventListener('change',filter);locale.addEventListener('change',filter);filter();
for(const audio of document.querySelectorAll('audio'))audio.addEventListener('play',()=>{for(const other of document.querySelectorAll('audio'))if(other!==audio)other.pause();});
for(const button of document.querySelectorAll('.copy'))button.addEventListener('click',()=>{document.querySelector('#selection').textContent='Selected '+button.dataset.voice+'. Tell the agent this voice ID to use it. This does not start a render.';});
"""


def page_html(voices):
    esc = html.escape
    cards = []
    for index, voice in enumerate(voices, 1):
        sample = esc(voice["sample"])
        kind = "English tutorial candidate" if voice["language"] == "English" else "Native-language sample / script translation needed"
        cards.append(f'''<section class="voice" data-language="{esc(voice['language'])}" data-locale="{esc(voice['locale'])}">
<span class="number">{index:02} / {esc(voice['id'])}</span><h2>{esc(voice['name'])}</h2><p class="description">{esc(voice['description'])}</p><span class="locale">Locale: {esc(voice['locale'])}<br>{kind}</span>
<audio controls preload="metadata" aria-label="Listen to {esc(voice['name'])}, {esc(voice['description'])}"><source src="{esc(voice['file'])}" type="audio/wav"></audio>
<details><summary>Read sample / {voice['duration']:.1f} seconds</summary><p class="sample" lang="{esc(voice['lang'])}">{sample}</p></details><button class="copy" data-voice="{esc(voice['id'])}">Choose {esc(voice['id'])}</button></section>''')
    languages = sorted({v["language"] for v in voices})
    locales = sorted({v["locale"] for v in voices})
    language_options = ''.join(f'<option>{esc(v)}</option>' for v in languages)
    locale_options = ''.join(f'<option>{esc(v)}</option>' for v in locales)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kortex / Choose Your Narrator</title><style>{STYLE}</style></head>
<body><main class="page"><div class="eyebrow">Kortex / Local Neural Narration</div><h1>Find the voice<br>for your story.</h1><p>{len(voices)} real local voice samples across seven language locales. Compare the English voices for the English Kortex tutorial, or explore international-language narration. Choose a voice below and tell the agent its ID.</p>
<p class="notice"><strong>Language matters.</strong> International samples are spoken in their own languages, not presented as verified English accents. Locale labels describe the synthesis language setting, not a verified nationality. A non-English tutorial needs a reviewed translation; choosing a voice does not translate the script.</p>
<div class="filters"><label>Language <select id="language"><option value="all">All languages</option>{language_options}</select></label><label>Locale <select id="locale"><option value="all">All locales</option>{locale_options}</select></label><span id="count" role="status"></span></div>
<p id="selection" class="status" aria-live="polite">No voice selected. The full tutorial has not been re-rendered.</p><div class="choices">{''.join(cards)}</div>
<footer>Synthesized locally with Kokoro ONNX. No model download, cloud narration or voice cloning for this gallery expansion.<br>Human listening approval is still required. The original video and original three samples are preserved.</footer></main><script>{SCRIPT}</script></body></html>'''


def build_gallery(directory, models=None):
    directory = Path(directory).expanduser().absolute()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    narrator = Narrator(**({"models": models} if models else {}))
    result = []
    for voice in CATALOG:
        print(f"Generating voice sample: {voice['id']} / {voice['description']}", flush=True)
        wav, speech = narrator.synthesize(voice["sample"], voice["id"], 0.94, {"Kortex": "Cortex"})
        filename = {"bf_emma": "emma.wav", "bf_isabella": "isabella.wav", "bm_george": "george.wav"}.get(voice["id"], voice["id"] + ".wav")
        destination = directory / filename
        if destination.exists() and sha256(destination) != speech["wav_sha256"]:
            filename = voice["id"] + "-" + speech["wav_sha256"][:12] + ".wav"
            destination = directory / filename
        if not destination.exists():
            with destination.open("xb") as target, wav.open("rb") as source:
                shutil.copyfileobj(source, target)
        if sha256(destination) != speech["wav_sha256"]:
            raise ValueError("Gallery output audio integrity mismatch")
        result.append({**voice, "file": filename, "duration": speech["duration"], "sha256": speech["wav_sha256"]})
    page = directory / "voice-preview.html"
    if page.exists():
        backup = directory / ("voice-preview-backup-" + sha256(page)[:12] + ".html")
        if not backup.exists():
            with backup.open("xb") as target, page.open("rb") as source:
                shutil.copyfileobj(source, target)
    content = page_html(result)
    temp = directory / "voice-preview.html.pending"
    with temp.open("x", encoding="utf-8") as stream:
        stream.write(content)
    temp.replace(page)
    receipt = {"status": "complete", "voices": result, "count": len(result), "model_hashes": narrator.hashes, "full_tutorial_rendered": False}
    (directory / "gallery-receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n")
    return {"page": str(page), "voices": len(result), "languages": sorted({v['language'] for v in result}), "full_tutorial_rendered": False}
