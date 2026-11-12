import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { capture } from '../browser/capture.mjs';

const executable = process.env.TUTORIAL_CHROMIUM_EXECUTABLE;
test('actual local browser capture uses real app state and refuses existing output', { skip: !executable, timeout: 30000 }, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'tutorial-browser-'));
  const server = http.createServer((_request, response) => {
    response.setHeader('Content-Type', 'text/html');
    response.end('<!doctype html><title>Local tutorial demo</title><input type="password" id="token"><button onclick="document.querySelector(\'h1\').textContent=\'Connected locally\'">Connect</button><h1>Welcome</h1>');
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const output = path.join(directory, 'screens');
  process.env.TUTORIAL_TEST_SECRET = 'synthetic-noncredential-test-value';
  const plan = {schema_version:1,url:`http://127.0.0.1:${server.address().port}`,steps:[
    {action:'fill',selector:'#token',env:'TUTORIAL_TEST_SECRET'},
    {action:'click',selector:'button'},
    {action:'wait',selector:'h1:text-is("Connected locally")'},
    {action:'screenshot',name:'connected.png'},
  ]};
  const file = path.join(directory, 'plan.json');
  await fs.writeFile(file, JSON.stringify(plan));
  try {
    const result = await capture(file, output);
    assert.equal(result.status, 'complete');
    assert.ok((await fs.stat(path.join(output, 'connected.png'))).size > 1000);
    assert.equal(result.secret_inputs_masked, true);
    await assert.rejects(() => capture(file, output));
  } finally {
    delete process.env.TUTORIAL_TEST_SECRET;
    await new Promise(r => server.close(r));
    await fs.rm(directory, {recursive:true, force:true});
  }
});

test('actual browser refuses off-origin application fetches', { skip: !executable, timeout: 30000 }, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'tutorial-browser-block-'));
  let externalRequests = 0;
  const outside = http.createServer((_req, res) => { externalRequests++; res.end('unexpected'); });
  await new Promise(r => outside.listen(0, '127.0.0.1', r));
  const server = http.createServer((_req, res) => {
    res.setHeader('Content-Type','text/html');
    res.end(`<script>fetch('http://127.0.0.1:${outside.address().port}/blocked').catch(()=>{document.body.dataset.blocked='yes'})</script>`);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const file = path.join(directory,'plan.json');
  await fs.writeFile(file,JSON.stringify({schema_version:1,url:`http://127.0.0.1:${server.address().port}`,steps:[{action:'wait',selector:'body[data-blocked="yes"]'},{action:'screenshot',name:'blocked.png'}]}));
  try {
    await assert.rejects(() => capture(file,path.join(directory,'output')), /off-origin/);
    assert.equal(externalRequests,0);
  } finally {
    await new Promise(r => server.close(r)); await new Promise(r => outside.close(r));
    await fs.rm(directory,{recursive:true,force:true});
  }
});
