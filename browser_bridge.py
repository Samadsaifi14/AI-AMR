"""Browser entry points for the same audited local Python pipeline."""
import base64
import io
import json
import shutil
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from amr_discovery.data import build_cohort, IntegrityError, parse_mic
from amr_discovery.modeling import fit_and_evaluate
from amr_discovery.reporting import write_report
from amr_discovery.topology import gene_network, spatial_edges

LAST_MODEL = None
LAST_CFG = None
LAST_TRAIN_IDS = set()


def archive(folder):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                z.write(p,p.relative_to(folder).as_posix())
    return base64.b64encode(stream.getvalue()).decode()


def execute(payload):
    global LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS
    action = payload['action']
    if action == 'predict':
        if LAST_MODEL is None:
            raise IntegrityError('Train a model in this session before predicting.')
        row = {'species':payload['species']}
        observed = 0
        for drug in LAST_CFG['features']:
            d = payload['values'].get(drug, {})
            value = str(d.get('value','')).strip()
            mic = parse_mic(value,str(d.get('operator','='))) if value else None
            if value and mic is None:
                raise IntegrityError(f'Invalid MIC for {drug}; use a positive mg/L bound up to 1024.')
            observed += int(mic is not None)
            row.update({f'{drug}__log2_bound':mic.log2 if mic else np.nan,
                        f'{drug}__left_censored':float(mic.operator in {'<','<='}) if mic else 0.,
                        f'{drug}__right_censored':float(mic.operator in {'>','>='}) if mic else 0.,
                        f'{drug}__strict_bound':float(mic.operator in {'<','>'}) if mic else 0.,
                        f'{drug}__missing':float(mic is None)})
        if observed < LAST_CFG['min_observed_features']:
            raise IntegrityError('Insufficient observed MIC panel; defer.')
        p = LAST_MODEL.predict_proba(pd.DataFrame([row]))
        return json.dumps({'action':action,'probability':float(p[0]),'decision':str(LAST_MODEL.decisions(p)[0]),
                           'threshold':LAST_MODEL.threshold,'evidence_status':LAST_MODEL.evidence_status,
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
    LAST_MODEL, LAST_CFG, LAST_TRAIN_IDS = None, None, set()
    cfg = json.loads(payload['configuration'])
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
    cohort,audit,exclusions,columns = build_cohort(data,cfg,breakpoints)
    cohort.to_csv(folder/'cohort.csv',index=False)
    exclusions.to_csv(folder/'exclusions.csv',index=False)
    (folder/'audit.json').write_text(json.dumps(audit,indent=2))
    (folder/'configuration.json').write_text(json.dumps(cfg,indent=2))
    answer = {'action':action,'audit':audit,'preview':json.loads(cohort.head(15).to_json(orient='records')),
              'countries':json.loads(cohort.groupby('country').size().rename('isolates').reset_index().to_json(orient='records')) if len(cohort) else []}
    result = None
    blocked = None
    if action == 'train':
        try:
            result,_ = fit_and_evaluate(cohort,columns,cfg,audit,folder)
            import joblib
            LAST_MODEL = joblib.load(folder/'research_model.joblib')  # Only the model generated here; no arbitrary uploads.
            LAST_CFG = cfg
            split = pd.read_csv(folder/'cohort_with_splits.csv')
            LAST_TRAIN_IDS = set(split.loc[split.partition.eq('train'),'isolate_id'])
            answer['metrics'] = result
            answer['features'] = cfg['features']
            answer['species'] = cfg['species']
            answer['comparison'] = json.loads(pd.read_csv(folder/'development_cv.csv').to_json(orient='records'))
        except IntegrityError as e:
            blocked = str(e)
            answer['blocked'] = blocked
            (folder/'blocked.json').write_text(json.dumps({'status':'TRAINING_BLOCKED','reason':blocked}))
    write_report(folder,audit,result,blocked)
    answer['report'] = (folder/'report.html').read_text()
    answer['archive'] = archive(folder)
    return json.dumps(answer,allow_nan=False)
