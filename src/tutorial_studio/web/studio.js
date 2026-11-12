'use strict';
const $ = id => document.getElementById(id);
const fragment = new URLSearchParams(location.hash.slice(1));
let token = fragment.get('token') || sessionStorage.getItem('tutorial-studio-token') || '';
if (token) sessionStorage.setItem('tutorial-studio-token', token);
history.replaceState(null, '', location.pathname);
let draft, revision, voices = [], selected = 0, dirty = false, busy = false, lastJob = '', lastStatus = '', changeVersion = 0;
let saving = false;
let toastTimer;
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
function visual() {
  const scene = current(); if (!scene) return;
  $('visual-number').textContent = String(selected + 1).padStart(2, '0');
  $('visual-title').textContent = scene.title;
  $('visual-card').textContent = scene.card || '';
  $('visual-note').textContent = scene.note || '';
  $('visual-image').hidden = !scene.image;
  if (scene.image) $('visual-image').src = media('/' + scene.image);
  else $('visual-image').removeAttribute('src');
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
    const preview = button('▶ Preview', () => startPreview(voice.id)); preview.disabled = busy; preview.setAttribute('aria-label', `Preview ${voice.id}`);
    const choose = button(voice.id === draft.voice ? 'Selected' : 'Choose voice', () => { draft.voice = voice.id; changed(); renderVoices(); }, 'choose-voice');
    choose.setAttribute('aria-pressed', voice.id === draft.voice ? 'true' : 'false');
    controls.append(preview, choose); card.append(controls); $('voices').append(card);
  }
  if (!filtered.length) $('voices').append(node('p', 'No matching voices. Try resetting the filters.'));
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
  if (busy) throw new Error('Wait for the current operation to finish');
  const job = await api('/api/preview', {voice, text, speed: draft.speed}); updateJob(job);
  $('job-message').scrollIntoView({behavior:'smooth', block:'nearest'});
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
  lastJob = job.id; lastStatus = job.status; renderVoices();
  if (busy) { $('job-message').textContent = job.kind === 'render' ? 'Rendering a saved snapshot locally. You may keep editing; this render will not change.' : `Synthesizing ${job.voice} locally. No model downloads.`; return; }
  if (job.status === 'failed') { $('job-message').textContent = 'Operation failed. Your draft is safe. See the details above and retry when ready.'; toast('Operation failed. Check the output panel.'); return; }
  if (job.kind === 'preview') {
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
async function init() {
  const state = await api('/api/state'); draft = state.draft; revision = state.revision; voices = state.voices;
  $('workspace').textContent = state.workspace; $('title').value = draft.title;
  if (![...$('speed').options].some(o => Number(o.value) === draft.speed)) { const option = node('option', String(draft.speed)); option.value = draft.speed; $('speed').append(option); }
  $('speed').value = String(draft.speed);
  for (const [id, values] of [['language',voices.map(v=>v.language)],['locale',voices.map(v=>v.locale)],['engine',voices.map(engine)]]) {
    for (const value of [...new Set(values)].sort()) { const option = node('option', value); option.value = value; $(id).append(option); }
  }
  $('save-status').textContent = 'Draft loaded'; renderScenes(); editScene(); renderVoices(); updateJob(state.job);
  $('preview-audio').addEventListener('play', () => $('result-video').pause());
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
  $('use-card').onclick = () => { const scene = current(); delete scene.image; scene.card = scene.card || ''; changed(); renderScenes(); editScene(); };
  $('image-upload').onchange = guard(async () => {
    const file = $('image-upload').files[0]; if (!file) return; if (file.size > 8_000_000) throw new Error('Use an image smaller than 8 MB');
    const scene = current(); const reader = new FileReader(); const encoded = await new Promise((resolve,reject) => { reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file); });
    const result = await api('/api/image',{data:encoded}); scene.image = result.image; delete scene.card; changed(); renderScenes(); editScene(); $('image-upload').value = '';
  });
  $('preview-scene').onclick = guard(() => { if (!current().narration.trim()) throw new Error('Write some narration first'); return startPreview(draft.voice,current().narration); });
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
