import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const root = fileURLToPath(new URL('../',import.meta.url));
const dist = path.join(root,'dist');
const html = fs.readFileSync(path.join(dist,'index.html'),'utf8');
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(ids.length,new Set(ids).size,'Duplicate element IDs');
for (const match of html.matchAll(/\b(?:src|href)="([^"]+)"/g)) {
  const ref=match[1];
  if (!ref.startsWith('#') && !ref.startsWith('https:')) {
    assert(fs.existsSync(path.join(dist,ref)), 'Missing local asset: '+ref);
  }
}
const sources=JSON.parse(fs.readFileSync(path.join(dist,'python-sources.json'),'utf8'));
for(const [name,content] of Object.entries(sources)) {
  assert.equal(content,fs.readFileSync(path.join(root,name),'utf8'),'Stale Python source: '+name);
}
for (const name of ['app.js','worker.js']) {
  execFileSync(process.execPath,['--check',path.join(dist,name)]);
}
console.log('PASS: generated modules, asset links, unique IDs and JavaScript syntax.');
