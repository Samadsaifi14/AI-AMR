import json
from pathlib import Path
import pandas as pd
import pytest
from amr_discovery.data import build_cohort, encode_ast, IntegrityError, validate_config
from amr_discovery.demo import generate_demo
from amr_discovery.modeling import partitions

ROOT=Path(__file__).resolve().parents[1]


def categorical_fixture(tmp_path):
    cfg=json.loads((ROOT/'configs/demo.json').read_text())
    cfg['representation']='categorical_ast'
    p=generate_demo(tmp_path/'data',200)
    d=pd.read_csv(p,keep_default_na=False)
    # Test synthetic categorical observations with absent MIC fields.
    mask=~d.drug.eq(cfg['target'])
    d.loc[mask,'reported_sir']=[['S','I','R','SDD'][i%4] for i in range(mask.sum())]
    d['measurement']='';d['units']='';d['method']='reported AST'
    d.to_csv(p,index=False)
    return p,cfg,d


def test_nominal_ast_encoding_preserves_missing_and_sdd():
    for category in ['S','I','R','SDD','']:
        encoded,present=encode_ast('cefepime',category)
        assert sum(encoded.values())==1
        assert encoded['cefepime__'+(category or 'missing')]==1
        assert present==bool(category)
    with pytest.raises(IntegrityError):encode_ast('cefepime','4 mg/L')


def test_categorical_accepts_absent_mics_without_changing_mic_rules(tmp_path):
    p,cfg,_=categorical_fixture(tmp_path)
    cohort,audit,_,cols=build_cohort(p,cfg)
    assert len(cohort)>100
    assert audit['representation']=='categorical_ast'
    assert not any('log2' in c for c in cols)
    cfg['representation']='mic'
    cohort,_,_,_=build_cohort(p,cfg)
    assert cohort.empty


def test_target_results_never_enter_feature_matrix(tmp_path):
    p,cfg,d=categorical_fixture(tmp_path)
    a,_,_,cols=build_cohort(p,cfg)
    mask=d.drug.eq(cfg['target'])
    d.loc[mask,'reported_sir']=d.loc[mask,'reported_sir'].map({'R':'S','S':'R','I':'I'})
    d.to_csv(p,index=False)
    b,_,_,other=build_cohort(p,cfg)
    assert cols==other
    pd.testing.assert_frame_equal(a[cols],b[cols])
    assert a.y.ne(b.y).any()
    assert not any(c.startswith(('meropenem__','imipenem__')) for c in cols)


def test_categorical_does_not_accept_mic_breakpoint_inference(tmp_path):
    _,cfg,_=categorical_fixture(tmp_path)
    cfg['label_mode']='breakpoints'
    with pytest.raises(IntegrityError,match='reported labels'):validate_config(cfg)


def test_region_split_is_not_a_source_split():
    d=pd.DataFrame({'region':['Northern']*60+['Western']*80,'source_id':['one-study']*140,
                    'group_id':range(140),'y':[0,1]*70})
    split=partitions(d,{'split':{'mode':'region','heldout':['Northern']}})
    assert set(split.loc[split.partition.eq('test'),'region'])=={'Northern'}
    assert set(split.loc[~split.partition.eq('test'),'region'])=={'Western'}
    assert split.source_id.nunique()==1


def test_empty_mechanism_cohort_still_has_a_readable_audit_report(tmp_path):
    from amr_discovery.reporting import write_report
    p,cfg,_=categorical_fixture(tmp_path)
    cfg['mechanism_cohort']='NDM_OR_OXA48'
    d=pd.read_csv(p,keep_default_na=False)
    d['ndm']='unknown';d['oxa48']='unknown';d['mechanism_evidence']=''
    d.to_csv(p,index=False)
    cohort,audit,_,_=build_cohort(p,cfg)
    assert cohort.empty and 'isolate_id' in cohort
    out=tmp_path/'report';out.mkdir()
    cohort.to_csv(out/'cohort.csv',index=False)
    assert pd.read_csv(out/'cohort.csv').empty
    write_report(out,audit)
    assert 'AUDIT COMPLETE' in (out/'report.html').read_text()


def test_categorical_training_and_prediction_use_nominal_features(tmp_path,monkeypatch):
    import amr_discovery.modeling as mod
    p,cfg,_=categorical_fixture(tmp_path)
    cfg['bootstrap_repeats']=10
    cohort,audit,_,cols=build_cohort(p,cfg)
    original=mod.candidates
    monkeypatch.setattr(mod,'candidates',lambda c,s:original(c,s)[:4])
    out=tmp_path/'fit';out.mkdir()
    result,predictions=mod.fit_and_evaluate(cohort,cols,cfg,audit,out)
    assert result['all_eligible_isolates_used']
    assert len(predictions)==result['n']
    import joblib
    model=joblib.load(out/'research_model.joblib')
    assert model.columns==cols
    assert len(model.predict_proba(cohort.iloc[:2][cols].assign(species=cohort.iloc[:2].species)))==2
