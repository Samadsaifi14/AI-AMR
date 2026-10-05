"""Changing holdout answers must not change selected models or operating thresholds."""
import json
from pathlib import Path
import pandas as pd
from amr_discovery.data import build_cohort
from amr_discovery.demo import generate_demo
from amr_discovery.modeling import fit_and_evaluate


def test_holdout_labels_do_not_influence_model_lock(tmp_path,monkeypatch):
    import amr_discovery.modeling as mod
    config=json.loads((Path(__file__).resolve().parents[1]/"configs/demo.json").read_text())
    config["bootstrap_repeats"]=10
    cohort,audit,_,features=build_cohort(generate_demo(tmp_path/"data",600),config)
    original=mod.candidates
    monkeypatch.setattr(mod,"candidates",lambda cols,seed:original(cols,seed)[:4])
    a=tmp_path/"a";a.mkdir()
    fit_and_evaluate(cohort,features,config,audit,a)
    altered=cohort.copy()
    mask=altered.source_id.eq("DEMO_B")
    altered.loc[mask,"y"]=altered.loc[mask,"y"].to_numpy()[::-1]
    b=tmp_path/"b";b.mkdir()
    fit_and_evaluate(altered,features,config,audit,b)
    lock_a=json.loads((a/"model_lock.json").read_text())
    lock_b=json.loads((b/"model_lock.json").read_text())
    for key in ["selected_model","threshold","deferral_low","deferral_high","split_sha256"]:
        assert lock_a[key]==lock_b[key]

