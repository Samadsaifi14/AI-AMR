"""Controlled learning: development profiles, immutable versions and release evidence.

No pseudo-labeling, automatic clinical promotion or test-driven optimization.
Models are loaded only from trusted local runs with verified hashes.
"""
import hashlib
import json
import os
import copy
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .data import IntegrityError, identity_tokens, sha256, build_cohort, validate_config
from .modeling import fit_and_evaluate, metrics
from .reporting import write_report
from .harmonization import known
from .uncertainty import exact_interval


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identities(cohort):
    return sorted({hashlib.sha256(t.encode()).hexdigest() for row in cohort.to_dict('records') for t in identity_tokens(row)})


def observation_identities(data):
    """Include excluded observations so a later configuration cannot reuse them."""
    return identities(pd.read_csv(data,dtype=str,keep_default_na=False))


def profile(cohort, cfg):
    """Only call on training rows; quantile bins are fixed before monitoring."""
    if cohort.empty:
        raise IntegrityError('Cannot construct a reference profile from an empty cohort.')
    features = {}
    for drug in cfg['features']:
        if cfg.get('representation') == 'categorical_ast':
            keys = [f'{drug}__{x}' for x in ['S','I','R','SDD','missing']]
            features[drug] = {'kind':'categorical', 'columns':keys,
                              'probabilities':[float(cohort[k].mean()) for k in keys]}
        else:
            key = f'{drug}__log2_bound'
            values = cohort[key].dropna().to_numpy(float)
            cuts = sorted(set(float(x) for x in np.quantile(values, [.2,.4,.6,.8]))) if len(values) else []
            counts = np.histogram(values, [-np.inf, *cuts, np.inf])[0]
            probs = [float(x / len(cohort)) for x in counts] + [float(cohort[key].isna().mean())]
            features[drug] = {'kind':'mic', 'column':key, 'cuts':cuts, 'probabilities':probs}
    return {'schema':1, 'fit_partition':'train', 'n':len(cohort), 'configuration_sha256':digest(cfg),
            'features':features, 'species':cohort.species.value_counts(normalize=True).to_dict(),
            'clinical_validation':False}


def drift_report(reference, cohort, cfg):
    if reference.get('schema') != 1 or reference.get('configuration_sha256') != digest(cfg):
        raise IntegrityError('Monitoring configuration differs from the training reference.')
    if cohort.empty:
        raise IntegrityError('No eligible incoming observations for drift analysis.')
    rows = []
    for drug, spec in reference['features'].items():
        if spec['kind'] == 'categorical':
            q = np.array([float(cohort[k].mean()) for k in spec['columns']])
        else:
            values = cohort[spec['column']].dropna().to_numpy(float)
            counts = np.histogram(values, [-np.inf,*spec['cuts'],np.inf])[0]
            q = np.r_[counts / len(cohort), cohort[spec['column']].isna().mean()]
        p = np.array(spec['probabilities'], float)
        # Smoothing avoids log(0); a descriptive heuristic, not a hypothesis test.
        p, q = np.maximum(p, 1e-6), np.maximum(q, 1e-6)
        p, q = p/p.sum(), q/q.sum()
        psi = float(np.sum((q-p)*np.log(q/p)))
        missing_change = float(q[-1]-p[-1])
        rows.append({'drug':drug, 'psi':psi, 'missingness_change':missing_change,
                     'review_required':psi >= .2 or abs(missing_change) >= .1})
    unseen = sorted(set(cohort.species) - set(reference['species']))
    return {'schema':1, 'status':'REVIEW_REQUIRED' if unseen or any(x['review_required'] for x in rows) else 'NO_HEURISTIC_ALERT',
            'incoming_n':len(cohort), 'reference_n':reference['n'], 'features':rows,
            'unseen_species':unseen, 'clinical_validation':False,
            'interpretation':'PSI >= 0.2 or missingness change >= 0.10 triggers review. These are configurable-workflow heuristics, not proof of harm, safety, accuracy or clinical validity. No retraining or promotion is automatic.'}


