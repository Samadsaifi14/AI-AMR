import json
from pathlib import Path
import pandas as pd
from amr_discovery.modeling import select_candidate, fit_and_evaluate
from amr_discovery.data import build_cohort
from amr_discovery.demo import generate_demo


def test_specificity_objective_does_not_choose_probability_loss_winner():
    scores = [dict(model='logistic', mean_fold_log_loss=.1, worst_fold_log_loss=.2,
                   development_specificity_at_sensitivity=.6),
              dict(model='forest', mean_fold_log_loss=.2, worst_fold_log_loss=.3,
                   development_specificity_at_sensitivity=.8),
              dict(model='species_only', mean_fold_log_loss=.01, worst_fold_log_loss=.01,
                   development_specificity_at_sensitivity=1.)]
    assert select_candidate(scores, {}) == 'logistic'
    assert select_candidate(scores, {'selection_objective':'specificity_at_sensitivity'}) == 'forest'


def test_specificity_selection_cannot_see_holdout_answers(tmp_path, monkeypatch):
    import amr_discovery.modeling as mod
    cfg = json.loads((Path(__file__).resolve().parents[1]/'configs/demo.json').read_text())
    cfg.update(selection_objective='specificity_at_sensitivity', bootstrap_repeats=5)
    cohort, audit, _, cols = build_cohort(generate_demo(tmp_path/'data', 600), cfg)
    original = mod.candidates
    monkeypatch.setattr(mod, 'candidates', lambda c,s: original(c,s)[:5])
    locks = []
    for name, frame in [('original',cohort),('changed',cohort.copy())]:
        if name == 'changed':
            mask = frame.source_id.eq('DEMO_B')
            frame.loc[mask,'y'] = frame.loc[mask,'y'].to_numpy()[::-1]
        out = tmp_path/name; out.mkdir()
        fit_and_evaluate(frame, cols, cfg, audit, out)
        locks.append(json.loads((out/'model_lock.json').read_text()))
    for key in ['selected_model','threshold','split_sha256','selection_objective']:
        assert locks[0][key] == locks[1][key]
