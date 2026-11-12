import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

export function localOrigin(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', '[::1]'].includes(url.hostname) || url.username || url.password) {
    throw new Error('Only explicit numeric loopback HTTP origins without URL credentials are allowed');
  }
  return url.origin;
}

export function validatePlan(plan) {
  if (!plan || plan.schema_version !== 1 || typeof plan.url !== 'string') throw new Error('Expected capture schema_version 1 and url');
  const origin = localOrigin(plan.url);
  if (new URL(plan.url).search || new URL(plan.url).hash) throw new Error('Initial URL must not contain query credentials or fragments');
  if (!Array.isArray(plan.steps) || !plan.steps.length || plan.steps.length > 200) throw new Error('Expected 1..200 capture steps');
  const names = new Set();
  for (const step of plan.steps) {
    if (!['click', 'fill', 'press', 'wait', 'screenshot', 'scroll'].includes(step.action)) throw new Error('Unsupported capture action');
    if (step.action === 'screenshot') {
      if (typeof step.name !== 'string' || !/^[a-zA-Z0-9_-]{1,80}\.png$/.test(step.name) || names.has(step.name)) throw new Error('Screenshot names must be unique plain PNG filenames');
      names.add(step.name);
    } else if (typeof step.selector !== 'string' || !step.selector || step.selector.length > 500) throw new Error('Action requires a bounded locator selector');
    if (step.action === 'fill' && ((typeof step.value === 'string') === (typeof step.env === 'string'))) throw new Error('Fill requires exactly one value or secret environment variable');
    if (step.env && !/^[A-Z][A-Z0-9_]{0,100}$/.test(step.env)) throw new Error('Invalid environment variable name');
    if (typeof step.value === 'string' && step.value.length > 5000) throw new Error('Fill value too long');
    if (step.action === 'press' && (typeof step.key !== 'string' || step.key.length > 80)) throw new Error('Press requires a bounded key');
  }
  if (names.size === 0) throw new Error('Capture plan must include a screenshot');
  if (plan.mask !== undefined && (!Array.isArray(plan.mask) || plan.mask.length > 50 || plan.mask.some(x => typeof x !== 'string' || x.length > 500))) throw new Error('Invalid screenshot masks');
  return origin;
}

export async function capture(planPath, output) {
  if ((await fs.stat(planPath)).size > 1_000_000) throw new Error('Capture plan exceeds 1 MB');
  const plan = JSON.parse(await fs.readFile(planPath, 'utf8'));
  const origin = validatePlan(plan);
  // Do not silently provision a browser, start an application or load a user profile.
  const executablePath = process.env.TUTORIAL_CHROMIUM_EXECUTABLE;
  if (!executablePath || !path.isAbsolute(executablePath)) throw new Error('Set TUTORIAL_CHROMIUM_EXECUTABLE to an already installed, trusted browser');
  await fs.mkdir(output, { recursive: false, mode: 0o700 });
  const browser = await chromium.launch({ headless: true, executablePath });
  const cancel = () => { void browser.close().finally(() => process.exit(130)); };
  process.once('SIGTERM', cancel); process.once('SIGINT', cancel);
  const images = [], blocked = new Set(), secretSelectors = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, serviceWorkers: 'block', acceptDownloads: false });
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin === origin) return route.continue();
      blocked.add(url.origin);
      return route.abort('blockedbyclient');
    });
    await context.routeWebSocket('**/*', route => route.close());
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    await page.goto(plan.url, { waitUntil: 'domcontentloaded' });
    for (const step of plan.steps) {
      const locator = step.selector ? page.locator(step.selector) : null;
      switch (step.action) {
        case 'click': await locator.click(); break;
        case 'fill': {
          const value = step.env ? process.env[step.env] : step.value;
          if (value === undefined) throw new Error('Required secret environment variable is not set');
          if (step.env) secretSelectors.push(step.selector);
          await locator.fill(value);
          break;
        }
        case 'press': await locator.press(step.key); break;
        case 'wait': await locator.waitFor({ state: 'visible' }); break;
        case 'scroll': await locator.scrollIntoViewIfNeeded(); break;
        case 'screenshot': {
          if (blocked.size) throw new Error('App attempted off-origin traffic; capture refused');
          await page.screenshot({ path: path.join(output, step.name), animations: 'disabled', mask: ['input[type="password"]', ...(plan.mask ?? []), ...secretSelectors].map(s => page.locator(s)) });
          images.push(step.name); break;
        }
      }
    }
    if (blocked.size) throw new Error('App attempted off-origin traffic; capture refused');
    const receipt = { status: 'complete', capture_style: 'actual browser stills', origin, images, secret_inputs_masked: true, app_process_started: false };
    await fs.writeFile(path.join(output, 'capture-receipt.json'), JSON.stringify(receipt, null, 2));
    return receipt;
  } finally {
    process.removeListener('SIGTERM', cancel); process.removeListener('SIGINT', cancel);
    await browser.close();
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  capture(process.argv[2], process.argv[3]).then(v => console.log(JSON.stringify(v))).catch(() => {
    // Playwright diagnostics can contain filled secrets: retain only a generic failure.
    console.error('Capture failed. Check the local app, reviewed plan, installed browser and off-origin requests. Secrets are not logged.');
    process.exitCode = 1;
  });
}
