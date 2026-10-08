import {loadPyodide} from './test-runtime/node_modules/pyodide/pyodide.mjs';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const keepAlive=setInterval(()=>{},1000);
try {
const root=fileURLToPath(new URL('./dist/',import.meta.url));
const py=await loadPyodide({indexURL:fileURLToPath(new URL('./test-runtime/node_modules/pyodide/',import.meta.url)),packageBaseUrl:'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/',stdout:console.log});
const lock=JSON.parse(fs.readFileSync(new URL('./test-runtime/node_modules/pyodide/pyodide-lock.json',import.meta.url)));
for(const packageName of ['scipy','pandas']){
  const entry=lock.packages[packageName];
  const cached=new URL('./test-runtime/node_modules/pyodide/'+entry.file_name,import.meta.url);
  if(fs.existsSync(cached)){
    if(createHash('sha256').update(fs.readFileSync(cached)).digest('hex')!==entry.sha256)throw Error('Cached '+packageName+' checksum mismatch');
    await py.loadPackage(entry.depends,{checkIntegrity:true});
    await py.loadPackage(fileURLToPath(cached));
  }
}
await py.loadPackage(['numpy','pandas','scikit-learn','matplotlib','joblib','threadpoolctl'],{checkIntegrity:true});
py.FS.mkdirTree('/app/amr_discovery');
for(const [name,text] of Object.entries(JSON.parse(fs.readFileSync(root+'python-sources.json','utf8'))))py.FS.writeFile('/app/'+name,text);
py.runPython('import sys\nsys.path.insert(0,"/app")\nfrom browser_bridge import execute');
async function execute(p){py.globals.set('payload_json',JSON.stringify(p));return JSON.parse(await py.runPythonAsync('execute(__import__("json").loads(payload_json))'));}
const demoCsv=fs.readFileSync(root+'data/demo.csv','utf8');
let prepared=await execute({action:'prepare',csv:demoCsv,base_csv:demoCsv});
if(prepared.manifest.exact_duplicate_rows_removed!==prepared.manifest.rows||prepared.manifest.status!=='PREPARED_NOT_AUDITED')throw Error('Batch deduplication contract failed');
console.log('BATCH_PREPARE_RUNTIME_OK');
const configuration=fs.readFileSync(root+'configs/demo.json','utf8');
let r=await execute({action:'train',configuration,csv:fs.readFileSync(root+'data/demo.csv','utf8')});
if(!r.metrics)throw Error('Demo blocked '+r.blocked);
console.log('TRAIN_OK',JSON.stringify(r.metrics));
fs.writeFileSync(new URL('./test-runtime/browser-demo.zip',import.meta.url),Buffer.from(r.archive,'base64'));
r=await execute({action:'predict',species:'Klebsiella pneumoniae',values:{cefepime:{value:16,operator:'>='},ceftazidime:{value:8,operator:'='},ciprofloxacin:{value:4,operator:'='}}});
if(!Number.isFinite(r.probability))throw Error('Prediction is not finite');console.log('PREDICT_OK',JSON.stringify(r));
const id=py.runPython('__import__("browser_bridge").LAST_TRAIN_IDS.copy().pop()');
r=await execute({action:'topology',genes:`isolate_id,gene,status,evidence_reference\n${id},NDM,positive,test_fixture\n${id},OXA48,unknown,test_fixture\n`});
if(r.genes.edges!==1||r.genes.preview[0].jointly_observed!==0)throw Error('Unknown gene call incorrectly included');console.log('TOPOLOGY_OK');
r=await execute({action:'train',configuration:fs.readFileSync(root+'configs/public_pilot.json','utf8'),csv:fs.readFileSync(root+'data/india.csv','utf8')});
if(!r.blocked||r.audit.eligible_isolates!==1)throw Error('India gate failed');console.log('INDIA_BLOCK_OK',r.blocked);
r=await execute({action:'train',configuration:fs.readFileSync(root+'configs/public_source_holdout.json','utf8'),csv:fs.readFileSync(root+'data/public.csv','utf8')});
if(!r.metrics||r.metrics.n!==165||!r.metrics.all_eligible_isolates_used||r.metrics.fn+r.metrics.tp!==29)throw Error('Public source integrity failure: '+JSON.stringify(r.metrics||r.blocked));
console.log('PUBLIC_SOURCE_RUNTIME_OK',JSON.stringify({n:r.metrics.n,auroc:r.metrics.auroc,sensitivity:r.metrics.sensitivity,fn:r.metrics.fn}));
fs.writeFileSync(new URL('./test-runtime/browser-public-source.zip',import.meta.url),Buffer.from(r.archive,'base64'));
r=await execute({action:'validate',configuration:fs.readFileSync(root+'configs/public_pilot.json','utf8'),csv:fs.readFileSync(root+'data/india.csv','utf8')});
if(!r.suite||!r.suite.experiments.every(x=>x.status==='blocked'))throw Error('Validation suite must retain blocked experiments');
const catConfig=fs.readFileSync(root+'configs/india_categorical.json','utf8');
const catCsv=fs.readFileSync(root+'data/india_categorical.csv','utf8');
r=await execute({action:'audit',configuration:catConfig,csv:catCsv});
if(r.audit.raw_isolates!==266||r.audit.eligible_isolates!==213||r.audit.representation!=='categorical_ast')throw Error('Full categorical India audit mismatch');
r=await execute({action:'validate',configuration:catConfig,csv:catCsv});
if(r.suite.experiments.filter(x=>x.kind==='region').length!==2||!r.suite.experiments.every(x=>x.status==='blocked'))throw Error('Categorical regional validation gates failed');
if(r.audit.comparability.missing_provenance_rows.lab_id!==1862)throw Error('Lab audit missed undocumented Indian labs');
const strict=JSON.parse(catConfig);Object.assign(strict,{comparability_policy:'strict',standard:'EUCAST',standard_version:'documented-version-required',allow_unversioned_reported:false});
r=await execute({action:'audit',configuration:JSON.stringify(strict),csv:catCsv});
if(r.audit.raw_isolates!==266||r.audit.eligible_isolates!==0||r.audit.comparability.policy!=='strict')throw Error('Strict provenance gate failed');
console.log('INDIA_CATEGORICAL_FULL_AUDIT_OK');
console.log('STRICT_LAB_PROVENANCE_OK');
const frameworkConfig=JSON.parse(fs.readFileSync(root+'configs/framework_browser.json','utf8'));
frameworkConfig.bootstrap_repeats=10;
r=await execute({action:'train',configuration:JSON.stringify(frameworkConfig),csv:fs.readFileSync(root+'data/public.csv','utf8')});
if(!r.metrics||!r.selection||r.selection.fit_partition!=='training_only'||!r.metrics.selected_model.startsWith('forest_'))throw Error('Broad MIC framework failed: '+JSON.stringify(r.blocked||r.metrics));
if(r.metrics.selected_drugs.includes(frameworkConfig.target)||!r.importance.length)throw Error('Target leakage or absent importance');
fs.writeFileSync(new URL('./test-runtime/browser-framework-v09.zip',import.meta.url),Buffer.from(r.archive,'base64'));
console.log('FRAMEWORK_BROWSER_OK',JSON.stringify({n:r.metrics.n,model:r.metrics.selected_model,panel:r.metrics.selected_drugs,sensitivity:r.metrics.sensitivity,specificity:r.metrics.specificity}));
console.log('BROWSER_RUNTIME_TESTS_PASSED');

} catch(e) { console.error('RUNTIME_TEST_FAILED',e.message);process.exitCode=1; } finally {clearInterval(keepAlive);}
