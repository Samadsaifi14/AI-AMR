import numpy as np
import pandas as pd
import pytest
from amr_discovery.modeling import transport_threshold, ResearchModel
from amr_discovery.data import validate_config, IntegrityError
from test_framework import configuration


def test_source_threshold_uses_weaker_development_source():
    train=pd.DataFrame({'source_id':['a']*4+['b']*4,'y':[1,1,0,0]*2})
    probability=np.array([.9,.85,.6,.5,.3,.2,.1,.05])
    cal=pd.DataFrame({'source_id':['a']*4,'y':[1,1,0,0]})
    threshold,rows=transport_threshold(train,probability,cal,[.95,.9,.5,.1],1.)
    assert threshold==.2
    assert all(((probability[train.source_id.eq(s)]>=threshold)&train.loc[train.source_id.eq(s),'y'].eq(1)).sum()==2 for s in ['a','b'])
    assert {r['partition'] for r in rows}=={'training_oof','calibration'}


def test_research_outputs_are_available_without_claiming_validation():
    model=ResearchModel(None,None,[],.3,.2,.4,'test','EXPLORATORY_MEASURED_DATA',[],interpretation_status='OPERATING_POINT_FAILED',decision_policy='research_binary')
    assert list(model.decisions([.1,.5]))==['research_non_resistant','research_resistant']
    assert model.interpretation_status=='OPERATING_POINT_FAILED'
    with pytest.raises(IntegrityError):model.decisions([np.nan])


def test_threshold_policy_rejects_silent_fallback():
    cfg=configuration();cfg['threshold_policy']='test_optimized'
    with pytest.raises(IntegrityError):validate_config(cfg)
