import { test } from 'node:test';
import assert from 'node:assert/strict';
import { invocation, voiceCatalog, voiceIds, mutating } from '../pi/requests.mjs';

test('Pi accepts all voices from the shared CLI catalog', () => {
  assert.equal(voiceIds.length,23);
  assert.equal(new Set(voiceIds).size,23);
  assert.equal(new Set(voiceCatalog.map(v=>v.locale)).size,7);
  for(const voice of voiceIds) assert.ok(invocation('preview',{output:'/tmp/sample.wav',voice},'/tmp').includes(voice));
});

test('gallery uses a literal output path and participates in mutation approval', () => {
  assert.ok(mutating.has('gallery'));
  assert.deepEqual(invocation('gallery',{output:'voice samples'},'/tmp'),['-m','tutorial_studio.cli','gallery','--output','/tmp/voice samples']);
});
