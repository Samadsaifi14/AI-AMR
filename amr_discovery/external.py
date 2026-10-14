"""Independent challenge of a saved, locally trusted research model snapshot."""
import json
import os
from pathlib import Path
import joblib
import pandas as pd
from .data import IntegrityError, build_cohort, sha256, identity_tokens
from .harmonization import known
from .modeling import metrics, cluster_intervals
from .uncertainty import exact_interval

FILES = ('research_model.joblib', 'model_lock.json', 'cohort_with_splits.csv')


def snapshot_external(run, out):
    run = Path(run).resolve()
    lock = json.loads((run / 'model_lock.json').read_text())
    protocol = {
        'schema': 1, 'run': os.path.relpath(run, Path(out).resolve().parent),
        'sha256': {name: sha256(run / name) for name in FILES},
        'configuration': lock['configuration'], 'threshold': lock['threshold'],
        'country': 'India', 'sensitivity_lower_95_required': .95,
        'specificity_lower_95_required': .50,
        'interpretation': 'External cohort evidence only; no national or clinical certification.',
        'trusted_local_model_only': True,
    }
    with Path(out).open('x') as f:
        json.dump(protocol, f, indent=2)
    return protocol


def evaluate_external(protocol_path, data, out, breakpoints=None):
    """No fitting, calibration, threshold search or row subsampling is performed."""
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(Path(protocol_path).read_text())
    result = {'status': 'BLOCKED', 'india_accuracy_established': False,
              'clinical_validation': False, 'row_subsampling': False,
              'protocol_sha256': sha256(protocol_path), 'input_sha256': sha256(data)}
    try:
        run = (Path(protocol_path).resolve().parent / protocol['run']).resolve()
        if protocol.get('schema') != 1:
            raise IntegrityError('Unsupported external protocol schema.')
        if (protocol['sensitivity_lower_95_required'] != .95
                or protocol['specificity_lower_95_required'] != .50):
            raise IntegrityError('External evidence targets cannot be relaxed in this workflow.')
        for name in FILES:
            if sha256(run / name) != protocol['sha256'][name]:
                raise IntegrityError(f'Evaluation snapshot changed: {name}')
        lock = json.loads((run / 'model_lock.json').read_text())
        if protocol['configuration'] != lock['configuration'] or protocol['threshold'] != lock['threshold']:
            raise IntegrityError('Protocol differs from the evaluation snapshot.')
        if protocol['configuration']['label_mode'] == 'breakpoints':
            if not breakpoints or not lock.get('breakpoints_sha256') or sha256(breakpoints) != lock['breakpoints_sha256']:
                raise IntegrityError('External breakpoint rules must match the hash recorded before evaluation.')
        cohort, audit, exclusions, features = build_cohort(data, protocol['configuration'], breakpoints)
        exclusions.to_csv(folder / 'exclusions.csv', index=False)
        (folder / 'audit.json').write_text(json.dumps(audit, indent=2))
        if audit['synthetic']:
            raise IntegrityError('Synthetic observations cannot establish external measured validation.')
        if cohort.empty:
            raise IntegrityError('No eligible external isolates; inspect exclusions.')
        if not cohort.country.str.strip().str.casefold().eq(protocol['country'].casefold()).all():
            raise IntegrityError('External cohort must contain only the prespecified country.')
        prior = pd.read_csv(run / 'cohort_with_splits.csv', dtype=str, keep_default_na=False)
        if set(cohort.isolate_id) & set(prior.isolate_id):
            raise IntegrityError('External isolate IDs overlap prior training, calibration or test data.')
        if not cohort.source_id.map(known).all():
            raise IntegrityError('External source identity is unknown.')
        if set(cohort.source_id) & set(prior.source_id):
            raise IntegrityError('External sources overlap a previously used source.')
        duplicates = set(cohort.duplicate_group) - {''}
        if duplicates & (set(prior.duplicate_group) - {''}):
            raise IntegrityError('External duplicate components overlap prior data.')
        prior_tokens = set().union(*(identity_tokens(r) for r in prior.to_dict('records')))
        new_tokens = set().union(*(identity_tokens(r) for r in cohort.to_dict('records')))
        if prior_tokens & new_tokens:
            raise IntegrityError('External patient/identity links overlap prior data.')
        # joblib is executable serialization: only load the user's trusted local run.
        model = joblib.load(run / 'research_model.joblib')
        if model.evidence_status == 'SOFTWARE_DEMONSTRATION':
            raise IntegrityError('A synthetic-trained model cannot establish measured model validation.')
        if model.threshold != protocol['threshold']:
            raise IntegrityError('Serialized model threshold differs from the evaluation snapshot.')
        p = model.predict_proba(cohort.drop(columns=['y', 'target_sir']))
        predictions = cohort[['isolate_id', 'source_id', 'species', 'group_id']].copy()
        predictions['probability_R'] = p
        predictions['prediction_R'] = p >= model.threshold
        predictions.to_csv(folder / 'predictions_before_scoring.csv', index=False)
        result.update(metrics(cohort.y, p, model.threshold))
        result['sensitivity_exact_95'] = exact_interval(result['tp'], result['tp']+result['fn'])
        result['specificity_exact_95'] = exact_interval(result['tn'], result['tn']+result['fp'])
        result['cluster_intervals'] = cluster_intervals(cohort.y, p, cohort.group_id, model.threshold,
                                                       repeats=1000)
        result['small_sample_warning'] = bool(cohort.group_id.nunique() < 20
                                             or min(result['resistant'], result['nonresistant']) < 5)
        if result['small_sample_warning']:
            result['bootstrap_warning'] = 'Sparse cohorts can produce degenerate bootstrap intervals; do not interpret them as precise evidence. Exact binomial intervals are also reported.'
        verified = (cohort.patient_id.map(known).all() and cohort.label_version.map(known).all()
                    and not cohort.duplicate_group.duplicated().where(cohort.duplicate_group.ne(''), False).any()
                    and not cohort.patient_id.duplicated().any())
        ci_s = result['sensitivity_exact_95']['low']
        ci_p = result['specificity_exact_95']['low']
        passed = (ci_s is not None and ci_p is not None
                  and ci_s >= protocol['sensitivity_lower_95_required']
                  and ci_p >= protocol['specificity_lower_95_required'])
        result['status'] = 'COHORT_GATES_MET' if passed and verified else 'EXTERNAL_GATES_NOT_ESTABLISHED'
        result['identity_and_label_metadata_complete'] = bool(verified)
        result['interpretation'] = 'Selected external cohort only. National representativeness and prospective clinical utility remain unestablished. Identity checks use recorded identifiers; metadata must be independently verified.'
        result['limitations'] = audit['limitations']
        cohort.assign(probability_R=p).to_csv(folder / 'scored_cohort.csv', index=False)
        rows = []
        for column in ['source_id', 'species']:
            for value, frame in cohort.assign(probability_R=p).groupby(column):
                rows.append({'stratum': column, 'value': value,
                             **metrics(frame.y, frame.probability_R, model.threshold)})
        pd.DataFrame(rows).to_csv(folder / 'strata.csv', index=False)
    except IntegrityError as error:
        result['reason'] = str(error)
    (folder / 'external_result.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    return result

# Compatibility for existing scripts; no retraining lock is imposed.
freeze_external = snapshot_external
