import {loadPyodide} from '../test-runtime/node_modules/pyodide/pyodide.mjs';
import {fileURLToPath} from 'node:url';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
const keepAlive=setInterval(()=>{},1000);
try {
const root=fileURLToPath(new URL('../dist/',import.meta.url));
const py=await loadPyodide({indexURL:fileURLToPath(new URL('../test-runtime/node_modules/pyodide/',import.meta.url)),packageBaseUrl:'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/',stdout:console.log});
const lock=JSON.parse(fs.readFileSync(new URL('../test-runtime/node_modules/pyodide/pyodide-lock.json',import.meta.url)));
for(const packageName of ['scipy','pandas']){
  const entry=lock.packages[packageName];
  const cached=new URL('../test-runtime/node_modules/pyodide/'+entry.file_name,import.meta.url);
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
let r;
const frameworkConfig=JSON.parse(fs.readFileSync(root+'configs/framework_browser.json','utf8'));
frameworkConfig.bootstrap_repeats=10;
r=await execute({action:'train',configuration:JSON.stringify(frameworkConfig),csv:fs.readFileSync(root+'data/public.csv','utf8')});
if(!r.metrics||!r.selection||r.selection.fit_partition!=='training_only'||!r.metrics.selected_model.startsWith('forest_'))throw Error('Broad MIC framework failed: '+JSON.stringify(r.blocked||r.metrics));
if(r.metrics.selected_drugs.includes(frameworkConfig.target)||!r.importance.length)throw Error('Target leakage or absent importance');
fs.writeFileSync(new URL('../test-runtime/browser-framework-v09.zip',import.meta.url),Buffer.from(r.archive,'base64'));
console.log('FRAMEWORK_BROWSER_OK',JSON.stringify({n:r.metrics.n,model:r.metrics.selected_model,panel:r.metrics.selected_drugs,sensitivity:r.metrics.sensitivity,specificity:r.metrics.specificity}));

r=await execute({action:'predict',species:'Klebsiella pneumoniae',values:{cefepime:{value:16,operator:'='},ceftazidime:{value:8,operator:'='},ciprofloxacin:{value:4,operator:'='}}});
if(!r.decision.startsWith('research_'))throw Error('Dynamic research prediction still globally gated');
console.log('DYNAMIC_RESEARCH_PREDICTION_OK',JSON.stringify(r));
console.log('FRAMEWORK_RUNTIME_TESTS_PASSED');
} catch(e) { console.error('RUNTIME_TEST_FAILED',e.message);process.exitCode=1; } finally {clearInterval(keepAlive);}
