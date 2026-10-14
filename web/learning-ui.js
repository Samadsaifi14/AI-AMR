'use strict';
(() => {
  const el=id=>document.getElementById(id);
  const key='amr-research-versions-v1';
  let versions=[],drift=null,storageAvailable=true;
  try {const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))versions=saved.filter(v=>v.schema===1&&typeof v.version_id==='string').slice(-20);}
  catch {storageAvailable=false;}
  function history(){el('learning-history').textContent=versions.length?versions.map(v=>`${v.version_id} · ${v.target} · ${v.selected_model} · ${v.metrics.n} evaluated · ${v.release.status}`).join('\n'):'No saved research versions.';if(!storageAvailable)el('learning-history').textContent+=' Browser storage unavailable; download your evidence.';}
  document.addEventListener('amr:state',({detail:s})=>{el('import-export').disabled=s.busy||el('dataset').value!=='upload';el('check-drift').disabled=s.busy||!s.modelReady;el('monitor-file').disabled=s.busy;el('drift-download').disabled=s.busy||!drift;if(!s.modelReady){drift=null;el('learning-version').textContent='No active session version. Train the current source and settings; saved history is separate.';el('drift-download').disabled=true;el('drift-result').textContent='Train a session version before monitoring incoming data.';}});
  document.addEventListener('amr:version',({detail:v})=>{el('learning-version').textContent=`Version ${v.version_id}. ${v.release.status}. Gates needing evidence: ${v.release.failed_gates.join(', ')}. Clinical validation: not established.`;versions=versions.filter(x=>x.version_id!==v.version_id);versions.push(v);versions=versions.slice(-20);try{localStorage.setItem(key,JSON.stringify(versions));}catch{storageAvailable=false;}history();});
  document.addEventListener('amr:drift',({detail:r})=>{drift=r;el('drift-result').textContent=`${r.status}. ${r.incoming_n} eligible incoming isolates. ${r.interpretation}`;el('drift-result').insertAdjacentHTML('beforeend',table(r.features));el('drift-download').disabled=false;});
  el('import-export').onclick=()=>launch('import_export');
  el('check-drift').onclick=()=>launch('drift');
  el('history-download').onclick=()=>download(JSON.stringify(versions,null,2),'amr-version-history.json','application/json',false);
  el('drift-download').onclick=()=>download(JSON.stringify(drift,null,2),'amr-drift-report.json','application/json',false);
  history();
})();
