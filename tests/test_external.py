import json
import pandas as pd
import pytest
from amr_discovery.external import exact_interval, freeze_external, evaluate_external
from amr_discovery.demo import generate_demo


def make_run(tmp_path):
    run=tmp_path/'run';run.mkdir()
    (run/'research_model.joblib').write_bytes(b'not loaded by blocked tests')
    cfg=json.loads((__import__('pathlib').Path(__file__).resolve().parents[1]/'configs/demo.json').read_text())
    (run/'model_lock.json').write_text(json.dumps({'configuration':cfg,'threshold':.5}))
    pd.DataFrame({'isolate_id':['prior'],'source_id':['old'],'duplicate_group':['']}).to_csv(run/'cohort_with_splits.csv',index=False)
    protocol=tmp_path/'protocol.json';freeze_external(run,protocol)
    return run,protocol


def test_perfect_small_sample_does_not_prove_sensitivity():
    assert exact_interval(8,8)['low'] < .95
    assert exact_interval(72,72)['low'] >= .95
    assert exact_interval(0,8)['low'] == 0
    assert exact_interval(0,0)['low'] is None


def test_artifact_mutation_blocks_before_deserialization(tmp_path):
    run,protocol=make_run(tmp_path)
    (run/'research_model.joblib').write_bytes(b'changed')
    data=generate_demo(tmp_path/'demo',100)
    result=evaluate_external(protocol,data,tmp_path/'out')
    assert result['status']=='BLOCKED'
    assert 'research_model.joblib' in result['reason']
    assert not result['india_accuracy_established']


def test_synthetic_external_data_cannot_establish_accuracy(tmp_path):
    _,protocol=make_run(tmp_path)
    result=evaluate_external(protocol,generate_demo(tmp_path/'demo',100),tmp_path/'out')
    assert result['status']=='BLOCKED'
    assert 'Synthetic observations' in result['reason']


def test_freeze_cannot_overwrite_protocol(tmp_path):
    run,protocol=make_run(tmp_path)
    with pytest.raises(FileExistsError):
        freeze_external(run,protocol)


def test_external_labels_never_enter_predictions(tmp_path, monkeypatch):
    import numpy as np
    from amr_discovery import external
    _,protocol=make_run(tmp_path)
    # Test fixture only: exercise the measured-data branch with a stub predictor.
    data=generate_demo(tmp_path/'demo',100)
    d=pd.read_csv(data,keep_default_na=False)
    d['evidence_class']='measured_authorized';d['country']='India';d['source_id']='NEW'
    d.to_csv(data,index=False)
    class Stub:
        threshold=.5
        evidence_status='EXPLORATORY_MEASURED_DATA'
        def predict_proba(self,frame):
            assert 'y' not in frame and 'target_sir' not in frame
            return np.full(len(frame),.7)
    monkeypatch.setattr(external.joblib,'load',lambda p:Stub())
    a=evaluate_external(protocol,data,tmp_path/'a')
    mask=d.drug.eq('meropenem')
    d.loc[mask,'reported_sir']=d.loc[mask,'reported_sir'].map({'R':'S','S':'R','I':'I'})
    d.to_csv(data,index=False)
    b=evaluate_external(protocol,data,tmp_path/'b')
    assert a['status']!='BLOCKED' and b['status']!='BLOCKED'
    pd.testing.assert_frame_equal(pd.read_csv(tmp_path/'a/predictions_before_scoring.csv'),
                                  pd.read_csv(tmp_path/'b/predictions_before_scoring.csv'))
    assert not a['india_accuracy_established'] and not b['india_accuracy_established']


def test_relaxed_evidence_targets_are_rejected(tmp_path):
    _,protocol=make_run(tmp_path)
    p=json.loads(protocol.read_text());p['sensitivity_lower_95_required']=.1
    protocol.write_text(json.dumps(p))
    result=evaluate_external(protocol,generate_demo(tmp_path/'demo',100),tmp_path/'out')
    assert 'cannot be relaxed' in result['reason']
