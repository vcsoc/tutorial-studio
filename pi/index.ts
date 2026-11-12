import type { ExtensionAPI, ExtensionContext } from '@earendil-works/pi-coding-agent';
import { truncateHead, withFileMutationQueue } from '@earendil-works/pi-coding-agent';
import { Type } from 'typebox';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { actions, invocation, mutating, voiceIds, voiceCatalog } from './requests.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = join(root, '.venv', 'bin', 'python');
const voiceSchema = Type.Union(voiceIds.map((id: string) => Type.Literal(id)));

export default function tutorialStudio(pi: ExtensionAPI) {
  async function run(action: string, options: { manifest?: string; output?: string; voice?: string }, ctx: ExtensionContext, signal?: AbortSignal) {
    if (signal?.aborted) throw new Error('Tutorial operation cancelled');
    const args = invocation(action, options, ctx.cwd);
    if (mutating.has(action)) {
      if (!ctx.hasUI) throw new Error('Mutation requires interactive approval. Use the CLI directly in noninteractive automation.');
      const note = action === 'capture'
        ? 'This opens an isolated browser against an already-running loopback app. Reviewed clicks/fills can change app state. No app is started. Secret inputs are masked, but screenshots can still contain private content.'
        : action === 'gallery'
          ? 'This generates local voice samples and updates voice-preview.html in the chosen directory. Existing audio is retained and existing gallery HTML is backed up. No downloads or full tutorial render.'
          : 'This creates local files and may run local neural inference and FFmpeg. No cloud narration, project execution, implicit model download or existing-output overwrite.';
      const ok = await ctx.ui.confirm(`Tutorial Studio: ${action}`, `${note}\n\nInput: ${options.manifest ?? '(built-in voice preview)'}\nOutput: ${options.output ?? options.manifest}\nVoice: ${options.voice ?? 'manifest/default Emma'}`);
      if (!ok) throw new Error('Tutorial operation was not approved');
    }
    if (ctx.hasUI) ctx.ui.setStatus('tutorial-studio', `Tutorial: ${action}`);
    const execute = async () => {
      const result = await pi.exec(python, args, { cwd: root, signal, timeout: action === 'render' ? 3_600_000 : 300_000, maxBuffer: 2 * 1024 * 1024 });
      if (result.code !== 0 || result.killed || result.truncated) {
        throw new Error(truncateHead(result.stderr || result.stdout || 'Tutorial process failed or was cancelled', { maxBytes: 8000, maxLines: 100 }).content);
      }
      const text = truncateHead(result.stdout, { maxBytes: 12_000, maxLines: 200 });
      return text.content + (text.truncated ? '\n[Output truncated. Full render receipts are in the chosen output directory.]' : '');
    };
    try {
      if (mutating.has(action)) {
        const target = resolve(ctx.cwd, options.output ?? options.manifest!);
        return await withFileMutationQueue(target, execute);
      }
      return await execute();
    } finally {
      if (ctx.hasUI) ctx.ui.setStatus('tutorial-studio', undefined);
    }
  }

  pi.registerTool({
    name: 'tutorial_studio',
    label: 'Tutorial Studio',
    description: 'Local tutorial framework: doctor, voices, validate, init, neural voice preview, video render or approved loopback browser capture. Mutations require an interactive confirmation. No cloud TTS or implicit downloads. Use-only in consumer projects: do not edit the Tutorial Studio framework or extension. Output capped at 12 KB / 200 lines.',
    promptSnippet: 'Create and validate reusable local narrated tutorial videos',
    promptGuidelines: [
      'Use tutorial_studio when the user requests a tutorial video or voice preview. Read the framework README before authoring a manifest.',
      `When using tutorial_studio for another project, treat the Tutorial Studio installation at ${root} and its extension/loader registrations as read-only infrastructure. Do not edit, delete, move, patch, upgrade, commit or push its source, documentation, progress logs, tests, configuration, dependencies, model assets or extension files. A tutorial-production request is not permission to maintain the framework.`,
      'Keep tutorial_studio manifests, screenshots, scripts, drafts, previews, render outputs, receipts and project-specific progress notes in the consuming project or a user-approved external workspace, never in the Tutorial Studio checkout. Normal cache writes performed by the framework itself are allowed; do not manually modify framework internals.',
      'If tutorial_studio fails or lacks a feature, report the issue and ask for maintenance in the Tutorial Studio project instead of patching the installed framework or extension from a consumer session.',
      `Only edit tutorial_studio itself when the user explicitly requests framework/extension maintenance while working directly in the Tutorial Studio project at ${root}. Merely reading its files or running commands from its installation directory does not grant maintenance permission.`,

      'tutorial_studio manifests are inert data: do not execute target project code just to explain it, and never publish or capture private data without authorization.',
      'Use tutorial_studio preview and obtain voice approval before a full narration render. Do not claim screenshots are a continuous screen recording.',
    ],
    executionMode: 'sequential',
    parameters: Type.Object({
      action: Type.Union(actions.map((action: string) => Type.Literal(action))),
      manifest: Type.Optional(Type.String({ description: 'Manifest path; for capture, the reviewed capture plan' })),
      output: Type.Optional(Type.String({ description: 'Fresh output directory, or a new .wav path for preview' })),
      voice: Type.Optional(voiceSchema),
    }),
    async execute(_id, params, signal, onUpdate, ctx) {
      onUpdate?.({ content: [{ type: 'text', text: `Tutorial Studio: ${params.action}` }], details: {} });
      const text = await run(params.action, params, ctx, signal);
      return { content: [{ type: 'text', text }], details: { action: params.action, output: params.output } };
    },
  });

  pi.registerCommand('tutorial', {
    description: 'Local neural tutorial studio: doctor | voices | init PATH | validate PATH | preview | gallery | render PATH | capture PATH',
    getArgumentCompletions(prefix) {
      const values = actions.filter((action: string) => action.startsWith(prefix));
      return values.length ? values.map((value: string) => ({ value, label: value })) : null;
    },
    handler: async (args, ctx) => {
      try {
        const trimmed = args.trim();
        let action = trimmed.split(/\s+/, 1)[0];
        if (!action) {
          if (!ctx.hasUI) throw new Error('Specify a tutorial action');
          action = (await ctx.ui.select('Tutorial Studio', actions)) ?? '';
          if (!action) return;
        }
        if (!actions.includes(action)) throw new Error('Use doctor, voices, init, validate, preview, gallery, render or capture');
        const options: { manifest?: string; output?: string; voice?: string } = {};
        if (['init', 'validate', 'render', 'capture'].includes(action)) {
          let value = trimmed.slice(action.length).trim().replace(/^"(.*)"$/, '$1');
          if (!value && ctx.hasUI) value = (await ctx.ui.input('Manifest / capture-plan path')) ?? '';
          if (!value) return;
          options.manifest = value;
        }
        if (['preview', 'gallery', 'render', 'capture'].includes(action)) {
          if (!ctx.hasUI) throw new Error('Rendering, preview, gallery and capture require interactive mode');
          if (action === 'preview') {
            const labels = voiceCatalog.map((voice: { id: string; name: string; description: string }) => `${voice.name} / ${voice.description} / ${voice.id}`);
            const selected = await ctx.ui.select('Neural narrator (international voices use their own language)', labels);
            if (!selected) return;
            options.voice = voiceIds[labels.indexOf(selected)];
          }
          const suggested = join(process.env.HOME ?? ctx.cwd, 'Movies', `Tutorial-${Date.now()}${action === 'preview' ? '.wav' : ''}`);
          const answer = await ctx.ui.input('New output path (empty = suggested path)', suggested);
          if (answer === undefined) return;
          options.output = answer.trim() || suggested;
        }
        const text = await run(action, options, ctx);
        pi.sendMessage({ customType: 'tutorial-studio', content: text, display: true });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (ctx.hasUI) ctx.ui.notify(message, 'error');
        else throw error;
      }
    },
  });
}
