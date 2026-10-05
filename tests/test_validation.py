import json
from pathlib import Path
import pandas as pd
import pytest
from amr_discovery.modeling import development_folds
from amr_discovery.validation import validation_suite
from amr_discovery.data import IntegrityError


def test_source_cv_separates_sources_and_groups():
    frame = pd.DataFrame({'source_id':[s for s in ['A','B','C'] for _ in range(20)],
                          'group_id':range(60),'y':[0,1]*30})
    folds, design = development_folds(frame,{})
    assert design == 'leave_one_development_source_out'
    assert len(folds) == 3
    heldout = []
    for a,b in folds:
        assert not set(frame.iloc[a].source_id) & set(frame.iloc[b].source_id)
        heldout.extend(b)
    assert sorted(heldout) == list(range(60))
    frame.loc[20,'group_id'] = 0
    with pytest.raises(IntegrityError,match='crosses'):
        development_folds(frame,{})


def test_suite_retains_all_blocked_sources_and_india(tmp_path,monkeypatch):
    import amr_discovery.validation as module
    frame=pd.DataFrame({'isolate_id':['a','b'],'source_id':['A','B'],'country':['USA','USA']})
    calls=[]
    def blocked(cohort,features,cfg,audit,out):
        calls.append((len(cohort),cfg['split']))
        raise IntegrityError('Insufficient classes')
    monkeypatch.setattr(module,'fit_and_evaluate',blocked)
    monkeypatch.setattr(module,'write_report',lambda *a,**k:None)
    result=validation_suite(frame,[],{}, {'input_sha256':'test'},tmp_path)
    assert len(result['experiments'])==4
    assert all(n==2 for n,_ in calls)
    assert all(r['status']=='blocked' for r in result['experiments'])
    assert calls[-1][1]=={'mode':'country','heldout':['India']}
    assert (tmp_path/'suite_protocol.json').exists()
