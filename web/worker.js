/* Pinned Python runtime; uploaded observations never leave this worker. */
const INDEX = 'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/';
let runtime;
async function initialize() {
  if (runtime) return runtime;
  postMessage({type:'progress',message:'Loading the Python runtime and scientific packages. First launch downloads about 100 MB; keep this tab open.'});
  importScripts(INDEX+'pyodide.js');
  runtime = await loadPyodide({indexURL:INDEX,stdout:message=>postMessage({type:'progress',message})});
  await runtime.loadPackage(['numpy','pandas','scikit-learn','matplotlib','joblib','threadpoolctl']);
  const response=await fetch('python-sources.json');
  if(!response.ok) throw new Error('Cannot load application Python source.');
  const sources=await response.json();
  runtime.FS.mkdirTree('/app/amr_discovery');
  for (const [name,source] of Object.entries(sources)) runtime.FS.writeFile('/app/'+name,source);
  runtime.runPython('import sys\nsys.path.insert(0,"/app")\nfrom browser_bridge import execute');
  return runtime;
}
onmessage = async ({data}) => {
  try {
    const py=await initialize();
    py.globals.set('payload_json',JSON.stringify(data));
    const result=await py.runPythonAsync('execute(__import__("json").loads(payload_json))');
    postMessage({type:'result',result:JSON.parse(result)});
  } catch(error) {
    runtime=undefined;
    postMessage({type:'error',message:String(error)});
  }
};
