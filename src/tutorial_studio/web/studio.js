'use strict';
const $ = id => document.getElementById(id);
const themeMedia = matchMedia('(prefers-color-scheme: dark)');
let explicitTheme;
try { explicitTheme = localStorage.getItem('tutorial-studio-theme'); } catch { /* Storage may be disabled. */ }
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('theme-toggle').setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
  $('theme-toggle').title = $('theme-toggle').getAttribute('aria-label');
  $('theme-toggle').setAttribute('aria-pressed', String(theme === 'dark'));
}
applyTheme(['light', 'dark'].includes(explicitTheme) ? explicitTheme : themeMedia.matches ? 'dark' : 'light');
$('theme-toggle').onclick = () => {
  explicitTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(explicitTheme);
  try { localStorage.setItem('tutorial-studio-theme', explicitTheme); } catch { /* Theme still works without persistence. */ }
};
themeMedia.addEventListener('change', event => { if (!explicitTheme) applyTheme(event.matches ? 'dark' : 'light'); });
const fragment = new URLSearchParams(location.hash.slice(1));
let token = fragment.get('token') || sessionStorage.getItem('tutorial-studio-token') || '';
if (token) sessionStorage.setItem('tutorial-studio-token', token);
history.replaceState(null, '', location.pathname);
let draft, revision, voices = [], selected = 0, dirty = false, busy = false, lastJob = '', lastStatus = '', changeVersion = 0;
let saving = false;
let previewVoice = '', preparingVoice = '';
let toastTimer;
let pendingCapture, captureUrl, captureInserting = false;
const node = (tag, text, className) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
};
function toast(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 7000);
}
function guard(fn) { return async (...args) => { try { await fn(...args); } catch (e) { toast(e.message); } }; }
async function api(path, body) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Studio request failed');
  return value;
}
function media(path) { return path + '?token=' + encodeURIComponent(token); }
function changed() { changeVersion++; dirty = true; $('save-status').textContent = 'Unsaved changes'; }
function current() { return draft.scenes[selected]; }
function button(text, fn, className) { const b = node('button', text, className); b.onclick = guard(fn); return b; }
function renderScenes() {
  $('scene-count').textContent = draft.scenes.length;
  $('scenes').replaceChildren();
  draft.scenes.forEach((scene, index) => {
    const b = button('', () => { selected = index; renderScenes(); editScene(); }, 'scene-item' + (index === selected ? ' active' : ''));
    b.setAttribute('aria-label', `Scene ${index + 1}: ${scene.title || 'Untitled'}`);
    b.setAttribute('aria-current', index === selected ? 'step' : 'false');
    const thumb = node('span', scene.title || 'Untitled scene', 'scene-thumb');
    if (scene.image) { const img = node('img'); img.src = media('/' + scene.image); img.alt = ''; thumb.append(img); }
    const title = node('span', undefined, 'scene-name'); title.append(node('small', String(index + 1).padStart(2, '0')), node('span', scene.title || 'Untitled scene'));
    b.append(thumb, title); $('scenes').append(b);
  });
  $('render').disabled = !draft.scenes.length || busy;
}
function previewText(id, value) {
  // Do not replace an active editable node: doing so loses its caret and undo history.
  if (document.activeElement !== $(id) && $(id).textContent !== value) $(id).textContent = value;
}
function visual() {
  const scene = current(); if (!scene) return;
  previewText('visual-number', scene.breadcrumb || `SCENE ${String(selected + 1).padStart(2, '0')}`);
  previewText('visual-title', scene.title);
  previewText('visual-card', scene.card || '');
  $('visual-note').textContent = scene.note || '';
  $('visual-note').hidden = !!scene.image;
  $('visual-image').hidden = !scene.image;
  for (const id of ['visual-number', 'visual-title', 'visual-card']) {
    $(id).setAttribute('contenteditable', scene.image ? 'false' : 'plaintext-only');
    $(id).tabIndex = scene.image ? -1 : 0;
    $(id).setAttribute('aria-disabled', String(!!scene.image));
  }
  if (scene.image) $('visual-image').src = media('/' + scene.image);
  else $('visual-image').removeAttribute('src');
  $('visual').classList.toggle('has-content-image', !!scene.content_image);
  $('visual-content-image').hidden = !scene.content_image;
  if (scene.content_image) $('visual-content-image').src = media('/' + scene.content_image);
  else $('visual-content-image').removeAttribute('src');
  $('remove-content-image').hidden = !scene.content_image;
  $('canvas-help').textContent = scene.image ? 'Full-scene image. Choose Text card to edit labels and content, or insert a new inline image.' : 'Click the breadcrumb, title or content to edit directly. Images are inserted below the text.';
  $('card-label').hidden = !!scene.image;
  const words = scene.narration.trim().split(/\s+/).filter(Boolean).length;
  $('word-count').textContent = `${words} words / ~${Math.ceil(words / (145 * draft.speed) * 60)} sec (estimate)`;
}
function editScene() {
  const scene = current(); $('empty').hidden = !!scene; $('scene-editor').hidden = !scene;
  if (!scene) return;
  $('scene-title').value = scene.title; $('card').value = scene.card || ''; $('narration').value = scene.narration; $('note').value = scene.note || '';
  $('pronunciations').value = JSON.stringify(draft.pronunciations || {}, null, 2);
  $('up').disabled = selected === 0; $('down').disabled = selected === draft.scenes.length - 1;
  visual();
}
function addScene() {
  if (draft.scenes.length >= 100) throw new Error('A tutorial can have at most 100 scenes');
  draft.scenes.push({title: `Scene ${draft.scenes.length + 1}`, narration: '', card: ''}); selected = draft.scenes.length - 1;
  changed(); renderScenes(); editScene(); $('scene-title').focus();
}
function move(direction) {
  const target = selected + direction;
  if (target < 0 || target >= draft.scenes.length) return;
  [draft.scenes[selected], draft.scenes[target]] = [draft.scenes[target], draft.scenes[selected]];
  selected = target; changed(); renderScenes(); editScene();
}
function voiceGender(voice) { return voice.gender || (voice.id[1] === 'f' ? 'Female' : 'Male'); }
function engine(voice) { return voice.engine || 'Kokoro'; }
function renderVoices() {
  const search = $('voice-search').value.toLowerCase().trim();
  const filtered = voices.filter(v => (!search || `${v.name} ${v.id} ${v.description} ${v.language}`.toLowerCase().includes(search)) && (!$('language').value || v.language === $('language').value) && (!$('locale').value || v.locale === $('locale').value) && (!$('gender').value || voiceGender(v) === $('gender').value) && (!$('engine').value || engine(v) === $('engine').value));
  $('voice-count').textContent = `${filtered.length} of ${voices.length} voices`;
  const chosen = voices.find(v => v.id === draft.voice);
  $('selected-voice').textContent = chosen ? `${chosen.name} / ${chosen.id}` : draft.voice;
  $('voices').replaceChildren();
  for (const voice of filtered) {
    const card = node('article', undefined, 'voice-card' + (voice.id === draft.voice ? ' selected' : ''));
    card.append(node('span', `${voice.id} / ${engine(voice)}`, 'voice-id'), node('h3', voice.name), node('p', voice.description));
    const controls = node('div', undefined, 'voice-buttons');
    const preview = button('Preview', () => startPreview(voice.id)); preview.dataset.previewVoice = voice.id;
    const choose = button(voice.id === draft.voice ? 'Selected' : 'Choose voice', () => { draft.voice = voice.id; changed(); renderVoices(); }, 'choose-voice');
    choose.setAttribute('aria-pressed', voice.id === draft.voice ? 'true' : 'false');
    controls.append(preview, choose); card.append(controls); $('voices').append(card);
  }
  if (!filtered.length) $('voices').append(node('p', 'No matching voices. Try resetting the filters.'));
  updatePreviewButtons();
}
function updatePreviewButtons() {
  const playing = !$('preview-audio').paused && !$('preview-audio').ended;
  for (const b of document.querySelectorAll('[data-preview-voice]')) {
    const voice = b.dataset.previewVoice;
    const stopping = playing && voice === previewVoice;
    const label = stopping ? 'Stop' : preparingVoice === voice ? 'Preparing...' : 'Preview';
    b.textContent = label;
    b.setAttribute('aria-label', `${label} ${voice}`);
    b.setAttribute('aria-pressed', String(stopping));
    b.disabled = busy && !stopping;
  }
  $('preview-scene').textContent = playing ? 'Stop preview' : 'Listen to this scene';
}
function stopPreview() {
  $('preview-audio').pause(); $('preview-audio').currentTime = 0;
  updatePreviewButtons();
}
async function save() {
  if (current()) {
    const value = JSON.parse($('pronunciations').value);
    if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Pronunciations must be a JSON object');
    draft.pronunciations = value;
  }
  if (saving) throw new Error('A save is already in progress');
  const version = changeVersion; saving = true; $('save').disabled = true;
  try {
    const result = await api('/api/save', {draft, revision}); revision = result.revision;
    dirty = version !== changeVersion;
    $('save-status').textContent = dirty ? 'Unsaved changes' : 'Draft saved'; return result;
  } finally { saving = false; $('save').disabled = false; }
}
async function startPreview(voice, text) {
  if (!text && voice === previewVoice && !$('preview-audio').paused) { stopPreview(); return; }
  if (busy) throw new Error('Wait for the current operation to finish');
  stopPreview(); preparingVoice = voice; busy = true;
  $('render').disabled = true; $('preview-scene').disabled = true; updatePreviewButtons();
  try {
    const job = await api('/api/preview', {voice, text, speed: draft.speed}); updateJob(job);
  } catch (error) {
    busy = false; preparingVoice = ''; renderScenes(); $('preview-scene').disabled = false; updatePreviewButtons(); throw error;
  }
}
function updateJob(job) {
  if (!job) return;
  busy = job.status === 'running'; $('render').disabled = busy || !draft.scenes.length; $('preview-scene').disabled = busy;
  $('job-status').textContent = `${job.kind.toUpperCase()} / ${job.status.toUpperCase()}`;
  $('job-progress').hidden = !busy;
  $('job-log').hidden = !job.progress && job.status !== 'failed';
  $('job-log').textContent = job.error || job.progress || '';
  if (job.progress) $('job-log').scrollTop = $('job-log').scrollHeight;
  if (job.id === lastJob && job.status === lastStatus) return;
  lastJob = job.id; lastStatus = job.status;
  if (!busy) preparingVoice = '';
  renderVoices();
  if (busy) { $('job-message').textContent = job.kind === 'render' ? 'Rendering a saved snapshot locally. You may keep editing; this render will not change.' : `Synthesizing ${job.voice} locally. No model downloads.`; return; }
  if (job.status === 'failed') { $('job-message').textContent = 'Operation failed. Your draft is safe. See the details above and retry when ready.'; toast('Operation failed. Check the output panel.'); return; }
  if (job.kind === 'preview') {
    previewVoice = job.voice;
    $('preview-audio').hidden = false; $('preview-audio').src = media(job.media);
    $('job-message').textContent = `Preview ready / ${job.voice}. Listen before approving a full render.`;
    $('preview-audio').play().catch(() => {});
  } else {
    $('result-video').hidden = false; $('result-video').src = media(job.media);
    const v = job.validation; $('job-message').textContent = `Render complete / ${Math.round(v.duration_seconds)} seconds / ${v.chapters} chapters / full audio-video decode ${v.full_audio_video_decode ? 'passed' : 'not verified'}. Review the finished tutorial before sharing.`;
    $('downloads').replaceChildren();
    for (const [file,label] of [['tutorial.mp4','Video'],['captions.srt','Captions'],['TRANSCRIPT.md','Transcript'],['receipt.json','Receipt'],['manifest.json','Manifest']]) {
      const link = node('a', label); link.href = media(`/media/${job.id}/${file}`); link.download = file; $('downloads').append(link);
    }
  }
}
function bindInline(id, key, limit, multiline) {
  const el = $(id);
  el.addEventListener('input', () => {
    let value = el.innerText.replace(/\r/g, '').replace(/\u00a0/g, ' ');
    if (!multiline) value = value.replace(/\n/g, ' ');
    if (value.length > limit) {
      value = value.slice(0, limit); el.textContent = value;
      const range = document.createRange(); range.selectNodeContents(el); range.collapse(false);
      const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
      toast(`This field is limited to ${limit} characters`);
    }
    if (key === 'breadcrumb' && !value.trim()) delete current().breadcrumb;
    else current()[key] = value;
    if (key === 'title') { $('scene-title').value = value; renderScenes(); }
    if (key === 'card') $('card').value = value;
    changed();
  });
  el.addEventListener('keydown', event => { if (!multiline && event.key === 'Enter') { event.preventDefault(); el.blur(); } });
  el.addEventListener('blur', visual);
  el.addEventListener('drop', event => event.preventDefault());
  el.addEventListener('paste', event => {
    // Keep pasted markup inert even in browsers without plaintext-only editing support.
    event.preventDefault();
    const selection = getSelection(); if (!selection.rangeCount) return;
    const range = selection.getRangeAt(0); if (!el.contains(range.commonAncestorContainer)) return;
    let text = event.clipboardData?.getData('text/plain') || ''; if (!multiline) text = text.replace(/[\r\n]+/g, ' ');
    range.deleteContents(); const inserted = document.createTextNode(text); range.insertNode(inserted);
    range.setStartAfter(inserted); range.collapse(true); selection.removeAllRanges(); selection.addRange(range);
    el.dispatchEvent(new Event('input', {bubbles: true}));
  });
}
async function attachImage(file, scene, background = false) {
  if (!file || file.size > 8_000_000) throw new Error('Use an image smaller than 8 MB');
  if (!draft.scenes.includes(scene)) throw new Error('The target scene was deleted; select a scene and try again');
  const reader = new FileReader();
  const encoded = await new Promise((resolve, reject) => { reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = () => reject(new Error('Could not read image')); reader.readAsDataURL(file); });
  const result = await api('/api/image', {data: encoded});
  if (!draft.scenes.includes(scene)) throw new Error('The target scene was deleted while uploading');
  if (background) { scene.image = result.image; delete scene.card; delete scene.content_image; }
  else { delete scene.image; scene.card = scene.card || ''; scene.content_image = result.image; }
  changed(); renderScenes(); editScene();
}
function discardCapture() {
  pendingCapture = undefined;
  if (captureUrl) URL.revokeObjectURL(captureUrl);
  captureUrl = undefined; $('capture-preview').removeAttribute('src');
  if ($('capture-review').open) $('capture-review').close();
}
async function captureScreen() {
  if (!navigator.mediaDevices?.getDisplayMedia) throw new Error('Screen capture is not available in this browser. Use Insert image to upload a screenshot.');
  const scene = current(); if (!scene) throw new Error('Add or select a scene first');
  let stream;
  const video = document.createElement('video'); video.muted = true; video.playsInline = true;
  $('capture-screen').disabled = true;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({video: true, audio: false});
    video.srcObject = stream; await video.play();
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('No screen frame was received. Try again.')), 5000);
      const done = () => { clearTimeout(timeout); resolve(); };
      if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(done); else setTimeout(done, 150);
    });
    if (!video.videoWidth || !video.videoHeight) throw new Error('The selected capture source has no visible frame');
    const scale = Math.min(1, 1920 / video.videoWidth, 1080 / video.videoHeight);
    const canvas = document.createElement('canvas'); canvas.width = Math.max(1, Math.round(video.videoWidth * scale)); canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    for (const track of stream.getTracks()) track.stop();
    stream = undefined;
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) throw new Error('Could not create the screenshot');
    discardCapture(); pendingCapture = {blob, scene};
    captureUrl = URL.createObjectURL(blob); $('capture-preview').src = captureUrl;
  } catch (error) {
    if (['NotAllowedError', 'AbortError'].includes(error.name)) throw new Error('Screen capture cancelled or not permitted. No scene changes were made.');
    throw error;
  } finally {
    if (stream) for (const track of stream.getTracks()) track.stop();
    video.pause(); video.srcObject = null; $('capture-screen').disabled = false;
  }
  // Review only after all screen-sharing tracks are stopped; no server write yet.
  $('capture-review').showModal();
}
async function init() {
  const state = await api('/api/state'); draft = state.draft; revision = state.revision; voices = state.voices;
  $('workspace').textContent = state.workspace; $('title').value = draft.title;
  if (![...$('speed').options].some(o => Number(o.value) === draft.speed)) { const option = node('option', String(draft.speed)); option.value = draft.speed; $('speed').append(option); }
  $('speed').value = String(draft.speed);
  for (const [id, values] of [['language',voices.map(v=>v.language)],['locale',voices.map(v=>v.locale)],['engine',voices.map(engine)]]) {
    for (const value of [...new Set(values)].sort()) { const option = node('option', value); option.value = value; $(id).append(option); }
  }
  $('save-status').textContent = 'Draft loaded'; renderScenes(); editScene(); renderVoices(); updateJob(state.job);
  $('preview-audio').addEventListener('play', () => { $('result-video').pause(); updatePreviewButtons(); });
  for (const event of ['pause', 'ended', 'error']) $('preview-audio').addEventListener(event, updatePreviewButtons);
  $('result-video').addEventListener('play', () => $('preview-audio').pause());
  $('save').onclick = guard(save);
  $('add').onclick = $('add-bottom').onclick = $('start').onclick = guard(addScene);
  $('title').oninput = () => { draft.title = $('title').value; changed(); };
  $('speed').onchange = () => { draft.speed = Number($('speed').value); changed(); visual(); };
  for (const [id,key] of [['scene-title','title'],['card','card'],['narration','narration'],['note','note']]) {
    $(id).oninput = () => { const scene = current(); scene[key] = $(id).value; if (key === 'note' && !scene[key]) delete scene.note; changed(); visual(); if (key === 'title') renderScenes(); };
  }
  $('pronunciations').onchange = guard(() => { const value = JSON.parse($('pronunciations').value); if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('Pronunciations must be a JSON object'); draft.pronunciations = value; changed(); });
  $('up').onclick = () => move(-1); $('down').onclick = () => move(1);
  $('duplicate').onclick = guard(() => { if (draft.scenes.length >= 100) throw new Error('Scene limit reached'); draft.scenes.splice(selected + 1,0,structuredClone(current())); selected++; changed(); renderScenes(); editScene(); });
  $('delete').onclick = () => { if (!confirm('Delete this scene from the draft?')) return; draft.scenes.splice(selected,1); selected = Math.max(0, Math.min(selected,draft.scenes.length-1)); changed(); renderScenes(); editScene(); };
  bindInline('visual-number', 'breadcrumb', 120, false);
  bindInline('visual-title', 'title', 180, false);
  bindInline('visual-card', 'card', 2000, true);
  $('use-card').onclick = () => { const scene = current(); delete scene.image; scene.card = scene.card || ''; changed(); renderScenes(); editScene(); };
  $('remove-content-image').onclick = () => { delete current().content_image; changed(); visual(); };
  for (const [id, background] of [['image-upload', true], ['content-image-upload', false]]) {
    $(id).onchange = guard(async () => {
      const file = $(id).files[0]; if (!file) return;
      try { await attachImage(file, current(), background); } finally { $(id).value = ''; }
    });
  }
  for (const label of document.querySelectorAll('.upload-button')) label.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); label.querySelector('input').click(); }
  });
  $('capture-screen').onclick = guard(captureScreen);
  $('capture-discard').onclick = $('capture-close').onclick = discardCapture;
  $('capture-review').addEventListener('close', discardCapture);
  $('capture-review').addEventListener('cancel', event => { if (captureInserting) event.preventDefault(); });
  $('capture-insert').onclick = guard(async () => {
    if (!pendingCapture || captureInserting) return;
    captureInserting = true;
    for (const id of ['capture-insert', 'capture-discard', 'capture-close']) $(id).disabled = true;
    try { await attachImage(pendingCapture.blob, pendingCapture.scene); discardCapture(); toast('Screenshot inserted. Save the draft to keep this scene change.'); }
    finally { captureInserting = false; for (const id of ['capture-insert', 'capture-discard', 'capture-close']) $(id).disabled = false; }
  });
  $('preview-scene').onclick = guard(() => { if (!$('preview-audio').paused) { stopPreview(); return; } if (!current().narration.trim()) throw new Error('Write some narration first'); return startPreview(draft.voice,current().narration); });
  for (const id of ['voice-search','language','locale','gender','engine']) $(id).addEventListener(id === 'voice-search' ? 'input' : 'change',renderVoices);
  $('reset-filters').onclick = () => { for (const id of ['voice-search','language','locale','gender','engine']) $(id).value=''; renderVoices(); };
  $('render').onclick = guard(async () => {
    if (!confirm(`Render with ${draft.voice}? Confirm you have listened to and approved this voice. This creates a new local video; it does not publish anything.`)) return;
    await save(); const job = await api('/api/render',{revision}); updateJob(job); $('job-message').scrollIntoView({behavior:'smooth',block:'center'});
  });
  async function poll() { try { if (busy) { const next = await api('/api/state'); updateJob(next.job); } } catch (e) { toast(e.message); } finally { setTimeout(poll,1200); } }
  poll();
}
window.addEventListener('beforeunload',event => { if (dirty) { event.preventDefault(); event.returnValue=''; } });
guard(init)();
