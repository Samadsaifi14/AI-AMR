import json
import pandas as pd
import pytest
from amr_discovery.data import build_cohort, parse_mic, IntegrityError, validate_config
from amr_discovery.harmonization import provenance_issue
from amr_discovery.modeling import partitions
from test_categorical import categorical_fixture


def test_mic_units_are_equivalent_and_censoring_is_preserved():
    assert parse_mic('<=4', units='µg/mL') == parse_mic('4', '<=', 'mg/L')
    assert parse_mic('>=16').operator == '>='
    assert parse_mic('>=16').bound == 16


@pytest.mark.parametrize('field,value', [('standard','CLSI'),('standard_version','different')])
def test_mixed_predictor_interpretations_become_missing(tmp_path, field, value):
    p,cfg,d=categorical_fixture(tmp_path)
    before,_,_,_=build_cohort(p,cfg)
    drug=cfg['features'][0]
    d.loc[d.drug.eq(drug),field]=value
    d.to_csv(p,index=False)
    after,audit,_,_=build_cohort(p,cfg)
    assert audit['excluded_event_counts']['feature_interpretation_mismatch']>0
    assert after[drug+'__missing'].eq(1).all()
    assert before[drug+'__missing'].eq(0).any()


def test_strict_provenance_excludes_unknown_labs_and_pins_target_version(tmp_path):
    p,cfg,d=categorical_fixture(tmp_path)
    cfg.update(comparability_policy='strict',standard_version=str(d.standard_version.iloc[0]))
    cfg['standard']='EUCAST';d['standard']='EUCAST'
    d['method']='broth microdilution';d['qc_reference']='documented QC record'
    d.to_csv(p,index=False)
    cohort,audit,_,_=build_cohort(p,cfg)
    assert cohort.empty
    assert audit['excluded_event_counts']['target_lab_unknown']>0
    d['lab_id']='lab-A';d.to_csv(p,index=False)
    cohort,_,_,cols=build_cohort(p,cfg)
    assert len(cohort)>100 and all('lab' not in c for c in cols)
    d.loc[d.drug.eq(cfg['target']),'standard_version']='wrong-version'
    d.to_csv(p,index=False)
    cohort,audit,_,_=build_cohort(p,cfg)
    assert cohort.empty and audit['excluded_event_counts']['target_version_mismatch']>0


def test_strict_config_rejects_unknown_interpretation_version():
    with pytest.raises(IntegrityError,match='pinned'):
        validate_config({'comparability_policy':'strict','standard':'EUCAST'})


def test_actual_dilution_ladders_are_checked_without_rescaling():
    row=pd.Series(dict(lab_id='A',qc_reference='QC',method='broth microdilution',
        panel_id='panel-A',tested_concentrations='[0.5, 1, 2, 4, 8]',measurement='>=8',operator='',units='mg/L'))
    assert provenance_issue(row,{},False) is None
    row['tested_concentrations']='[0.5, 1, 4, 8]'
    assert provenance_issue(row,{},False) is None  # Nonuniform reported ladder allowed.
    row['measurement']='2'
    assert provenance_issue(row,{},False)=='dilution_panel_invalid'
    row['tested_concentrations']='[8, 4, 1]'
    assert provenance_issue(row,{},False)=='dilution_panel_invalid'


def test_lab_holdout_uses_real_lab_ids_and_blocks_unknowns():
    d=pd.DataFrame({'lab_id':['A']*60+['B']*80,'source_id':['one-study']*140,
                    'group_id':range(140),'y':[0,1]*70})
    cfg={'split':{'mode':'lab','heldout':['A']}}
    split=partitions(d,cfg)
    assert set(split.loc[split.partition.eq('test'),'lab_id'])=={'A'}
    assert set(split.loc[~split.partition.eq('test'),'lab_id'])=={'B'}
    d.loc[0,'lab_id']=''
    with pytest.raises(IntegrityError,match='unknown lab_id'):partitions(d,cfg)


def test_invalid_supplied_mic_ladder_cannot_enter_exploratory_features(tmp_path):
    from amr_discovery.demo import generate_demo
    from test_categorical import ROOT
    cfg=json.loads((ROOT/'configs/demo.json').read_text())
    p=generate_demo(tmp_path/'data',200)
    cohort,_,_,_=build_cohort(p,cfg)
    isolate=cohort.isolate_id.iloc[0]
    d=pd.read_csv(p,dtype=str,keep_default_na=False)
    d['tested_concentrations']=''
    drug=cfg['features'][0]
    mask=d.isolate_id.eq(isolate)&d.drug.eq(drug)
    d.loc[mask,['measurement','operator','units','tested_concentrations']]=['2','=','mg/L','[4,8]']
    d.to_csv(p,index=False)
    cohort,audit,_,_=build_cohort(p,cfg)
    assert audit['excluded_event_counts']['feature_MIC_invalid']>0
    assert cohort.loc[cohort.isolate_id.eq(isolate),drug+'__missing'].eq(1).all()
