import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { chromium } from 'playwright';
import { studioLauncher } from '../pi/studio-process.mjs';
import { invocation, actions, mutating } from '../pi/requests.mjs';

const root = path.resolve(import.meta.dirname, '..');
const executable = process.env.TUTORIAL_CHROMIUM_EXECUTABLE;

test('studio invocation uses explicit workspace, optional import and no shell', () => {
  assert.ok(actions.includes('studio') && mutating.has('studio'));
  assert.deepEqual(invocation('studio', {output:'./workspace',manifest:'./manifest.json'},'/tmp'), ['-m','tutorial_studio.cli','studio','--workspace','/tmp/workspace','--no-browser','--manifest','/tmp/manifest.json']);
  assert.throws(() => invocation('studio', {},'/tmp'));
});

test('browser editor saves, previews Heart, renders, and works on mobile', {skip:!executable,timeout:180000}, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(),'tutorial-editor-'));
  const launcher = studioLauncher(path.join(root,'.venv/bin/python'),root);
  let browser;
  try {
    const ready = await launcher.start(invocation('studio',{output:directory},root));
    assert.equal((await launcher.start(invocation('studio',{output:directory},root))).studio_url,ready.studio_url);
    browser = await chromium.launch({executablePath:executable,headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror',error=>errors.push(error.message));
    page.on('dialog',dialog=>dialog.accept());
    await page.goto(ready.studio_url);
    await page.locator('#save-status').filter({hasText:'Draft loaded'}).waitFor();
    assert.equal(await page.locator('#scene-count').textContent(),'0');
    await page.locator('#start').click();
    await page.locator('#title').fill('Browser acceptance tutorial');
    await page.locator('#scene-title').fill('A real browser edit');
    await page.locator('#card').fill('Write. Preview. Render.');
    await page.locator('#narration').fill('Welcome to Tutorial Studio. This is a real local render.');
    await page.locator('#save').click();
    await page.locator('#save-status').filter({hasText:'Draft saved'}).waitFor();
    await page.reload();
    await page.locator('#save-status').filter({hasText:'Draft loaded'}).waitFor();
    assert.equal(await page.locator('#narration').inputValue(),'Welcome to Tutorial Studio. This is a real local render.');
    await page.locator('#duplicate').click();
    assert.equal(await page.locator('#scene-count').textContent(),'2');
    await page.locator('#up').click();
    await page.locator('#delete').click();
    assert.equal(await page.locator('#scene-count').textContent(),'1');
    const image = await page.locator('#visual').screenshot();
    await page.locator('#image-upload').setInputFiles({name:'scene.png',mimeType:'image/png',buffer:image});
    await page.locator('#visual-image:not([hidden])').waitFor();
    await page.locator('#voice-search').fill('af_heart');
    assert.equal(await page.locator('.voice-card').count(),1);
    await page.getByRole('button',{name:'Preview af_heart',exact:true}).click();
    await page.locator('#preview-audio:not([hidden])').waitFor({timeout:90000});
    assert.ok(await page.locator('#preview-audio').evaluate(el=>el.src.includes('preview.wav')));
    await page.locator('#render').click();
    await page.locator('#result-video:not([hidden])').waitFor({timeout:90000});
    await page.locator('#job-message').filter({hasText:'full audio-video decode passed'}).waitFor();
    assert.equal(await page.locator('#downloads a').count(),5);
    const receiptUrl=await page.locator('#downloads a').filter({hasText:'Receipt'}).getAttribute('href');
    const receipt=await (await page.request.get(new URL(receiptUrl,ready.studio_url).href)).json();
    assert.equal(receipt.status,'complete'); assert.equal(receipt.voice,'af_heart');
    assert.equal(receipt.validation.full_audio_video_decode,true);
    assert.equal(receipt.scenes.length,1);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.locator('#scene-title').fill('<script>window.bad=true</script>');
    assert.equal(await page.evaluate(()=>window.bad),undefined);
    await page.locator('#save').click();
    await page.locator('#save-status').filter({hasText:'Draft saved'}).waitFor();
    assert.deepEqual(errors,[]);
    assert.ok((await fs.stat(path.join(directory,'draft.json'))).size>0);
  } finally {
    if(browser) await browser.close();
    await launcher.stop();
    await fs.rm(directory,{recursive:true,force:true});
  }
});
