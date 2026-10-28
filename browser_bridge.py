"""Browser entry points for the same audited local Python pipeline."""
import base64
import io
import json
import shutil
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from amr_discovery.data import build_cohort, IntegrityError, parse_mic, encode_ast, validate_config, COMBINATIONS, REQUIRED
from amr_discovery.modeling import fit_and_evaluate
from amr_discovery.reporting import write_report
from amr_discovery.topology import gene_network, spatial_edges

LAST_MODEL = None
LAST_CFG = None
LAST_TRAIN_IDS = set()
LAST_PROFILE = None


def archive(folder):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                z.write(p,p.relative_to(folder).as_posix())
    return base64.b64encode(stream.getvalue()).decode()


def _normalise_wide_observations(csv_text, cfg):
    """Conservatively convert common wide AST matrices to long observations."""
    try:
        raw = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise IntegrityError(f"Could not parse the uploaded CSV: {exc}") from exc
    raw.columns = [str(col).strip() for col in raw.columns]
    raw = raw.apply(lambda col: col.str.strip())
    if REQUIRED <= set(raw.columns):
        return csv_text, False

    def norm(value):
        return ''.join(ch.lower() for ch in str(value) if ch.isalnum())

    by_norm = {norm(col): col for col in raw.columns}
    def find(*names):
        return next((by_norm[norm(name)] for name in names if norm(name) in by_norm), None)

    id_col = find('isolate_id','isolate id','isolate','biosample','biosample accession',
                  '#BioSample','sample id','strain id','accession','id')
    species_col = find('species','organism','scientific name','taxon','bacterial species')
    source_col = find('source_id','source id','study id','project id','BioProject','study','dataset')
    evidence_col = find('evidence_class','evidence class','evidence type')
    standard_col = find('standard','testing standard','interpretation standard','guideline')
    version_col = find('standard_version','standard version','breakpoint version','guideline version')
    method_col = find('method','AST method','test method','assay')
    platform_col = find('platform','laboratory typing platform','instrument','system','AST platform')
    units_col = find('units','unit','MIC units','measurement units')
    country_col = find('country','country of origin')
    location_col = find('location','geographic location')
    region_col = find('region','geoclimatic zone','state')
    patient_col = find('patient_id','patient id','patient','subject id')
    if not id_col or not species_col:
        # If this is not recognisably a wide AST table, leave it for the canonical-schema validator.
        return csv_text, False

    from amr_discovery.data import drug_name, ANTIBIOTICS, COMBINATIONS
    supported = set(ANTIBIOTICS) | set(COMBINATIONS)
    drug_aliases = {
        'amoxicillin-clavulanic acid':'amoxicillin-clavulanate',
        'amoxicillin clavulanic acid':'amoxicillin-clavulanate',
        'amoxicillin/clavulanate':'amoxicillin-clavulanate',
        'piperacillin tazobactam':'piperacillin-tazobactam',
        'ceftazidime avibactam':'ceftazidime-avibactam',
        'trimethoprim sulfamethoxazole':'trimethoprim-sulfamethoxazole',
        'polymyxin b':'polymyxin-b'
    }
    def canonical_drug(label):
        label = str(label).strip()
        label_norm = norm(label)
        if label_norm.endswith('phenotype'):
            label = label[:-len('phenotype')].rstrip(' _-')
        elif label_norm.endswith('interpretation'):
            label = label[:-len('interpretation')].rstrip(' _-')
        elif label_norm.endswith('micmgl'):
            label = label[:-len('micmgl')].rstrip(' _-')
        elif label_norm.endswith('micmg l'):
            label = label[:-len('micmg l')].rstrip(' _-')
        elif label_norm.endswith('mic'):
            label = label[:-len('mic')].rstrip(' _-')
        key = label.lower().replace('_',' ').strip()
        key = drug_aliases.get(key, key)
        key = drug_name(key)
        return key if key in supported else None

    # Group columns by drug and result type. A phenotype + MIC pair becomes one
    # observation, preserving both original fields when both are supplied.
    drug_columns = {}
    for col in raw.columns:
        cn = norm(col)
        kind = None
        if cn.endswith('phenotype'):
            kind = 'sir'
        elif cn.endswith('interpretation'):
            kind = 'sir'
        elif 'mic' in cn and (cn.endswith('mgl') or cn.endswith('mic') or '_mic_' in col.lower()):
            kind = 'mic'
        if not kind:
            continue
        drug = canonical_drug(col)
        if drug:
            drug_columns.setdefault(drug, {})[kind] = col

    if not drug_columns:
        return csv_text, False

    # A public accession supports public-source classification; otherwise evidence
    # must be explicitly present in the uploaded file.
    public_identifier = find('#BioSample','BioSample','BioSample accession','accession','NCBI accession')
    if not evidence_col and not public_identifier:
        raise IntegrityError(
            "Wide AST matrix detected, but evidence class is not recorded. Add an evidence_class column "
            "with measured_public or measured_authorized according to the source documentation."
        )

    sir_values = {'s','susceptible','sensitive','r','resistant','i','intermediate',
                  'sdd','susceptibledosedependent'}
    import re
    rows = []
    for _, source_row in raw.iterrows():
        isolate = source_row.get(id_col, '').strip()
        species = source_row.get(species_col, '').strip()
        if not isolate or not species:
            continue
        source = source_row.get(source_col, '').strip() if source_col else ''
        evidence = source_row.get(evidence_col, '').strip() if evidence_col else 'measured_public'
        for drug, result_cols in drug_columns.items():
            sir_raw = source_row.get(result_cols.get('sir',''), '').strip() if result_cols.get('sir') else ''
            mic_raw = source_row.get(result_cols.get('mic',''), '').strip() if result_cols.get('mic') else ''
            if not sir_raw and not mic_raw:
                continue
            item = {field: '' for field in REQUIRED}
            item.update(
                isolate_id=isolate,
                source_id=source or 'unknown_source_review_required',
                species=species,
                drug=drug,
                evidence_class=evidence,
                method=source_row.get(method_col, '').strip() if method_col else '',
                standard=source_row.get(standard_col, '').strip() if standard_col else '',
                standard_version=source_row.get(version_col, '').strip() if version_col else '',
                units=source_row.get(units_col, '').strip() if units_col else '',
                country=source_row.get(find('country','country of origin') or '', '').strip(),
                region=source_row.get(region_col, '').strip() if region_col else '',
                patient_id=source_row.get(patient_col, '').strip() if patient_col else '',
                platform=source_row.get(platform_col, '').strip() if platform_col else '',
                specimen=source_row.get(find('specimen','isolation source','isolation type') or '', '').strip(),
                host=source_row.get(find('host') or '', '').strip(),
                collection_date=source_row.get(find('collection date','collection_date','date collected') or '', '').strip(),
                source_row=source_row.get(find('index','row id','source row') or '', '').strip()
            )
            if sir_raw and norm(sir_raw) in sir_values:
                item['reported_sir'] = sir_raw
            elif sir_raw:
                # Preserve unrecognized phenotype text in the source export, but do not map it to S/I/R.
                item['reported_sir'] = ''
            if mic_raw:
                match = re.fullmatch(r'\s*(<=|>=|<|>|≤|≥|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*', mic_raw)
                if match:
                    item['operator'] = (match.group(1) or '=').replace('≤','<=').replace('≥','>=')
                    item['measurement'] = match.group(2)
                    # Units are assigned only when explicitly encoded in the MIC header or source units field.
                    if not item['units'] and 'mgl' in norm(result_cols.get('mic','')):
                        item['units'] = 'mg/L'
                else:
                    # If MIC is not parseable, retain any valid reported phenotype only.
                    if not item['reported_sir']:
                        continue
            rows.append(item)
    if not rows:
        raise IntegrityError("Wide AST matrix detected, but no supported antibiotic phenotype/MIC results were found. Check drug column names and values.")
    return pd.DataFrame(rows).to_csv(index=False), True

