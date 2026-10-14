import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from amr_discovery.data import validate_config, IntegrityError, build_cohort
from amr_discovery.panel import DrugPanelSelector
from amr_discovery.demo import generate_demo
from amr_discovery.modeling import fit_and_evaluate

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    return json.loads((ROOT/'configs/framework_browser.json').read_text())


def test_target_and_combination_leakage_excluded():
    cfg = configuration()
    assert 'imipenem' in validate_config(cfg)['features']
    for name in ['MEM', 'meropenem-vaborbactam', 'ndm', 'country']:
        cfg['features'] = [name]
        with pytest.raises(IntegrityError):
            validate_config(cfg)
    cfg = configuration(); cfg['target'] = 'ciprofloxacin'; cfg['features'].remove('ciprofloxacin')
    assert validate_config(cfg)['target'] == 'ciprofloxacin'


def test_selector_training_coverage_and_whole_blocks():
    frame = pd.DataFrame({'a__log2_bound':np.arange(30.), 'a__missing':0.,
                          'b__log2_bound':np.nan, 'b__missing':1.,
                          'c__log2_bound':np.arange(30.)*2, 'c__missing':0.})
    selector = DrugPanelSelector().fit(frame, np.arange(30)%2)
    assert selector.selected_drugs_ == ['a']
    before = selector.manifest()
    changed = frame.copy(); changed['b__missing']=0; changed['b__log2_bound']=np.arange(30.)
    assert list(selector.transform(changed)) == ['a__log2_bound','a__missing']
    assert selector.manifest() == before
    assert 'low_training_coverage' == before['dropped_drugs']['b']


def test_mechanism_annotations_never_enter_matrix(tmp_path):
    cfg = json.loads((ROOT/'configs/demo.json').read_text())
    cfg['task'] = 'antibiotic_resistance'
    file = generate_demo(tmp_path/'data', 200)
    raw = pd.read_csv(file,keep_default_na=False)
    raw['kpc']='positive';raw['mechanism_evidence']='fixture'
    raw.to_csv(file,index=False)
    cohort,audit,_,columns=build_cohort(file,cfg)
    assert cohort.mechanism.str.contains('KPC').all()
    assert not any(c.startswith(('ndm','kpc','vim','imp','oxa48','meropenem')) for c in columns)
    assert audit['panel_coverage']


def test_holdout_values_and_answers_do_not_choose_panel(tmp_path, monkeypatch):
    import amr_discovery.modeling as mod
    cfg=json.loads((ROOT/'configs/demo.json').read_text())
    cfg.update(task='antibiotic_resistance',include_species=True,threshold_policy='source_robust',decision_policy='research_binary',
               feature_selection={'min_coverage':.2,'correlation_threshold':.95,'max_drugs':3},bootstrap_repeats=3)
    cohort,audit,_,columns=build_cohort(generate_demo(tmp_path/'data',600),cfg)
    original=mod.candidates
    monkeypatch.setattr(mod,'candidates',lambda cols,seed:original(cols,seed)[:4])
    a=tmp_path/'a';a.mkdir();fit_and_evaluate(cohort,columns,cfg,audit,a)
    changed=cohort.copy();mask=changed.source_id.eq('DEMO_B')
    changed.loc[mask,'y']=changed.loc[mask,'y'].to_numpy()[::-1]
    for c in columns:
        changed.loc[mask,c]=changed.loc[mask,c].to_numpy()[::-1]
    b=tmp_path/'b';b.mkdir();fit_and_evaluate(changed,columns,cfg,audit,b)
    first=json.loads((a/'model_lock.json').read_text());second=json.loads((b/'model_lock.json').read_text())
    for key in ['selected_model','threshold','feature_selection','split_sha256']:
        assert first[key] == second[key]
    assert len(first['feature_selection']['selected_drugs']) == 3


def test_direct_training_rejects_target_matrix(tmp_path):
    cfg=json.loads((ROOT/'configs/demo.json').read_text())
    with pytest.raises(IntegrityError,match='possible leakage'):
        fit_and_evaluate(pd.DataFrame(),['meropenem__log2_bound'],cfg,{},tmp_path)


def test_combination_requires_measured_inhibitor():
    cfg=configuration();cfg['features']=['ceftazidime-avibactam'];cfg['min_observed_features']=1
    with pytest.raises(IntegrityError,match='fixed_inhibitor'):
        validate_config(cfg)
    cfg['combination_reviews']={'ceftazidime-avibactam':{'reviewed':True,'citation':'fixture-reviewed-protocol','fixed_inhibitor_mg_l':4}}
    assert validate_config(cfg)['features']==['ceftazidime-avibactam']