def release_evidence(result, audit, independent=False):
    """Research release review uses conservative precision and metadata gates."""
    gates = {
        'measured_data':not audit.get('synthetic', True),
        'independent_evaluation':independent is True,
        'sensitivity_lower_95_at_least_095':(result.get('sensitivity_exact_95',{}).get('low') or 0) >= .95,
        'specificity_lower_95_at_least_050':(result.get('specificity_exact_95',{}).get('low') or 0) >= .5,
        'finite_calibration_evidence':result.get('brier') is not None and np.isfinite(result['brier']),
        'metadata_verified':result.get('identity_and_label_metadata_complete') is True,
    }
    return {'schema':1, 'status':'ELIGIBLE_FOR_RESEARCH_REVIEW' if all(gates.values()) else 'RESEARCH_ONLY_GATES_NOT_MET',
            'gates':{k:bool(v) for k,v in gates.items()}, 'failed_gates':[k for k,v in gates.items() if not v],
            'clinical_validation':False, 'automatic_promotion':False,
            'clinical_requirements':['independent reviewed laboratory cohort','prospective evaluation for intended use',
                                     'clinical oversight and agreed acceptance criteria'],
            'note':'Meeting software research gates does not certify clinical use. Internal and previously inspected public holdouts remain retrospective.'}


def version_manifest(cfg, audit, result, run=None, parent=None):
    manifest = {'schema':1, 'created_at':datetime.now(timezone.utc).isoformat(),
                'configuration_sha256':digest(cfg), 'input_sha256':audit.get('input_sha256'),
                'selected_model':result['selected_model'], 'target':cfg['target'],
                'parent_version':parent, 'clinical_validation':False,
                'scientific_code_sha256':{name:sha256(Path(__file__).parent/name) for name in ['data.py','modeling.py','panel.py','harmonization.py']},
                'metrics':{k:result.get(k) for k in ['n','tp','tn','fp','fn','auroc','sensitivity','specificity','brier']},
                'release':release_evidence(result,audit), 'hashes':{}}
    if run:
        manifest['environment']=json.loads((Path(run)/'model_lock.json').read_text())['environment']
        for name in ['research_model.joblib','model_lock.json','cohort_with_splits.csv','metrics.json','reference_profile.json']:
            manifest['hashes'][name] = sha256(Path(run)/name)
    manifest['version_id'] = digest({k:v for k,v in manifest.items() if k != 'created_at'})[:20]
    return manifest


def training_artifacts(folder, cfg, audit, result, parent=None):
    folder = Path(folder)
    split = pd.read_csv(folder/'cohort_with_splits.csv')
    training = split.loc[split.partition.eq('train')]
    reference = profile(training, cfg)
    (folder/'reference_profile.json').write_text(json.dumps(reference,indent=2))
    manifest = version_manifest(cfg,audit,result,folder,parent)
    (folder/'learning_version.json').write_text(json.dumps(manifest,indent=2))
    return manifest


def _registry(path):
    path = Path(path)
    if path.exists():
        r = json.loads(path.read_text())
        if r.get('schema') != 1:
            raise IntegrityError('Unsupported learning registry.')
        for v in r['versions']:
            v['run']=str((path.resolve().parent/v['run']).resolve())
        for e in r.get('evaluations',[]):
            e['result']=str((path.resolve().parent/e['result']).resolve())
        return r
    return {'schema':1, 'versions':[], 'reserved':[], 'evaluations':[], 'active_research_version':None}


def write_registry(path, registry):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    saved=copy.deepcopy(registry)
    for v in saved['versions']:
        v['run']=os.path.relpath(v['run'],path.resolve().parent)
    for e in saved.get('evaluations',[]):
        e['result']=os.path.relpath(e['result'],path.resolve().parent)
    # Replace one complete registry snapshot rather than partially writing it.
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(saved,indent=2));temp.replace(path)


def reserve_evaluation(data, config, registry):
    cfg = validate_config(json.loads(Path(config).read_text()))
    cohort, audit, _, _ = build_cohort(data,cfg)
    if cohort.empty or audit['synthetic']:
        raise IntegrityError('Reserve nonempty measured evaluation data only.')
    r = _registry(registry)
    tokens = observation_identities(data)
    used = {t for v in r['versions'] for t in v['identities']}
    if used & set(tokens):
        raise IntegrityError('Evaluation identities overlap previously trained or inspected data.')
    entry = {'input_sha256':sha256(data), 'identities':tokens,
             'sources':sorted(pd.read_csv(data,dtype=str,keep_default_na=False).source_id.unique()), 'configuration_sha256':digest(cfg)}
    if any(x['input_sha256']==entry['input_sha256'] for x in r['reserved']):
        raise IntegrityError('Evaluation file is already reserved.')
    r['reserved'].append(entry)
    write_registry(registry,r)
    return {'status':'RESERVED_FOR_EVALUATION','n':len(cohort),'input_sha256':entry['input_sha256']}


