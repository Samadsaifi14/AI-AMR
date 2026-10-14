import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {unzipSync, strFromU8} from 'fflate';

const root = fileURLToPath(new URL('../',import.meta.url));
const dist = path.join(root,'dist');
const html = fs.readFileSync(path.join(dist,'index.html'),'utf8');
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(ids.length,new Set(ids).size,'Duplicate element IDs');
for (const match of html.matchAll(/\b(?:src|href)="([^"]+)"/g)) {
  const ref=match[1];
  if (!ref.startsWith('#') && !/^[a-z]+:/i.test(ref)) {
    assert(fs.existsSync(path.join(dist,ref.split('#')[0])), 'Missing local asset: '+ref);
  }
}
const app=fs.readFileSync(path.join(dist,'app.js'),'utf8');
for(const m of app.matchAll(/\$\(['"]([a-z][a-z0-9-]*)['"]\)/g))assert(ids.includes(m[1]),'Missing UI control: '+m[1]);
assert(html.includes('framework-mode')&&app.includes('framework_browser.json'),'Framework preset inaccessible');
const sources=JSON.parse(fs.readFileSync(path.join(dist,'python-sources.json'),'utf8'));
const archive=unzipSync(fs.readFileSync(path.join(dist,'AMR_Discovery_Source.zip')));
for(const [name,content] of Object.entries(sources)) {
  assert.equal(content,fs.readFileSync(path.join(root,name),'utf8'),'Stale Python source: '+name);
  assert.equal(strFromU8(archive[name]),content,'Stale source download: '+name);
}
assert(archive['results/public_pilot/audit.json'],'Source download missing materialization hash');
for(const page of ['guide.html','resources.html']){const document=fs.readFileSync(path.join(dist,page),'utf8');for(const m of document.matchAll(/\b(?:src|href)="([^"]+)"/g)){const ref=m[1];if(!ref.startsWith('#')&&!/^[a-z]+:/i.test(ref))assert(fs.existsSync(path.join(dist,ref.split('#')[0])),'Missing guide asset: '+ref);}}
for (const name of ['app.js','worker.js','onboarding.js']) {
  execFileSync(process.execPath,['--check',path.join(dist,name)]);
}
console.log('PASS: generated modules, asset links, unique IDs and JavaScript syntax.');
