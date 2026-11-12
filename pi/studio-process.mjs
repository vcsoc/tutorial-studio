import { spawn } from 'node:child_process';

// One session-owned server. The Python server shuts down its render worker on SIGTERM.
export function studioLauncher(python, cwd) {
  let child;
  let launching;
  let current;
  let key;
  async function stop() {
    const active = child;
    child = undefined; current = undefined; key = undefined;
    if (!active || active.exitCode !== null || active.signalCode !== null) return;
    await new Promise(resolve => {
      const timer = setTimeout(() => { active.kill('SIGKILL'); }, 12000);
      active.once('exit', () => { clearTimeout(timer); resolve(); });
      active.kill('SIGTERM');
    });
  }
  async function start(args) {
    if (launching) throw new Error('Studio is already starting');
    const nextKey = JSON.stringify(args);
    if (child && child.exitCode === null && child.signalCode === null && key === nextKey && current) return current;
    launching = true;
    try {
      await stop();
      current = await new Promise((resolve, reject) => {
        const active = spawn(python, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
        child = active; key = nextKey;
        let out = '', err = '', settled = false;
        const timer = setTimeout(() => fail(new Error('Studio did not start within 15 seconds')), 15000);
        const fail = error => { if (settled) return; settled = true; clearTimeout(timer); active.kill('SIGTERM'); reject(error); };
        active.on('error', fail);
        active.stderr.on('data', chunk => { err = (err + chunk.toString()).slice(-8000); });
        active.stdout.on('data', chunk => {
          if (settled) return;
          out += chunk.toString();
          if (out.length > 12000) return fail(new Error('Invalid studio startup response'));
          if (!out.includes('\n')) return;
          try {
            const value = JSON.parse(out.split('\n')[0]);
            const url = new URL(value.studio_url);
            if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.hash.startsWith('#token=')) throw new Error('Invalid local studio URL');
            settled = true; clearTimeout(timer); resolve(value);
          } catch (error) { fail(error); }
        });
        active.once('exit', () => { if (!settled) fail(new Error(err || 'Studio exited before startup')); });
      });
      return current;
    } finally { launching = false; }
  }
  return { start, stop };
}
