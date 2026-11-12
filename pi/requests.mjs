import path from 'node:path';
import { readFileSync } from 'node:fs';

export const voiceCatalog = JSON.parse(readFileSync(new URL('../src/tutorial_studio/voices.json', import.meta.url), 'utf8'));

export const actions = ['doctor', 'voices', 'validate', 'init', 'preview', 'gallery', 'render', 'capture'];
export const mutating = new Set(['init', 'preview', 'gallery', 'render', 'capture']);
export const voiceIds = voiceCatalog.map(voice => voice.id);
const voices = new Set(voiceIds);

export function invocation(action, options, cwd) {
  if (!actions.includes(action)) throw new Error('Unknown tutorial action');
  const args = ['-m', 'tutorial_studio.cli', action];
  const absolute = value => {
    if (typeof value !== 'string' || !value.trim() || value.includes('\0')) throw new Error('An explicit nonempty path is required');
    return path.resolve(cwd, value.startsWith('@') ? value.slice(1) : value);
  };
  if (['validate', 'init', 'render', 'capture'].includes(action)) args.push(absolute(options.manifest));
  if (['preview', 'gallery', 'render', 'capture'].includes(action)) args.push('--output', absolute(options.output));
  if (['preview', 'render'].includes(action) && options.voice) {
    if (!voices.has(options.voice)) throw new Error('Unknown voice');
    args.push('--voice', options.voice);
  }
  if (action === 'capture') args.push('--approve-browser');
  return args;
}
