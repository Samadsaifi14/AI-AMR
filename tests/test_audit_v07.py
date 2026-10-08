import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from amr_discovery.data import IntegrityError, build_cohort, validate_config, construct_groups
from amr_discovery.demo import generate_demo
from amr_discovery.harmonization import known
from amr_discovery.modeling import ResearchModel, metrics, xgboost_candidates
from amr_discovery.uncertainty import exact_interval

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('value', ['unknown', 'NaN', 'N/A', 'None', 'REPLACE_WITH_DOCUMENTED_VERSION'])
def test_placeholders_do_not_establish_provenance(value):
    assert not known(value)
    cfg = json.loads((ROOT / 'configs/india_strict_categorical.json').read_text())
    cfg['standard_version'] = value
    with pytest.raises(IntegrityError, match='pinned'):
        validate_config(cfg)


@pytest.mark.parametrize('field,value', [('sensitivity_target', 0), ('specificity_target', float('nan')),
    ('deferral_halfwidth', .5), ('bootstrap_repeats', 0)])
def test_invalid_protocol_rejected_before_training(field, value):
    cfg = json.loads((ROOT / 'configs/demo.json').read_text())
    cfg[field] = value
    with pytest.raises(IntegrityError):
        validate_config(cfg)


def test_whitespace_cannot_split_an_isolate_identity(tmp_path):
    cfg = json.loads((ROOT / 'configs/demo.json').read_text())
    path = generate_demo(tmp_path / 'data', 100)
    before, _, _, _ = build_cohort(path, cfg)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    row = raw.iloc[[0]].copy()
    row['isolate_id'] = ' ' + row.isolate_id + ' '
    pd.concat([raw, row]).to_csv(path, index=False)
    after, _, _, _ = build_cohort(path, cfg)
    pd.testing.assert_frame_equal(before, after)


def test_failed_and_unreviewed_models_defer_all_decisions():
    m = ResearchModel(None, None, [], .5, .4, .6, 'test', 'EXPLORATORY_MEASURED_DATA', ['A'])
    assert set(m.decisions([.01, .99])) == {'defer_model_not_validated'}
    m.interpretation_status = 'OPERATING_POINT_FAILED'
    assert set(m.decisions([.01, .99])) == {'defer_model_not_validated'}
    with pytest.raises(IntegrityError):
        m.decisions([float('nan')])


def test_predictor_requires_species_and_valid_panel():
    cols = ['drug__S', 'drug__I', 'drug__R', 'drug__SDD', 'drug__missing']
    m = ResearchModel(None, None, cols, .5, .4, .6, 'test', 'TEST', ['A'])
    frame = pd.DataFrame([[1, 0, 0, 0, 0]], columns=cols)
    with pytest.raises(IntegrityError, match='species'):
        m.predict_proba(frame)
    with pytest.raises(IntegrityError, match='species'):
        m.predict_proba(frame.assign(species='B'))
    frame['drug__R'] = 1
    with pytest.raises(IntegrityError, match='encoding'):
        m.predict_proba(frame.assign(species='A'))
    frame[cols] = [0, 0, 0, 0, 1]
    with pytest.raises(IntegrityError, match='insufficient'):
        m.predict_proba(frame.assign(species='A'))


def test_quick_prediction_cannot_bypass_strict_provenance(monkeypatch):
    import browser_bridge as bridge
    monkeypatch.setattr(bridge, 'LAST_MODEL', object())
    monkeypatch.setattr(bridge, 'LAST_CFG', {'comparability_policy': 'strict'})
    with pytest.raises(IntegrityError, match='provenance'):
        bridge.execute({'action': 'predict'})


def test_quick_prediction_rejects_units_and_target_answers(monkeypatch):
    import browser_bridge as bridge
    monkeypatch.setattr(bridge, 'LAST_MODEL', object())
    monkeypatch.setattr(bridge, 'LAST_CFG', {'features': ['cefepime'], 'min_observed_features': 1})
    with pytest.raises(IntegrityError, match='Unexpected'):
        bridge.execute({'action': 'predict', 'values': {'meropenem': {'value': '4'}}})
    with pytest.raises(IntegrityError, match='unit'):
        bridge.execute({'action': 'predict', 'species': 'A',
                        'values': {'cefepime': {'value': '4', 'units': 'mm'}}})