def execute(payload):
    global LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS, LAST_PROFILE
    action = payload['action']
    if action == 'import_export':
        from amr_discovery.export_import import import_ncbi_export
        content,manifest=import_ncbi_export(payload.get('csv',''),payload.get('reference_csv',''))
        LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS, LAST_PROFILE = None, None, set(), None
        return json.dumps({'action':action,'csv':content,'manifest':manifest})
    if action == 'drift':
        from amr_discovery.learning import drift_report
        if LAST_PROFILE is None or LAST_CFG is None:
            raise IntegrityError('Train a session version before checking incoming data drift.')
        if payload.get('configuration') and validate_config(json.loads(payload['configuration'])) != LAST_CFG:
            raise IntegrityError('Session configuration changed; monitoring cannot use a stale model.')
        data=Path('/monitor.csv');data.write_text(payload['csv'])
        cohort,audit,exclusions,_=build_cohort(data,LAST_CFG)
        drift=drift_report(LAST_PROFILE,cohort,LAST_CFG)
        return json.dumps({'action':action,'drift':drift,'audit':audit},allow_nan=False)
    if action == 'prepare':
        from amr_discovery.batches import merge_observations
        content,manifest=merge_observations(payload.get('csv',''),payload.get('base_csv',''))
        LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS, LAST_PROFILE = None, None, set(), None
        return json.dumps({'action':'prepare','csv':content,'manifest':manifest})
    if action == 'predict':
        if LAST_MODEL is None:
            raise IntegrityError('Train a model in this session before predicting.')
        if LAST_CFG.get('comparability_policy') == 'strict':
            # This compact form cannot collect observation-level QC, method and panel provenance.
            # Never silently weaken the contract used to train a strict model.
            raise IntegrityError('Strict models require observation-level laboratory provenance. Use the external CSV evaluation workflow; this quick prediction form cannot verify it.')
        if set(LAST_CFG['features']) & COMBINATIONS:
            raise IntegrityError('Combination MIC prediction needs documented inhibitor concentration; use the external CSV evaluation workflow.')
        extra = set(payload.get('values', {})) - set(LAST_CFG['features'])
        if extra:
            raise IntegrityError('Unexpected prediction drugs; supply only the selected predictor panel.')
        row = {'species':payload['species']}
        observed = 0
        for drug in LAST_CFG['features']:
            d = payload['values'].get(drug, {})
            value = str(d.get('value','')).strip()
            if LAST_CFG.get('representation') == 'categorical_ast':
                encoded, present = encode_ast(drug, value)
                row.update(encoded); observed += int(present)
                continue
            mic = parse_mic(value,str(d.get('operator','')),str(d.get('units','mg/L'))) if value else None
            if value and mic is None:
                raise IntegrityError(f'Invalid MIC for {drug}; use a positive mg/L bound up to 1024.')
            observed += int(mic is not None)
            row.update({f'{drug}__log2_bound':mic.log2 if mic else np.nan,
                        f'{drug}__left_censored':float(mic.operator in {'<','<='}) if mic else 0.,
                        f'{drug}__right_censored':float(mic.operator in {'>','>='}) if mic else 0.,
                        f'{drug}__strict_bound':float(mic.operator in {'<','>'}) if mic else 0.,
                        f'{drug}__missing':float(mic is None)})
        if observed < LAST_CFG['min_observed_features']:
            raise IntegrityError('Insufficient observed AST panel; defer.')
        p = LAST_MODEL.predict_proba(pd.DataFrame([row]))
        return json.dumps({'action':action,'probability':float(p[0]),'decision':str(LAST_MODEL.decisions(p)[0]),
                           'threshold':LAST_MODEL.threshold,'evidence_status':LAST_MODEL.evidence_status,
                           'interpretation_status':getattr(LAST_MODEL,'interpretation_status','NOT_EVALUATED'),
                           'clinical_validation':False})
    if action == 'topology':
        if not LAST_TRAIN_IDS:
            raise IntegrityError('Train first: networks use development training isolates only.')
        folder = Path('/topology')
        shutil.rmtree(folder,ignore_errors=True)
        folder.mkdir()
        result = {'action':action,'analysis':'Exploratory development-only observations; not causal interactions or transmission.'}
        for kind, func in [('genes',gene_network),('geography',spatial_edges)]:
            content = payload.get(kind,'').strip()
            if content:
                frame = pd.read_csv(io.StringIO(content),dtype=str).fillna('')
                edges = func(frame,LAST_TRAIN_IDS)
                edges.to_csv(folder / f'{kind}_edges.csv',index=False)
                result[kind] = {'edges':len(edges),'preview':json.loads(edges.head(30).to_json(orient='records'))}
        if len(result)==2:
            raise IntegrityError('Choose a gene or geography CSV.')
        (folder/'analysis.json').write_text(json.dumps(result,indent=2))
        result['archive'] = archive(folder)
        return json.dumps(result,allow_nan=False)
    LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS, LAST_PROFILE = None, None, set(), None
    print('Checking configuration and laboratory input', flush=True)
    cfg = validate_config(json.loads(payload['configuration']))
    folder = Path('/run')
    shutil.rmtree(folder,ignore_errors=True)
    folder.mkdir()
    input_csv, was_normalized = _normalise_wide_observations(payload['csv'], cfg)
    data = Path('/input.csv')
    data.write_text(input_csv)
    (folder/'input_observations.csv').write_text(input_csv)
    if was_normalized:
        # Wide public matrices often lack a breakpoint release. Permit only the
        # explicitly exploratory/non-strict path; strict comparability remains blocked.
        if cfg.get('comparability_policy', 'exploratory') != 'strict' and not cfg.get('standard_version'):
            cfg['allow_unversioned_reported'] = True
            (folder/'configuration.json').write_text(json.dumps(cfg, indent=2))
            print('Wide AST import: unversioned reported labels allowed for exploratory analysis only. Strict comparability is not established.', flush=True)
        print('Recognized wide AST matrix and converted paired phenotype/MIC fields to long observations. Review unknown source/method/version provenance in the audit; no missing values were imputed.', flush=True)
    # Fail early with a usable import explanation instead of a Python traceback.
    # Never synthesize missing provenance or infer MICs from categorical AST.
    try:
        input_columns = set(pd.read_csv(data, nrows=0, dtype=str).columns.str.strip())
    except Exception as exc:
        raise IntegrityError(f"Could not read the uploaded CSV header ({exc}). Export a UTF-8 CSV and retry.") from exc
    missing_columns = sorted(REQUIRED - input_columns)
    if missing_columns:
        wide_hints = [c for c in input_columns if any(token in c.lower() for token in
                       ('meropenem', 'imipenem', 'cefepime', 'ceftazidime', 'ciprofloxacin', 'amikacin'))]
        if wide_hints or not {'drug', 'measurement'} <= input_columns:
            raise IntegrityError(
                "This file is not in the required long-format observation schema. "
                f"Missing columns: {', '.join(missing_columns)}. "
                "It may be a wide antibiotic matrix. Open Use my own data and complete the "
                "column-mapping/preview step so the app creates a normalized analysis copy. "
                "If the mapping step is unavailable for this file, use the local Python "
                "import-wide workflow with an explicitly reviewed mapping file (see the Pune user guide). "
                "Map source, species, method, units, interpretation standard/version and evidence from records; "
                "do not invent missing metadata or convert S/I/R categories to MIC numbers."
            )
        raise IntegrityError(
            "The uploaded file is missing required observation columns: "
            + ", ".join(missing_columns)
            + ". Use the downloadable MIC or categorical AST template and map the original source columns."
        )
    breakpoints = None
    if payload.get('breakpoints','').strip():
        breakpoints = '/breakpoints.csv'
        Path(breakpoints).write_text(payload['breakpoints'])
        (folder/'reviewed_breakpoints.csv').write_text(payload['breakpoints'])
    cohort,audit,exclusions,columns = build_cohort(data,cfg,breakpoints,progress=lambda message: print(message,flush=True))
    print(f'Audit complete: {len(cohort)} eligible isolates. Preparing {action}.',flush=True)
    cohort.to_csv(folder/'cohort.csv',index=False)
    pd.DataFrame(audit['panel_coverage']).to_csv(folder/'panel_coverage.csv',index=False)
    exclusions.to_csv(folder/'exclusions.csv',index=False)
    (folder/'audit.json').write_text(json.dumps(audit,indent=2))
    (folder/'configuration.json').write_text(json.dumps(cfg,indent=2))
    answer = {'action':action,'audit':audit,'preview':json.loads(cohort.head(15).to_json(orient='records')),
              'countries':json.loads(cohort.groupby('country').size().rename('isolates').reset_index().to_json(orient='records')) if len(cohort) else []}
    answer['sources'] = json.loads(cohort.groupby('source_id').size().rename('isolates').reset_index().to_json(orient='records')) if len(cohort) else []
    result = None
    blocked = None
    if action == 'validate':
        from amr_discovery.validation import validation_suite
        answer['suite'] = validation_suite(cohort,columns,cfg,audit,folder/'validation')
    if action == 'train':
        try:
            from amr_discovery.modeling import metrics
            result,predictions = fit_and_evaluate(cohort,columns,cfg,audit,folder)
            import joblib
            LAST_MODEL = joblib.load(folder/'research_model.joblib')  # Only the model generated here; no arbitrary uploads.
            LAST_CFG = cfg
            split = pd.read_csv(folder/'cohort_with_splits.csv')
            LAST_TRAIN_IDS = set(split.loc[split.partition.eq('train'),'isolate_id'])
            from amr_discovery.learning import training_artifacts
            answer['learning_version']=training_artifacts(folder,cfg,audit,result)
            LAST_PROFILE=json.loads((folder/'reference_profile.json').read_text())
            answer['metrics'] = result
            curves = folder/'holdout_curves.png'
            if curves.exists():
                answer['curves_png'] = base64.b64encode(curves.read_bytes()).decode('ascii')
            answer['importance'] = json.loads(pd.read_csv(folder/'grouped_permutation_importance.csv').to_json(orient='records'))
            answer['selection'] = json.loads((folder/'feature_selection.json').read_text()) if (folder/'feature_selection.json').exists() else None
            answer['features'] = cfg['features']
            answer['species'] = LAST_MODEL.species
            answer['comparison'] = json.loads(pd.read_csv(folder/'development_cv.csv').to_json(orient='records'))
            subgroup_rows = []
            for column in ('source_id','species'):
                for group, part in predictions.groupby(column, dropna=False):
                    subgroup_rows.append({'grouping':column,'group':group,**metrics(part.y,part.p_resistant,result.get('threshold',.5))})
            answer['subgroups'] = json.loads(pd.DataFrame(subgroup_rows).to_json(orient='records')) if subgroup_rows else []
        except IntegrityError as e:
            blocked = str(e)
            answer['blocked'] = blocked
            (folder/'blocked.json').write_text(json.dumps({'status':'TRAINING_BLOCKED','reason':blocked}))
    print('Building evidence report and downloadable experiment',flush=True)
    write_report(folder,audit,result,blocked)
    answer['report'] = (folder/'report.html').read_text()
    answer['archive'] = archive(folder)
    return json.dumps(answer,allow_nan=False)