def train_version(data, config, out, registry, parent=None, breakpoints=None):
    cfg = validate_config(json.loads(Path(config).read_text()))
    cohort, audit, exclusions, columns = build_cohort(data,cfg,breakpoints)
    r = _registry(registry)
    if parent and parent not in {v['version_id'] for v in r['versions']}:
        raise IntegrityError('Unknown parent version.')
    if parent:
        old = next(v for v in r['versions'] if v['version_id']==parent)
        verify_version(old)
        if old['configuration_sha256'] != digest(cfg):
            raise IntegrityError('Parent configuration differs; start a new lineage for a changed endpoint or design.')
    tokens = observation_identities(data)
    reserved = {t for entry in r['reserved'] for t in entry['identities']}
    reserved_sources = {s for entry in r['reserved'] for s in entry['sources'] if known(s)}
    if set(tokens) & reserved or set(cohort.source_id) & reserved_sources or any(x['input_sha256']==sha256(data) for x in r['reserved']):
        raise IntegrityError('Training would consume reserved evaluation identities or sources.')
    folder = Path(out)
    folder.mkdir(parents=True,exist_ok=False)
    cohort.to_csv(folder/'cohort.csv',index=False)
    exclusions.to_csv(folder/'exclusions.csv',index=False)
    (folder/'audit.json').write_text(json.dumps(audit,indent=2))
    (folder/'configuration.json').write_text(json.dumps(cfg,indent=2))
    try:
        result, _ = fit_and_evaluate(cohort,columns,cfg,audit,folder)
    except IntegrityError as error:
        (folder/'blocked.json').write_text(json.dumps({'status':'TRAINING_BLOCKED','reason':str(error)},indent=2))
        write_report(folder,audit,blocked=str(error))
        raise
    write_report(folder,audit,result)
    version = training_artifacts(folder,cfg,audit,result,parent)
    if any(v['version_id']==version['version_id'] for v in r['versions']):
        raise IntegrityError('Duplicate version content; retain the existing registered run.')
    if parent:
        old = next(v for v in r['versions'] if v['version_id']==parent)
        prior = verify_version(old)
        if old['configuration_sha256'] != digest(cfg):
            raise IntegrityError('Parent configuration differs; start a new lineage for a changed endpoint or design.')
        drift = drift_report(json.loads((prior/'reference_profile.json').read_text()),cohort,cfg)
        (folder/'drift_report.json').write_text(json.dumps(drift,indent=2))
    raw_sources=sorted(pd.read_csv(data,dtype=str,keep_default_na=False).source_id.unique())
    r['versions'].append({**version,'run':str(folder.resolve()),'identities':tokens,'sources':raw_sources})
    write_registry(registry,r)
    return version


def verify_version(version):
    folder = Path(version['run'])
    required={'research_model.joblib','model_lock.json','cohort_with_splits.csv','metrics.json','reference_profile.json'}
    if not required <= set(version.get('hashes',{})):
        raise IntegrityError('Registered version hash manifest is incomplete.')
    for name, expected in version.get('scientific_code_sha256',{}).items():
        if sha256(Path(__file__).parent/name) != expected:
            raise IntegrityError(f'Scientific implementation differs from the registered version: {name}')
    for name, expected in version['hashes'].items():
        if sha256(folder/name) != expected:
            raise IntegrityError(f'Registered model version changed: {name}')
    return folder


def compare_versions(registry, champion, challenger, out):
    """Paired retrospective comparison only; does not promote a model."""
    r = _registry(registry)
    selected = {v['version_id']:v for v in r['versions']}
    if champion not in selected or challenger not in selected or champion==challenger:
        raise IntegrityError('Choose two distinct registered versions.')
    a,b = selected[champion],selected[challenger]
    if a['configuration_sha256'] != b['configuration_sha256']:
        raise IntegrityError('Comparison requires the same endpoint and configuration.')
    runs = [verify_version(v) for v in [a,b]]
    frames = [pd.read_csv(p/'cohort_with_splits.csv') for p in runs]
    test = frames[0].loc[frames[0].partition.eq('test')].copy()
    test_tokens = set(identities(test))
    for f in frames:
        if test_tokens & set(identities(f.loc[~f.partition.eq('test')])):
            raise IntegrityError('Comparison cohort was used in development of a version.')
    import joblib
    output = {'schema':1,'status':'RETROSPECTIVE_COMPARISON_ONLY','clinical_validation':False,
              'cohort_n':len(test),'versions':[], 'automatic_promotion':False}
    for v,p in zip([a,b],runs):
        model=joblib.load(p/'research_model.joblib')
        pred=model.predict_proba(test)
        output['versions'].append({'version_id':v['version_id'],**metrics(test.y,pred,model.threshold)})
    with Path(out).open('x') as handle:
        json.dump(output,handle,indent=2,allow_nan=False)
    return output


