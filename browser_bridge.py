"""Browser entry points for the same audited local Python pipeline."""
import base64
import io
import json
import shutil
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from amr_discovery.data import build_cohort, IntegrityError, parse_mic, encode_ast, validate_config, COMBINATIONS
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
    data = Path('/input.csv')
    data.write_text(payload['csv'])
    (folder/'input_observations.csv').write_text(payload['csv'])
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
