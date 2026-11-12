import { test } from 'node:test';
import assert from 'node:assert/strict';
import { invocation } from '../pi/requests.mjs';
import { localOrigin, validatePlan } from '../browser/capture.mjs';

test('extension builds literal argv, never shell interpolation', () => {
  const args = invocation('render', {manifest: 'my project/a;$(touch no).json', output: 'my output'}, '/tmp');
  assert.deepEqual(args, ['-m','tutorial_studio.cli','render','/tmp/my project/a;$(touch no).json','--output','/tmp/my output']);
});
test('unknown actions and missing paths fail', () => {
  assert.throws(() => invocation('exec', {}, '/tmp'));
  assert.throws(() => invocation('render', {}, '/tmp'));
  assert.throws(() => invocation('preview', {output:'/tmp/a.wav', voice:'unknown'}, '/tmp'));
});
test('read-only actions have no mutation flags', () => {
  assert.deepEqual(invocation('doctor', {}, '/tmp'), ['-m','tutorial_studio.cli','doctor']);
});
test('capture approval flag is only selected for capture', () => {
  assert.ok(invocation('capture',{manifest:'p.json', output:'images'},'/tmp').includes('--approve-browser'));
});
test('remote and credential-bearing capture URLs fail closed', () => {
  for (const url of ['https://example.com','http://localhost:7337','http://user:secret@127.0.0.1','file:///etc/passwd']) assert.throws(() => localOrigin(url));
  assert.equal(localOrigin('http://127.0.0.1:7337'), 'http://127.0.0.1:7337');
});
test('capture allows a bounded inert local plan', () => {
  assert.equal(validatePlan({schema_version:1,url:'http://127.0.0.1:7337',steps:[{action:'screenshot',name:'start.png'}]}), 'http://127.0.0.1:7337');
});
test('capture rejects execution, traversal, duplicate files and missing fill data', () => {
  for (const steps of [
    [{action:'evaluate',value:'process.exit()'}],
    [{action:'screenshot',name:'../secret.png'}],
    [{action:'screenshot',name:'same.png'},{action:'screenshot',name:'same.png'}],
    [{action:'fill',selector:'input'},{action:'screenshot',name:'a.png'}],
  ]) assert.throws(() => validatePlan({schema_version:1,url:'http://127.0.0.1:7337',steps}));
});
