'use strict';
(() => {
  const FIELDS = ['isolate_id','source_id','patient_id','duplicate_group','species','country','collection_date','host','specimen','drug','measurement','operator','units','method','platform','standard','standard_version','reported_sir','ndm','oxa48','mechanism_evidence','evidence_class','accession','source_row','region','hospital_id','lab_id','panel_id','tested_concentrations','qc_reference','fixed_inhibitor_mg_l'];
  const DRUGS = ['meropenem','imipenem','ertapenem','doripenem','cefepime','ceftazidime','cefotaxime','ceftriaxone','cefoxitin','cefazolin','aztreonam','amikacin','gentamicin','tobramycin','ciprofloxacin','levofloxacin','colistin','polymyxin-b','tigecycline','trimethoprim-sulfamethoxazole','ampicillin','piperacillin','fosfomycin','nitrofurantoin','chloramphenicol','tetracycline','ceftazidime-avibactam','meropenem-vaborbactam','imipenem-relebactam','piperacillin-tazobactam','ampicillin-sulbactam','amoxicillin-clavulanate'];
  const ALIASES = {
    isolate_id:['isolate_id','isolate id','isolate','biosample','bio sample','sample id','sample','accession','specimen id'],
    source_id:['source_id','source id','study id','study','bioproject','project id','batch id','cohort'],
    patient_id:['patient_id','patient id','patient code','subject id'],
    duplicate_group:['duplicate_group','duplicate group','replicate group'],
    species:['species','organism','bacterial species','organism name'],
    country:['country','country of origin'], collection_date:['collection_date','collection date','date collected'],
    host:['host','host species'], specimen:['specimen','sample type','isolation source'], drug:['drug','antibiotic','antimicrobial','antibiotic name'],
    measurement:['measurement','mic','mic value','mic (mg/l)','value','result'], operator:['operator','measurement sign','mic operator','sign'],
    units:['units','unit','measurement units','measurement unit'], method:['method','testing method','laboratory typing method'],
    platform:['platform','instrument','testing platform','laboratory typing platform'], standard:['standard','testing standard','interpretation standard'],
    standard_version:['standard_version','standard version','breakpoint version','guideline version'], reported_sir:['reported_sir','sir','s/i/r','phenotype','resistance phenotype','susceptibility','interpretation'],
    evidence_class:['evidence_class','evidence class'], region:['region','state','province'], hospital_id:['hospital_id','hospital id','site id'],
    lab_id:['lab_id','lab id','laboratory id'], panel_id:['panel_id','panel id'], tested_concentrations:['tested_concentrations','tested concentrations'],
    qc_reference:['qc_reference','qc reference'], fixed_inhibitor_mg_l:['fixed_inhibitor_mg_l','inhibitor concentration']
  };
  const DRUG_ALIASES = {'mem':'meropenem','mero':'meropenem','ipm':'imipenem','imi':'imipenem','ert':'ertapenem','etp':'ertapenem','dor':'doripenem','fep':'cefepime','cpm':'cefepime','caz':'ceftazidime','ctx':'cefotaxime','cro':'ceftriaxone','cip':'ciprofloxacin','amk':'amikacin','gen':'gentamicin','tob':'tobramycin','atm':'aztreonam','lvx':'levofloxacin','col':'colistin','polymyxin b':'polymyxin-b','ceftazidime avibactam':'ceftazidime-avibactam','caz avi':'ceftazidime-avibactam','ceftazidime avibactam combo':'ceftazidime-avibactam','piperacillin tazobactam':'piperacillin-tazobactam','pip tazo':'piperacillin-tazobactam','piptazo':'piperacillin-tazobactam','amoxicillin clavulanate':'amoxicillin-clavulanate','amox clav':'amoxicillin-clavulanate','amox clavulanate':'amoxicillin-clavulanate'};
  const norm = value => String(value ?? '').replace(/^\uFEFF/,'').trim().toLowerCase().replace(/[._-]+/g,' ').replace(/\s+/g,' ');
  function parseCSV(text) {
    const rows=[];let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++){
      const ch=text[i];
      if(quoted){if(ch==='"'&&text[i+1]==='"'){cell+='"';i++;}else if(ch==='"')quoted=false;else cell+=ch;}
      else if(ch==='"')quoted=true;
      else if(ch===','){row.push(cell);cell='';}
      else if(ch==='\n'){row.push(cell.replace(/\r$/,''));rows.push(row);row=[];cell='';}
      else cell+=ch;
    }
    if(cell.length||row.length){row.push(cell.replace(/\r$/,''));rows.push(row);}
    return rows.filter((r,i)=>i===0||r.some(v=>String(v).trim()!==''));
  }
  const quote = value => '"'+String(value??'').replace(/"/g,'""')+'"';
  function toCSV(rows) { return rows.map(row=>row.map(quote).join(',')).join('\n')+'\n'; }
  function columnIndex(reference){let value=0;for(const ch of reference.match(/^[A-Z]+/i)?.[0]||''){value=value*26+ch.toUpperCase().charCodeAt(0)-64;}return value-1;}
  function xmlDoc(bytes){const doc=new DOMParser().parseFromString(new TextDecoder().decode(bytes),'application/xml');if(doc.querySelector('parsererror'))throw new Error('The workbook contains an unreadable XML part.');return doc;}
  function parseWorkbook(buffer){
    if(!window.fflate)throw new Error('The local Excel reader did not load. Refresh the page and try again.');
    const files=window.fflate.unzipSync(new Uint8Array(buffer));
    const get=path=>{const item=files[path];if(!item)throw new Error('Workbook is missing '+path+'.');return item;};
    const workbook=xmlDoc(get('xl/workbook.xml'));
    const sheetNode=workbook.getElementsByTagName('sheet')[0];if(!sheetNode)throw new Error('The workbook has no worksheet.');
    const relId=sheetNode.getAttribute('r:id');
    const rels=xmlDoc(get('xl/_rels/workbook.xml.rels'));
    const relation=[...rels.getElementsByTagName('Relationship')].find(node=>node.getAttribute('Id')===relId);
    if(!relation)throw new Error('Could not identify the first worksheet in the workbook.');
    const target=relation.getAttribute('Target');
    const sheetPath=target.startsWith('/')?target.slice(1):target.startsWith('xl/')?target:'xl/'+target;
    const sheet=xmlDoc(get(sheetPath));
    let strings=[];
    if(files['xl/sharedStrings.xml']){
      const shared=xmlDoc(files['xl/sharedStrings.xml']);
      strings=[...shared.getElementsByTagName('si')].map(item=>[...item.getElementsByTagName('t')].map(t=>t.textContent||'').join(''));
    }
    const out=[];
    for(const rowNode of sheet.getElementsByTagName('row')){
      const row=[];
      for(const cell of rowNode.getElementsByTagName('c')){
        const index=columnIndex(cell.getAttribute('r')||'');while(row.length<=index)row.push('');
        const type=cell.getAttribute('t');let value='';
        if(type==='inlineStr')value=[...cell.getElementsByTagName('t')].map(t=>t.textContent||'').join('');
        else {const v=cell.getElementsByTagName('v')[0];value=v?.textContent||'';if(type==='s')value=strings[Number(value)]??'';}
        row[index]=value;
      }
      out.push(row);
    }
    return out;
  }
  function objects(rows){
    if(!rows.length)throw new Error('The selected file has no header row.');
    const headers=rows[0].map((v,i)=>String(v??'').trim()||`Column ${i+1}`);
    if(new Set(headers).size!==headers.length)throw new Error('The file has duplicate column names. Rename the duplicate headers, then choose the file again.');
    return {headers,records:rows.slice(1).map(row=>Object.fromEntries(headers.map((h,i)=>[h,String(row[i]??'').trim()]))) };
  }
  function matchField(header){const n=norm(header);for(const [field,aliases] of Object.entries(ALIASES))if(aliases.some(alias=>norm(alias)===n))return field;return null;}
  function matchDrug(header){const n=norm(header);if(DRUG_ALIASES[n])return DRUG_ALIASES[n];const name=n.replace(/\s*\([^)]*\)\s*$/,'').replace(/\s+/g,'-');return DRUGS.includes(name)?name:null;}
  function inspect(rows){
    const data=objects(rows),{headers,records}=data;
    const drugHeader=headers.find(h=>matchField(h)==='drug');
    const drugColumns=headers.map(h=>({column:h,drug:matchDrug(h)})).filter(x=>x.drug);
    const format=drugHeader?'long':drugColumns.length?'wide':'uncertain';
    const suggestions={};for(const h of headers){const f=matchField(h);if(f&&!suggestions[f])suggestions[f]=h;}
    return {...data,format,drugColumns,suggestions,preview:records.slice(0,8)};
  }
  function mappingControls(headers,selected){return ['isolate_id','source_id','species','patient_id','duplicate_group','country','collection_date','host','specimen','method','platform','standard','standard_version','units','reported_sir','measurement','operator','region','hospital_id','lab_id','panel_id','tested_concentrations','qc_reference','drug','evidence_class'].map(field=>({field,selected:selected[field]||''}));}
  function mapFieldValue(record,source){return source&&source!=='__constant'?(record[source]??''):'';}
  function parseMic(raw){const value=String(raw??'').trim();const m=value.match(/^(<=|≤|<|>=|≥|>)?\s*([0-9]+(?:\.[0-9]+)?(?:e[+-]?\d+)?)\s*(?:mg\s*\/\s*l)?$/i);if(!m)return {measurement:value,operator:''};const op=({'≤':'<=','≥':'>='}[m[1]]||m[1]||'=');return {measurement:m[2],operator:op};}
  function buildLong(source, mapping){
    const {headers,records,format,drugColumns}=source;const fields={...mapping.fields};const constants={...mapping.constants};const metadata={};
    for(const field of FIELDS)if(fields[field])metadata[field]=fields[field];
    const output=[FIELDS];const log=[];let sourceRow=1;
    if(format==='long'){
      for(const [field,column] of Object.entries(fields))if(column)log.push({item:`${field} uses “${column}”`,field,column});
      for(const [field,value] of Object.entries(constants))if(value)log.push({item:`${field} is set to the value you entered`,field,value});
      for(const record of records){sourceRow++;const row={};for(const field of FIELDS){row[field]=field==='source_row'?`${mapping.filename}:${sourceRow}`:mapFieldValue(record,fields[field]);if(constants[field])row[field]=constants[field];}
        if(!row.evidence_class)row.evidence_class=mapping.evidenceClass;
        const drug=fields.drug?record[fields.drug]:(constants.drug||'');row.drug=drug;
        if(mapping.valueType==='mic'&&row.measurement){const parsed=parseMic(row.measurement);if(parsed.operator){row.measurement=parsed.measurement;if(!row.operator)row.operator=parsed.operator;}}
        if(!row.measurement&&!row.reported_sir&&fields.result){const raw=record[fields.result];if(mapping.valueType==='mic'){const parsed=parseMic(raw);row.measurement=parsed.measurement;row.operator=parsed.operator;}else row.reported_sir=raw;}
        output.push(FIELDS.map(field=>row[field]??''));
      }
    } else {
      if(!mapping.drugs?.length)throw new Error('Choose at least one antibiotic column to import.');
      for(const [field,column] of Object.entries(fields))if(column)log.push({item:`${field} uses “${column}”`,field,column});
      for(const [field,value] of Object.entries(constants))if(value)log.push({item:`${field} is set to the value you entered`,field,value});
      for(const drug of mapping.drugs)log.push({item:`Column “${drug.column}” becomes ${drug.drug}`,field:drug.drug,column:drug.column});
      for(const record of records){sourceRow++;for(const drugInfo of mapping.drugs){const row={};for(const field of FIELDS){row[field]=field==='source_row'?`${mapping.filename}:${sourceRow}`:mapFieldValue(record,fields[field]);if(constants[field])row[field]=constants[field];}
        row.isolate_id=fields.isolate_id?record[fields.isolate_id]:constants.isolate_id||'';
        row.source_id=fields.source_id?record[fields.source_id]:constants.source_id||'';
        row.species=fields.species?record[fields.species]:constants.species||'';
        row.drug=drugInfo.drug;
        const raw=record[drugInfo.column]||'';
        if(mapping.valueType==='mic'){const parsed=parseMic(raw);row.measurement=parsed.measurement;row.operator=parsed.operator;row.units=fields.units?record[fields.units]:mapping.units||constants.units||'';}
        else row.reported_sir=raw;
        row.evidence_class=fields.evidence_class?record[fields.evidence_class]:(constants.evidence_class||mapping.evidenceClass);
        output.push(FIELDS.map(field=>row[field]??''));
      }}
    }
    const acceptedLog=log.filter(item=>mapping.accepted?.[item.item]!==false);
    return {csv:toCSV(output),log,acceptedLog,preview:output.slice(0,9).map(row=>Object.fromEntries(FIELDS.map((field,i)=>[field,row[i]])))};
  }
  window.ASTImport={FIELDS,DRUGS,parseCSV,parseWorkbook,inspect,matchField,matchDrug,mappingControls,buildLong,toCSV,quote};
})();
