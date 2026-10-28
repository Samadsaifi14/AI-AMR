'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const importer=window.ASTImport;
  let pendingFile=null, pendingSource=null, activeMapping=null;
  const DEFAULT_PREDICTORS=['amoxicillin-clavulanate','cefotaxime','cefepime','ceftriaxone','ciprofloxacin','gentamicin','piperacillin-tazobactam'];
  const RESERVED_TARGETS=['meropenem','imipenem','colistin','ceftazidime-avibactam'];
  const FIELD_LABELS={isolate_id:'Isolate identifier',source_id:'Study / batch source',species:'Species',patient_id:'Patient code',duplicate_group:'Duplicate group',country:'Country',collection_date:'Collection date',host:'Host',specimen:'Specimen',drug:'Antibiotic',measurement:'Measured MIC',operator:'MIC sign (≤, =, ≥)',units:'MIC units',method:'Test method',platform:'Instrument / platform',standard:'Interpretation standard',standard_version:'Standard version',reported_sir:'Reported category (S / I / R / SDD)',evidence_class:'Measurement source type',region:'Region',hospital_id:'Hospital code',lab_id:'Laboratory code',panel_id:'Test panel',tested_concentrations:'Tested concentrations',qc_reference:'Quality-control reference'};
  const LONG_FIELDS=Object.keys(FIELD_LABELS);
  const WIDE_FIELDS=['isolate_id','source_id','species','patient_id','duplicate_group','country','collection_date','host','specimen','method','platform','standard','standard_version','units','evidence_class','region','hospital_id','lab_id','panel_id','qc_reference'];
  const display=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function table(rows,columns){if(!rows?.length)return '<p class="hint">No preview rows to show.</p>';const keys=columns||Object.keys(rows[0]);return '<div class="table-scroll"><table><thead><tr>'+keys.map(key=>'<th>'+display(key)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+keys.map(key=>'<td>'+display(row[key]??'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  function sir(value){const v=String(value??'').trim().toLowerCase();if(['r','resistant'].includes(v))return 'R';if(['s','susceptible','sensitive'].includes(v))return 'S';if(['i','intermediate','susceptible, increased exposure'].includes(v))return 'I';if(['sdd','susceptible dose dependent'].includes(v))return 'SDD';return '';}
  function setRecipeVisibility(){const kind=$('dataset').value;$('recipe-panel').hidden=kind==='demo';}
  function availableDrugs(csv){if(!csv)return[];const rows=importer.parseCSV(csv);if(rows.length<2)return[];const headers=rows[0].map(x=>String(x).trim()),di=headers.indexOf('drug');if(di<0)return[];return [...new Set(rows.slice(1).map(row=>{const raw=String(row[di]||'').trim();return importer.matchDrug(raw)||raw.toLowerCase();}).filter(Boolean))].sort();}
  function normalizedCounts(csv){
    if(!csv) return [];
    const rows=importer.parseCSV(csv);if(rows.length<2)return [];
    const headers=rows[0].map(x=>String(x).trim());const indexes=Object.fromEntries(headers.map((name,i)=>[name,i]));
    if(!['isolate_id','drug'].every(k=>indexes[k]!=null))return [];
    const seen=new Map();
    for(const row of rows.slice(1)){
      const id=String(row[indexes.isolate_id]||'').trim(),rawDrug=String(row[indexes.drug]||'').trim(),drug=importer.matchDrug(rawDrug)||rawDrug.toLowerCase(),label=sir(row[indexes.reported_sir]);
      if(!id||!drug||!label)continue;
      const key=drug+'\u0000'+id;if(!seen.has(key))seen.set(key,new Set());seen.get(key).add(label);
    }
    const counts=new Map();
    for(const [key,labels] of seen){if(labels.size!==1)continue;const [drug]=key.split('\u0000');if(!counts.has(drug))counts.set(drug,{drug,R:0,S:0,I:0,SDD:0});const item=counts.get(drug);item[[...labels][0]]++;}
    return [...counts.values()].sort((a,b)=>a.drug.localeCompare(b.drug));
  }
  function renderTargets(counts,csvAvailable=true){
    const select=$('target-drug'),prior=select.value||(()=>{try{return JSON.parse($('configuration').value).target;}catch{return '';}})();
    select.replaceChildren();
    if(!counts.length){const option=document.createElement('option');option.value=prior||'';option.textContent=csvAvailable?'No target counts found in this file':'Select “Check target counts” to load measured examples';select.append(option);select.disabled=true;$('target-counts').textContent=csvAvailable?(document.getElementById('representation').value==='mic'?'MIC values alone do not identify resistant or susceptible labels without a reviewed breakpoint file. No category is inferred.':'No usable S/R target labels were detected. The full check may still explain the file.'):'Target counts have not been loaded yet. This step reads the selected source on this device.';return;}
    select.disabled=false;
    const targetOptions=RESERVED_TARGETS.map(drug=>counts.find(item=>item.drug===drug)||{drug,R:0,S:0,I:0});
    for(const item of targetOptions){const option=document.createElement('option');option.value=item.drug;const enough=item.R>=5&&item.S>=5;const total=item.R+item.S+item.I;option.disabled=!enough;option.textContent=`${item.drug} — ${total?`${item.R} resistant / ${item.S} susceptible${item.I?` / ${item.I} intermediate`:''}`:'no measured labels'}${enough?'':' · too few for the minimum held-out class count'}`;select.append(option);}
    if(prior&&!targetOptions.some(x=>x.drug===prior)){const option=document.createElement('option');option.value=prior;option.disabled=true;option.textContent=`${prior} — not in the reserved-target panel`;select.append(option);}
    const selected=select.querySelector(`option[value="${CSS.escape(prior)}"]`);
    if(selected)select.value=prior;else {const available=[...select.options].find(x=>!x.disabled);if(available)select.value=available.value;}
    showTargetCount();
  }
  function showTargetCount(){
    const target=$('target-drug').value;const item=window.__targetCounts?.find(x=>x.drug===target);
    if(!item){$('target-counts').textContent='Counts are preliminary and are checked again after exclusions. No measurements are inferred.';return;}
    $('target-counts').textContent=`Preliminary file count for ${target}: ${item.R} resistant and ${item.S} susceptible${item.I?`, ${item.I} intermediate`:''}. Results may be excluded during the full data check. The software holdout requires at least 5 test examples in each class; grouped splits may need more.`;
  }
  async function refreshCounts(){
    const kind=$('dataset').value;
    try{
      let csv='';
      if(kind==='upload')csv=window.__uploadState?.normalizedCsv||window.__restoredCsv||'';
      else csv=await asset('data/'+kind+'.csv');
      window.__targetCounts=normalizedCounts(csv);renderTargets(window.__targetCounts,true);
      const available=window.__targetCounts.map(x=>x.drug).filter(Boolean);
      if(kind==='upload'&&available.length){const cfg=JSON.parse($('configuration').value);cfg.features=DEFAULT_PREDICTORS.filter(d=>available.includes(d)&&d!==cfg.target);if(cfg.features.length)cfg.min_observed_features=Math.min(Number(cfg.min_observed_features||3),cfg.features.length);$('configuration').value=JSON.stringify(cfg,null,2);syncDesign();}
    }catch(error){status('Could not read target counts from the selected file. '+error.message,true);}
  }
  function selectOptions(headers,current){return `<option value="">Do not use / leave unknown</option><option value="__constant" ${current==='__constant'?'selected':''}>Use one value entered for all rows</option>`+headers.map(h=>`<option value="${display(h)}" ${current===h?'selected':''}>Column: ${display(h)}</option>`).join('');}
  function renderFieldControls(){
    const format=$('import-format').value,type=$('import-value-type').value;
    const fields=format==='long'?LONG_FIELDS:WIDE_FIELDS;
    const visible=fields.filter(field=>format!=='long'||type==='mic'?!['reported_sir'].includes(field):!['measurement','operator','units'].includes(field));
    $('mapping-fields').innerHTML='<h4>Match the file columns</h4><p class="hint">Required: isolate ID, source ID and species. If a value is the same for every row, enter it from the source record. Leave unrecorded fields blank.</p><div class="mapping-grid">'+visible.map(field=>{
      const fallback=field==='reported_sir'&&type==='reported_sir'?pendingSource.suggestions.measurement:field==='measurement'&&type==='mic'?pendingSource.suggestions.reported_sir:'';const suggested=pendingSource.suggestions[field]||fallback||'';const val=activeMapping?.fields?.[field]??suggested;const isConstant=val==='__constant';const constantValue=activeMapping?.constants?.[field]||'';
      return `<div class="mapping-control"><label for="map-${field}">${FIELD_LABELS[field]||field}</label><select id="map-${field}" data-field="${field}">${selectOptions(pendingSource.headers,val)}</select><input id="constant-${field}" data-constant="${field}" aria-label="Recorded value for all rows: ${FIELD_LABELS[field]||field}" placeholder="Enter the documented value" value="${display(constantValue)}" ${isConstant?'':'hidden'}></div>`;
    }).join('')+'</div>';
    for(const select of $('mapping-fields').querySelectorAll('select[data-field]'))select.addEventListener('change',()=>{const input=$(`constant-${select.dataset.field}`);input.hidden=select.value!=='__constant';updateChangeLog();});
    for(const input of $('mapping-fields').querySelectorAll('input[data-constant]'))input.addEventListener('input',updateChangeLog);
    renderDrugControls();updateChangeLog();
  }
  function renderDrugControls(){
    const format=$('import-format').value;if(format!=='wide'){$('mapping-drugs').innerHTML='';return;}
    const headers=pendingSource.headers;
    $('mapping-drugs').innerHTML='<h4>Which columns contain antibiotics?</h4><p class="hint">Keep only the columns that are antibiotic results. When a file has both a phenotype and MIC column for the same drug, keep both: they are combined into one isolate–drug observation.</p><div class="mapping-grid">'+headers.map((header,index)=>{
      const guess=pendingSource.drugColumns.find(x=>x.column===header)?.drug||'';const value=activeMapping?.drugColumns?.[header]??guess;
      return `<div class="mapping-control"><label for="drug-map-${index}">${display(header)}</label><select id="drug-map-${index}" data-drug-column="${display(header)}"><option value="">Do not use this column</option>${importer.DRUGS.map(drug=>`<option value="${drug}" ${drug===value?'selected':''}>${drug}</option>`).join('')}</select></div>`;
    }).join('')+'</div>';
    for(const select of $('mapping-drugs').querySelectorAll('[data-drug-column]'))select.addEventListener('change',updateChangeLog);
  }
  function collectMapping(){
    const format=$('import-format').value,type=$('import-value-type').value,fields={},constants={};
    for(const select of $('mapping-fields').querySelectorAll('select[data-field]')){
      const field=select.dataset.field;if(select.value==='__constant'){const value=$(`constant-${field}`).value.trim();if(value)constants[field]=value;}else if(select.value)fields[field]=select.value;
    }
    const drugMap={};for(const select of $('mapping-drugs').querySelectorAll('[data-drug-column]'))if(select.value){const column=select.dataset.drugColumn,detected=pendingSource.drugColumns.find(item=>item.column===column),drug=select.value;const entry=drugMap[drug]||{drug};const kind=detected?.resultKind||(type==='mic'?'measurement':'reported_sir');if(kind==='measurement'){entry.measurementColumn=column;entry.measurementUnits=detected?.units||'';}else if(kind==='reported_sir')entry.phenotypeColumn=column;else entry.column=column;drugMap[drug]=entry;}
    if(format==='wide'){
      const units=constants.units||'';
      return {format,valueType:type,fields,constants,drugs:Object.values(drugMap),units,evidenceClass:$('import-evidence').value,filename:pendingFile.name};
    }
    if(type==='reported_sir'&&!fields.reported_sir&&fields.measurement){fields.reported_sir=fields.measurement;delete fields.measurement;delete fields.operator;}
    if(type==='mic'&&!fields.measurement&&fields.reported_sir){fields.measurement=fields.reported_sir;delete fields.reported_sir;}
    return {format,valueType:type,fields,constants,drugs:[],evidenceClass:$('import-evidence').value,filename:pendingFile.name};
  }
  function updateChangeLog(){
    if(!pendingSource)return;
    try{
      const mapping=collectMapping();
      if(mapping.format==='wide'&&mapping.drugs.length===0){$('mapping-change-log').innerHTML='<p class="hint">Choose at least one antibiotic column. You can reject a suggestion by selecting “Do not use this column.”</p>';return;}
      const result=importer.buildLong({...pendingSource,format:mapping.format},mapping);
      const entries=result.log.map(item=>`<li>${display(item.item)}</li>`).join('')||'<li>No column mapping is selected yet.</li>';
      $('mapping-change-log').innerHTML=`<h4>Visible change log</h4><p class="hint">${pendingSource.records.length} source rows will be reshaped into ${result.preview.length-1} preview rows. The original file is unchanged; blank measurements remain blank.</p><ul>${entries}</ul>`;
      $('mapping-preview').innerHTML='<h4>Prepared preview</h4>'+table(result.preview.slice(0,8),importer.FIELDS);
    }catch(error){$('mapping-change-log').innerHTML=`<p class="hint">Mapping preview: ${display(error.message)}</p>`;$('mapping-preview').innerHTML='';}
  }
  function inferType(source){
    const sirColumn=source.suggestions.reported_sir||'';const column=source.format==='wide'?source.drugColumns[0]?.column:sirColumn||source.suggestions.measurement;
    if(!column)return 'reported_sir';const values=source.records.map(row=>sir(row[column])).filter(Boolean);return values.length&&values.length>=Math.min(5,source.records.length*.5)?'reported_sir':'mic';
  }
  function openMapping(file,source){
    pendingFile=file;pendingSource=source;activeMapping=null;
    $('import-review').hidden=false;$('import-format').value=source.format==='uncertain'?'long':source.format;
    $('import-value-type').value=inferType(source);$('import-evidence').value='';
    $('import-detection').textContent=`Detected ${source.format==='uncertain'?'an unclear layout':source.format+' format'} with ${source.headers.length} columns and ${source.records.length} data rows. The first worksheet is used for Excel files. Check each suggested mapping before proceeding.`;
    if(file.name.toLowerCase().endsWith('.xlsx'))$('import-detection').textContent+=' If Excel date fields appear as numbers, save that column as ISO dates in a CSV first; original workbook values are preserved.';
    renderFieldControls();
    $('recipe-panel').hidden=false;
    $('import-review').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  async function readUpload(file){
    if(!file)return;if(file.size>10*1024*1024){status('Files must be 10 MB or smaller in the browser. Use the local Python importer for larger files.',true);return;}
    try{
      let rows;
      if(file.name.toLowerCase().endsWith('.xlsx'))rows=importer.parseWorkbook(await file.arrayBuffer());
      else if(file.name.toLowerCase().endsWith('.csv'))rows=importer.parseCSV(await file.text());
      else throw new Error('Choose a .csv or .xlsx file.');
      const source=importer.inspect(rows);window.__uploadState={file,fileName:file.name,source,normalizedCsv:'',mapping:null};window.__restoredCsv='';preparedCsv=null;invalidateSession();document.dispatchEvent(new CustomEvent('amr:upload-selected'));openMapping(file,source);status('File opened locally. Review and confirm the column mapping; no values have been changed.');
    }catch(error){status('Could not read this file. '+error.message,true);}
  }
  function confirmImport(){
    try{
      if(!pendingFile||!pendingSource)throw new Error('Choose a CSV or Excel file first.');
      const mapping=collectMapping();const required=['isolate_id','source_id','species'];
      for(const field of required)if(!mapping.fields[field]&&!mapping.constants[field])throw new Error(`Map ${FIELD_LABELS[field]} to a column or enter the documented value shared by all rows.`);
      if(mapping.format==='wide'&&!mapping.drugs.length)throw new Error('Select at least one antibiotic column.');
      if(mapping.format==='long'&&!mapping.fields.drug&&!mapping.constants.drug)throw new Error('Map the antibiotic-name column.');
      if(mapping.valueType==='mic'){
        if(mapping.format==='long'&&!mapping.fields.measurement&&!mapping.fields.reported_sir)throw new Error('Map the MIC measurement column.');
        if(mapping.format==='wide'&&!mapping.fields.units&&!mapping.constants.units)throw new Error('Map the units column or enter the recorded MIC units, such as mg/L.');
        if(mapping.format==='long'&&!mapping.fields.units&&!mapping.constants.units)throw new Error('Map the units column or enter the recorded MIC units, such as mg/L.');
      }else if(mapping.format==='long'&&!mapping.fields.reported_sir&&!mapping.fields.measurement)throw new Error('Map the reported result column.');
      if(!mapping.fields.evidence_class&&!mapping.constants.evidence_class&&!['measured_authorized','measured_public'].includes(mapping.evidenceClass))throw new Error('Choose whether these are authorized laboratory measurements or documented public measurements.');
      const result=importer.buildLong({...pendingSource,format:mapping.format},mapping);
      window.__restoredCsv=result.csv;window.__uploadState={file:pendingFile,fileName:pendingFile.name,source:pendingSource,normalizedCsv:result.csv,mapping};preparedCsv=null;
      const cfg=JSON.parse($('configuration').value);cfg.representation=mapping.valueType==='mic'?'mic':'categorical_ast';cfg.label_mode='reported';cfg.task='antibiotic_resistance';cfg.features=DEFAULT_PREDICTORS.filter(d=>availableDrugs(result.csv).includes(d)&&d!==cfg.target);cfg.min_observed_features=3;cfg.split={mode:'exploratory_70_30'};cfg.comparability_policy='exploratory';cfg.allow_unversioned_reported=true;cfg.species=['Escherichia coli','Klebsiella pneumoniae','Klebsiella pneumoniae subsp. pneumoniae'];cfg.include_species=true;$('configuration').value=JSON.stringify(cfg,null,2);syncDesign();
      $('import-detection').textContent=`Mapping accepted. ${pendingSource.records.length} source rows were prepared without changing the original ${pendingFile.name}. Missing values remain missing; no MIC values or resistance labels were inferred.`;
      $('mapping-change-log').innerHTML='<h4>Accepted change log</h4><p>Source file preserved. The mapping shown below was accepted for this analysis copy.</p>'+table(result.log.map(x=>({mapping:x.item,status:'Accepted'})),['mapping','status']);
      $('mapping-fields').hidden=true;$('mapping-drugs').hidden=true;$('mapping-preview').innerHTML='<h4>Prepared preview</h4>'+table(result.preview.slice(0,8),importer.FIELDS);$('confirm-import').hidden=true;$('cancel-import').textContent='Choose a different file';
      window.__targetCounts=normalizedCounts(result.csv);renderTargets(window.__targetCounts,true);updateRecipeConfig();document.dispatchEvent(new CustomEvent('amr:upload-ready'));status('Data is ready for its check. Select “Check my data” to review exclusions and missing source details.');
    }catch(error){status(error.message,true);}
  }
  function updateRecipeConfig(){
    const target=$('target-drug').value;if(!target)return;
    try{const cfg=JSON.parse($('configuration').value);cfg.target=target;const available=window.__uploadState?.normalizedCsv?availableDrugs(window.__uploadState.normalizedCsv):cfg.features;cfg.features=DEFAULT_PREDICTORS.filter(d=>available.includes(d)&&d!==target&&!d.startsWith(target+'-')&&!target.startsWith(d+'-'));$('configuration').value=JSON.stringify(cfg,null,2);syncDesign();}catch(error){status('Could not update this recipe. '+error.message,true);}
  }
  function applyRecipeGoal(){
    try{const cfg=JSON.parse($('configuration').value);const goal=document.querySelector('input[name="recipe-goal"]:checked')?.value||'catch';cfg.sensitivity_target=goal==='catch'?(cfg.sensitivity_target??.95):.80;cfg.selection_objective='specificity_at_sensitivity';$('configuration').value=JSON.stringify(cfg,null,2);sync();}catch(error){status(error.message,true);}
  }
  function auditState(r){
    const audit=r.audit;if(!audit)return;
    const state=$('data-check-state');state.hidden=false;const exclusions=Object.entries(audit.excluded_event_counts||{});const provenance=Object.entries(audit.comparability?.missing_provenance_rows||{});const nEligible=Number(audit.eligible_isolates||0);let label='Ready',why='No structural exclusions were reported. Read the source and laboratory details before training.';
    if(r.blocked||nEligible===0){label='Cannot run';why=r.blocked||'No eligible isolates were available for this analysis.';}
    else if(audit.raw_isolates>nEligible||exclusions.length||provenance.some(([,n])=>Number(n)>0)){label='Needs attention';why='Some records were excluded or have missing source details. Review the items below; the original file has not been changed.';}
    const issueRows=[...exclusions.map(([reason,count])=>({item:`Excluded: ${reason.replaceAll('_',' ')}`,rows:count,action:'These records remain out of this analysis unless the source file is corrected and checked again.'})),...provenance.filter(([,count])=>Number(count)>0).map(([field,count])=>({item:`Missing recorded detail: ${field.replaceAll('_',' ')}`,rows:count,action:'The value remains unknown. Add it only from the original laboratory record.'}))];
    state.className='data-state '+label.toLowerCase().replaceAll(' ','-');state.innerHTML=`<div><p class="eyebrow">CHECK MY DATA</p><h3>${label}</h3><p>${display(why)}</p><p>${nEligible} eligible of ${Number(audit.raw_isolates||0)} isolates · ${Number(audit.raw_rows||0)} observations.</p>${issueRows.length?`<details open><summary>Review ${issueRows.length} data issue${issueRows.length===1?'':'s'}</summary><ul>${issueRows.map(item=>`<li><strong>${display(item.item)} (${display(item.rows)})</strong> — ${display(item.action)} <label class="review-issue"><input type="checkbox"> Mark reviewed</label></li>`).join('')}</ul></details>`:'<p>No corrections were proposed. No source value was altered.</p>'}<button type="button" class="data-state-action">${label==='Ready'?'Continue to training':'Review the details below'}</button></div>`;
    state.querySelector('.data-state-action').addEventListener('click',()=>{(r.action==='train'?'#metrics':'#run-summary')&&document.querySelector(r.action==='train'?'#metrics':'#run-summary').scrollIntoView({behavior:'smooth'});});
  }
  function trustAndLayers(r){
    if(!r.metrics){$('trust-badge').hidden=true;$('verdict-card').hidden=true;return;}
    const m=r.metrics,release=r.learning_version?.release||m.release;const independent=m.independently_verified_external_validation===true&&m.holdout_operating_target_met===true&&release?.independent_evaluation===true;
    const reliable=m.holdout_operating_target_met===true&&!r.blocked;const badge=$('trust-badge');badge.hidden=false;badge.className='trust-badge '+(independent?'independent':reliable?'promising':'not-reliable');
    badge.innerHTML=`<strong>${independent?'Passed on independent data':reliable?'Promising, internal only':'Not reliable yet'}</strong><p>${independent?'The independent-data gates are recorded as passed for this experiment.':reliable?'Configured internal test targets passed; no independent external check is attached.':'A configured test target was missed or the model was blocked. Review the failed gate and class counts below.'}</p>`;
    const verdict=$('verdict-card');verdict.hidden=false;
    verdict.innerHTML=`<p class="eyebrow">RESULT AT A GLANCE</p><h3>${m.resistant==null?'Not enough data for a verdict':`Caught ${display(m.tp)} of ${display(m.resistant)} resistant test isolates`}</h3><p>${m.resistant==null?display(r.blocked||'The run did not provide resistant test counts.'):`Missed resistance: ${display(m.fn)}. False alarms among ${display(m.nonresistant)} non-resistant test isolates: ${display(m.fp)}.`}</p><p class="hint">${m.fn==null||m.fp==null?'Some error counts are unavailable because the required test class was missing.':'A missed resistant isolate was not flagged. A false alarm was a non-resistant isolate the model flagged.'} Research estimate only; the badge describes the evidence level, not clinical suitability.</p>`;
    const metrics=$('metrics');const labels=['Ranking (AUROC)','Resistant cases caught','Non-resistant cases correctly left unflagged','Probability error (Brier score)'];metrics.querySelectorAll('.metric').forEach((node,index)=>{const title=node.querySelector('small'),value=node.querySelector('strong');if(title&&labels[index])title.textContent=labels[index];if(value&&[1,2].includes(index)&&value.textContent!=='—'&&!value.textContent.includes('%'))value.textContent=(Number(value.textContent)*100).toFixed(1)+'%';});
    if(!r.audit.synthetic){const original=metrics.querySelector('.demo-explainer');original?.remove();}
    const children=[...metrics.children];const grid=metrics.querySelector('.metrics-grid');const demo=metrics.querySelector('.demo-explainer');if(grid&&!metrics.querySelector('.full-detail')){const notice=grid.nextElementSibling?.classList.contains('notice')?grid.nextElementSibling:null;const detail=document.createElement('details');detail.className='full-detail';detail.innerHTML='<summary>Full detail: test counts, uncertainty and model information</summary>';for(const child of children)if(child!==grid&&child!==notice&&child!==demo)detail.append(child);metrics.append(detail);}
  }
  document.getElementById('observations').addEventListener('change',event=>readUpload(event.target.files[0]));
  document.addEventListener('amr:resume-upload',event=>readUpload(event.detail?.file));
  $('import-format').addEventListener('change',renderFieldControls);$('import-value-type').addEventListener('change',renderFieldControls);
  $('confirm-import').addEventListener('click',confirmImport);$('cancel-import').addEventListener('click',()=>{pendingFile=null;pendingSource=null;window.__uploadState=null;window.__restoredCsv='';$('observations').value='';$('import-review').hidden=true;status('Choose a different CSV or Excel workbook.');});
  $('target-drug').addEventListener('change',()=>{showTargetCount();updateRecipeConfig();});
  document.querySelectorAll('input[name="recipe-goal"]').forEach(input=>input.addEventListener('change',applyRecipeGoal));
  $('refresh-target-counts').addEventListener('click',refreshCounts);
  $('dataset').addEventListener('change',()=>{setRecipeVisibility();if($('dataset').value!=='upload')renderTargets([],false);});
  document.addEventListener('amr:result',event=>{auditState(event.detail);trustAndLayers(event.detail);});
  document.addEventListener('amr:upload-ready',()=>{setRecipeVisibility();window.__targetCounts=normalizedCounts(window.__uploadState?.normalizedCsv||window.__restoredCsv||'');renderTargets(window.__targetCounts,true);});
  document.addEventListener('amr:state',({detail})=>{for(const id of ['refresh-target-counts','confirm-import','cancel-import'])if($(id))$(id).disabled=detail.busy;});
  $('recipe-panel').hidden=$('dataset').value==='demo';
  if(window.__uploadState?.normalizedCsv){window.__targetCounts=normalizedCounts(window.__uploadState.normalizedCsv);renderTargets(window.__targetCounts,true);}
})();