def evaluate_version(registry, version_id, data, out, breakpoints=None):
    """Score a reserved independent file once, without fitting any component."""
    r = _registry(registry)
    version = next((v for v in r['versions'] if v['version_id']==version_id), None)
    if version is None:
        raise IntegrityError('Unknown version.')
    run = verify_version(version)
    cfg = json.loads((run/'configuration.json').read_text())
    file_hash = sha256(data)
    reservation = next((x for x in r['reserved'] if x['input_sha256']==file_hash), None)
    if not reservation or reservation['configuration_sha256'] != digest(cfg):
        raise IntegrityError('Reserve this evaluation file under the same configuration before scoring.')
    if any(x['input_sha256']==file_hash for x in r.get('evaluations', [])):
        raise IntegrityError('Evaluation outcomes have already been inspected; reserve a fresh cohort for independent evidence.')
    if cfg['label_mode']=='breakpoints':
        lock = json.loads((run/'model_lock.json').read_text())
        if not breakpoints or sha256(breakpoints)!=lock.get('breakpoints_sha256'):
            raise IntegrityError('Evaluation must use the original reviewed breakpoint rules.')
    cohort,audit,exclusions,_ = build_cohort(data,cfg,breakpoints)
    if cohort.empty or audit['synthetic']:
        raise IntegrityError('Independent evidence requires eligible measured observations.')
    tokens = set(identities(cohort))
    prior_tokens = {t for v in r['versions'] for t in v['identities']}
    prior_sources = set()
    for v in r['versions']:
        prior = pd.read_csv(verify_version(v)/'cohort_with_splits.csv')
        prior_sources |= set(prior.source_id) | set(v.get('sources',[]))
    if tokens & prior_tokens or set(cohort.source_id) & prior_sources:
        raise IntegrityError('Evaluation identities or sources overlap earlier development or inspected data.')
    import joblib
    model = joblib.load(run/'research_model.joblib')
    if model.evidence_status == 'SOFTWARE_DEMONSTRATION':
        raise IntegrityError('A synthetic-trained model cannot establish measured independent validation.')
    p = model.predict_proba(cohort)
    result = metrics(cohort.y,p,model.threshold)
    result.update(sensitivity_exact_95=exact_interval(result['tp'],result['tp']+result['fn']),
                  specificity_exact_95=exact_interval(result['tn'],result['tn']+result['fp']))
    # Missing provenance cannot be repaired by a good performance score.
    raw = pd.read_csv(data,dtype=str,keep_default_na=False)
    required = ['patient_id','standard_version','lab_id','qc_reference']
    reviewed_rows = raw.loc[raw.isolate_id.isin(cohort.isolate_id)]
    complete = all(c in reviewed_rows and reviewed_rows[c].map(known).all() for c in required)
    complete = complete and cohort.source_id.map(known).all() and not cohort.group_id.duplicated().any()
    result['identity_and_label_metadata_complete'] = bool(complete)
    result.update(version_id=version_id,input_sha256=file_hash,clinical_validation=False,
                  evaluation_scope='Reserved independent cohort; software-checked metadata require human verification.')
    result['release']=release_evidence(result,audit,independent=True)
    folder=Path(out);folder.mkdir(parents=True,exist_ok=False)
    cohort.assign(p_resistant=p).to_csv(folder/'predictions.csv',index=False)
    exclusions.to_csv(folder/'exclusions.csv',index=False)
    (folder/'evaluation.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    r.setdefault('evaluations',[]).append({'version_id':version_id,'input_sha256':file_hash,
                'result':str((folder/'evaluation.json').resolve()),'result_sha256':sha256(folder/'evaluation.json')})
    write_registry(registry,r)
    return result


def promote_research(registry, version_id):
    """Explicit research promotion only; no clinical deployment entitlement."""
    r=_registry(registry)
    version=next((v for v in r['versions'] if v['version_id']==version_id),None)
    if version is None:
        raise IntegrityError('Unknown version.')
    verify_version(version)
    evidence=[e for e in r.get('evaluations',[]) if e['version_id']==version_id]
    passed=False
    for e in evidence:
        if sha256(e['result'])!=e['result_sha256']:
            raise IntegrityError('Registered evaluation changed.')
        result=json.loads(Path(e['result']).read_text())
        if result['release']['status']=='ELIGIBLE_FOR_RESEARCH_REVIEW':
            passed=True
    if not passed:
        raise IntegrityError('Research promotion blocked: independent performance and provenance gates are not met.')
    r['active_research_version']=version_id
    write_registry(registry,r)
    return {'status':'ACTIVE_RESEARCH_VERSION','version_id':version_id,'clinical_validation':False}