@pytest.mark.parametrize('y,p', [([0, .9], [.1, .9]), ([0, 1], [.1]), ([[0, 1]], [[.1, .9]])])
def test_metric_input_cannot_silently_change_labels(y, p):
    with pytest.raises(IntegrityError):
        metrics(y, p)


def test_perfect_sample_retains_uncertainty():
    assert exact_interval(10, 10)['low'] < .70
    assert exact_interval(0, 10)['high'] > .30


def test_native_xgboost_is_real_and_reproducible():
    pytest.importorskip('xgboost')
    cols = ['a', 'b']
    rng = np.random.default_rng(12)
    frame = pd.DataFrame(rng.normal(size=(60, 2)), columns=cols)
    y = (frame.a > 0).astype(int)
    for name, model, columns in xgboost_candidates(cols, 42):
        assert model.named_steps['model'].__class__.__module__.startswith('xgboost')
        probability = model.fit(frame[columns], y).predict_proba(frame[columns])[:, 1]
        assert np.isfinite(probability).all()


def test_same_hospital_patient_is_grouped_across_sources():
    frame = pd.DataFrame([
        dict(isolate_id='A', patient_id='p', hospital_id='H', source_id='one'),
        dict(isolate_id='B', patient_id='p', hospital_id='H', source_id='two'),
        dict(isolate_id='C', patient_id='p', hospital_id='elsewhere', source_id='three')])
    groups = construct_groups(frame)
    assert groups[0] == groups[1] and groups[2] != groups[0]


def test_wide_categorical_import_preserves_all_rows_without_mics(tmp_path):
    from amr_discovery.importer import import_wide
    source = tmp_path/'wide.csv'
    source.write_text('id,MEM,FEP\nA,R,S\nB,S,\n')
    mapping = tmp_path/'mapping.json'
    mapping.write_text(json.dumps({'metadata': {'isolate_id': 'id'},
        'constants': {'source_id': 'study', 'species': 'A'},
        'drugs': {'meropenem': {'reported_sir': 'MEM'}, 'cefepime': {'reported_sir': 'FEP'}}}))
    out = tmp_path/'long.csv'
    manifest = import_wide(source, mapping, out, chunksize=1)
    frame = pd.read_csv(out, keep_default_na=False)
    assert manifest['input_rows'] == 2 and manifest['output_rows'] == 4
    assert frame.measurement.eq('').all()
    assert frame.loc[frame.isolate_id.eq('B') & frame.drug.eq('cefepime'), 'reported_sir'].iloc[0] == ''


def test_colistin_disk_categories_are_not_valid_features(tmp_path):
    from test_categorical import categorical_fixture
    p, cfg, raw = categorical_fixture(tmp_path)
    replaced = cfg['features'][0]
    cfg['features'][0] = 'colistin'
    mask = raw.drug.eq(replaced)
    raw.loc[mask, 'drug'] = 'colistin'
    raw.loc[mask, 'method'] = 'disk diffusion'
    raw.to_csv(p, index=False)
    cohort, audit, _, _ = build_cohort(p, cfg)
    assert not cohort.empty
    assert cohort['colistin__missing'].eq(1).all()
    assert audit['excluded_event_counts']['feature_drug_method_incompatible'] > 0


def test_explicit_quarantine_cannot_be_bypassed_by_exploratory_labels(tmp_path):
    from test_categorical import categorical_fixture
    p, cfg, raw = categorical_fixture(tmp_path)
    raw['curation_status'] = 'QUARANTINED_STANDARD_VERSION_AND_UNITS_REVIEW_REQUIRED'
    raw.to_csv(p, index=False)
    cohort, audit, _, _ = build_cohort(p, cfg)
    assert cohort.empty
    assert audit['excluded_event_counts']['curation_quarantined'] == raw.isolate_id.nunique()
