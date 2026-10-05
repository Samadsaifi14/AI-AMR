import fs from 'node:fs/promises';
import path from 'node:path';
import {gunzipSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const out = path.join(root, 'dist');
await fs.rm(out, {recursive:true, force:true});
await fs.cp(path.join(root,'web'), out, {recursive:true});
await fs.mkdir(path.join(out,'data'), {recursive:true});
await fs.mkdir(path.join(out,'configs'), {recursive:true});

const sources = {};
for (const name of (await fs.readdir(path.join(root,'amr_discovery'))).sort()) {
  if (name.endsWith('.py')) {
    sources['amr_discovery/'+name] = await fs.readFile(path.join(root,'amr_discovery',name),'utf8');
  }
}
sources['browser_bridge.py'] = await fs.readFile(path.join(root,'browser_bridge.py'),'utf8');
await fs.writeFile(path.join(out,'python-sources.json'), JSON.stringify(sources));

const files = {
  'data/demo.csv':'data/fixtures/browser_demo.csv',
  'data/india.csv':'data/raw/ncbi_india/observations.csv',
  'data_dictionary.md':'docs/DATA_DICTIONARY.md',
  'audit_v03.md':'docs/AUDIT_V03.md',
  'india_validation_v04.md':'docs/INDIA_VALIDATION_V04.md',
  'india_external_result_v04.json':'docs/INDIA_EXTERNAL_RESULT_V04.json',
  'implementation_plan.md':'docs/ORIGINAL_IMPLEMENTATION_PLAN.md',
  'AMR_Discovery_Source.zip':'downloads/AMR_Discovery_Source.zip'
};
for (const [destination,source] of Object.entries(files)) {
  await fs.copyFile(path.join(root,source),path.join(out,destination));
}
await fs.writeFile(path.join(out,'data/public.csv'),gunzipSync(await fs.readFile(path.join(root,'data/raw/ncbi_kp_human/observations.csv.gz'))));
for (const name of ['demo','public_pilot','public_source_holdout']) {
  await fs.copyFile(path.join(root,'configs',name+'.json'),path.join(out,'configs',name+'.json'));
}
console.log('Built static app from canonical Python modules and source-derived data.');
