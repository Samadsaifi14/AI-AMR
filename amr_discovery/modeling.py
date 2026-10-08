"""Grouped train/calibration/test separation and development-only model selection."""
from __future__ import annotations
from dataclasses import dataclass
import json
import platform
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, make_column_selector
from .panel import DrugPanelSelector
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             roc_auc_score, confusion_matrix)
from sklearn.model_selection import StratifiedGroupKFold, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from threadpoolctl import threadpool_limits
from .data import IntegrityError, sha256, validate_config
from .uncertainty import exact_interval


def logit(p):
    p = np.clip(p, 1e-6, 1-1e-6)
    return np.log(p / (1-p)).reshape(-1, 1)


def class_gate(frame, minimum, label):
    counts = frame.y.value_counts()
    if set(counts.index) != {0, 1} or counts.min() < minimum:
        raise IntegrityError(f"{label} needs >= {minimum} isolates of each class; found {counts.to_dict()}.")


def partitions(df, cfg):
    seed = cfg.get("seed", 42)
    split = cfg.get("split", {"mode": "internal"})
    mode = split["mode"]
    if mode == "internal":
        class_gate(df, 20, "Internal split")
        sg = StratifiedGroupKFold(5, shuffle=True, random_state=seed)
        dev_idx, test_idx = next(sg.split(df, df.y, df.group_id))
        dev, test = df.iloc[dev_idx].copy(), df.iloc[test_idx].copy()
    elif mode in {"source", "country", "region", "lab", "temporal"}:
        if mode == "temporal":
            dates = pd.to_datetime(df.collection_date, errors="coerce", format="mixed")
            if dates.isna().any():
                raise IntegrityError("Temporal splitting requires valid dates for every eligible isolate.")
            mask = dates.ge(pd.Timestamp(split["cutoff"]))
        else:
            col = {"source": "source_id", "country": "country", "region": "region", "lab": "lab_id"}[mode]
            from .harmonization import known
            if not df[col].map(known).all():
                raise IntegrityError(f"{mode} split cannot use unknown {col}.")
            heldout = split.get("heldout", [])
            if not heldout or not set(heldout) <= set(df[col]):
                raise IntegrityError("Every prespecified holdout must be present in eligible data.")
            mask = df[col].isin(heldout)
        dev, test = df.loc[~mask].copy(), df.loc[mask].copy()
        if set(dev.group_id) & set(test.group_id):
            raise IntegrityError("A patient/duplicate group crosses the external boundary; curate it explicitly.")
    else:
        raise IntegrityError("Split mode must be internal, source, country, region, lab or temporal.")
    class_gate(dev, 20, "Development")
    class_gate(test, 5, "Holdout (software minimum, not adequate research precision)")
    sg = StratifiedGroupKFold(4, shuffle=True, random_state=seed+1)
    train_idx, cal_idx = next(sg.split(dev, dev.y, dev.group_id))
    train, cal = dev.iloc[train_idx].copy(), dev.iloc[cal_idx].copy()
    class_gate(train, 10, "Training")
    class_gate(cal, 5, "Calibration")
    for a, b in [(train, cal), (train, test), (cal, test)]:
        if set(a.group_id) & set(b.group_id):
            raise IntegrityError("Group overlap between partitions.")
    result = []
    for part, frame in [("train", train), ("calibration", cal), ("test", test)]:
        frame["partition"] = part
        result.append(frame)
    return pd.concat(result, ignore_index=True)


def development_folds(train, cfg):
    """Match model selection to source transport, never inspecting final test data."""
    mode = cfg.get("selection_cv", "auto")
    if mode not in {"auto", "source", "grouped"}:
        raise IntegrityError("selection_cv must be auto, source or grouped.")
    use_source = mode == "source" or (mode == "auto" and train.source_id.nunique() >= 3)
    if use_source:
        if train.source_id.nunique() < 3:
            raise IntegrityError("Source selection needs at least three development sources.")
        if train.groupby("group_id").source_id.nunique().max() > 1:
            raise IntegrityError("A patient/duplicate group crosses development sources.")
        folds = list(LeaveOneGroupOut().split(train, train.y, train.source_id))
        for a, b in folds:
            class_gate(train.iloc[a], 2, "Source CV training")
        return folds, "leave_one_development_source_out"
    folds = list(StratifiedGroupKFold(3, shuffle=True, random_state=cfg.get("seed",42)+2)
                 .split(train, train.y, train.group_id))
    for a, b in folds:
        class_gate(train.iloc[a], 2, "Inner training fold")
        class_gate(train.iloc[b], 2, "Inner validation fold")
    return folds, "patient_duplicate_grouped; insufficient source diversity or explicitly requested"


def metrics(y, p, threshold=.5):
    y, p = np.asarray(y), np.asarray(p, float)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or not np.isin(y, [0, 1]).all():
        raise IntegrityError("Metrics require aligned one-dimensional binary labels and probabilities.")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise IntegrityError("Threshold must be finite in [0,1].")
    y = y.astype(int)
    if not len(y):
        return {"n": 0}
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise IntegrityError("Probabilities must be finite in [0,1].")
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    div = lambda a, b: float(a / b) if b else None
    sensitivity, specificity = div(tp, tp+fn), div(tn, tn+fp)
    two = len(np.unique(y)) == 2
    return {"n": len(y), "resistant": int(y.sum()), "nonresistant": int(len(y)-y.sum()),
            "prevalence": float(y.mean()), "threshold": float(threshold),
            "auroc": float(roc_auc_score(y, p)) if two else None,
            "average_precision": float(average_precision_score(y, p)) if two else None,
            "brier": float(brier_score_loss(y, p)), "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "sensitivity": sensitivity, "specificity": specificity,
            "balanced_accuracy": (sensitivity+specificity)/2 if two else None,
            "ppv": div(tp, tp+fp), "npv": div(tn, tn+fn), "accuracy": float((pred == y).mean()),
            "false_negative_fraction_R": div(fn, fn+tp),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def cluster_intervals(y, p, groups, threshold, seed=42, repeats=200):
    y, p, groups = np.asarray(y), np.asarray(p), np.asarray(groups)
    unique = np.unique(groups)
    rng = np.random.default_rng(seed)
    lookup = {g: np.flatnonzero(groups == g) for g in unique}
    names = ["auroc", "average_precision", "brier", "sensitivity", "specificity", "false_negative_fraction_R"]
    values = {name: [] for name in names}
    for _ in range(repeats):
        ix = np.concatenate([lookup[g] for g in rng.choice(unique, len(unique), replace=True)])
        m = metrics(y[ix], p[ix], threshold)
        for name in names:
            if m[name] is not None:
                values[name].append(m[name])
    return {name: {"low": float(np.quantile(v, .025)), "high": float(np.quantile(v, .975)),
                   "valid_replicates": len(v), "unit": "patient/duplicate component, else isolate"}
            for name, v in values.items() if v}


def threshold_for_sensitivity(y, p, desired=.95):
    y, p = np.asarray(y), np.asarray(p)
    if not 0 < desired <= 1:
        raise IntegrityError("Sensitivity target must be in (0,1].")
    thresholds = np.unique(np.concatenate(([0.0], p)))
    good = [t for t in thresholds if ((p >= t) & (y == 1)).sum() / (y == 1).sum() >= desired]
    return float(max(good))


def transport_threshold(train, oof_probabilities, calibration, calibration_probabilities, desired):
    """Conservative source thresholds using development outcomes only."""
    rows = []
    for partition, frame, probability in [('training_oof', train, oof_probabilities),
                                          ('calibration', calibration, calibration_probabilities)]:
        probability = np.asarray(probability)
        rows.append({'partition': partition, 'source': '__pooled__',
                     'resistant': int(frame.y.sum()),
                     'threshold': threshold_for_sensitivity(frame.y, probability, desired)})
        for source in sorted(frame.source_id.unique()):
            mask = frame.source_id.eq(source).to_numpy()
            # Each measured development source informs transport; single-positive
            # source estimates remain visibly sparse rather than being discarded.
            if frame.loc[mask, 'y'].sum() > 0:
                rows.append({'partition': partition, 'source': source,
                             'resistant': int(frame.loc[mask, 'y'].sum()),
                             'threshold': threshold_for_sensitivity(frame.loc[mask, 'y'], probability[mask], desired)})
    return float(min(row['threshold'] for row in rows)), rows


def select_candidate(scores, cfg):
    """Choose using development out-of-fold predictions only, never holdout metrics."""
    eligible = [s for s in scores if s['model'] not in {'species_only', 'missingness_only'}]
    if cfg.get('selection_objective', 'log_loss') == 'specificity_at_sensitivity':
        return min(eligible, key=lambda m: (-m['development_specificity_at_sensitivity'],
                   m['mean_fold_log_loss'], m['worst_fold_log_loss'], m['model']))['model']
    return min(eligible, key=lambda m: (m['mean_fold_log_loss'], m['worst_fold_log_loss'], m['model']))['model']


def candidates(columns, seed):
    def numeric(est):
        return Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                         ("scale", StandardScaler()), ("model", est)])
    result = [("prevalence", numeric(DummyClassifier(strategy="prior")), columns),
              ("species_only", Pipeline([("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                                         ("model", LogisticRegression(max_iter=1000))]), ["species"])]
    # Missingness is a diagnostic control, not eligible to become the primary model.
    miss = [c for c in columns if c.endswith("__missing")]
    result.append(("missingness_only", numeric(LogisticRegression(max_iter=1000)), miss))
    for C in [.1, 1.0]:
        result.append((f"logistic_C{C}", numeric(LogisticRegression(C=C, max_iter=2000)), columns))
    for depth in [4, 8]:
        result.append((f"forest_depth{depth}", numeric(RandomForestClassifier(n_estimators=120,
                       max_depth=depth, min_samples_leaf=5, n_jobs=1, random_state=seed)), columns))
    for leaves in [7, 15]:
        result.append((f"boost_leaves{leaves}", numeric(HistGradientBoostingClassifier(max_iter=120,
                       max_leaf_nodes=leaves, l2_regularization=2, early_stopping=False,
                       random_state=seed)), columns))
    return result


def xgboost_candidates(columns, seed):
    """Explicit opt-in native comparison; absence must never silently substitute another engine."""
    try:
        from xgboost import XGBClassifier
    except ImportError as error:
        raise IntegrityError('XGBoost requested but unavailable. Install the native xgboost extra; it is not supplied by the browser runtime.') from error
    return [(f'xgboost_depth{depth}', Pipeline([
        ('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
        ('model', XGBClassifier(n_estimators=120, max_depth=depth, learning_rate=.05,
                               min_child_weight=5, reg_lambda=2, subsample=1.,
                               colsample_bytree=1., objective='binary:logistic',
                               eval_metric='logloss', tree_method='hist', n_jobs=1,
                               random_state=seed))]), columns) for depth in [2, 4]]


@dataclass
class ResearchModel:
    estimator: object
    calibrator: object
    columns: list
    threshold: float
    low: float
    high: float
    name: str
    evidence_status: str
    species: list
    interpretation_status: str = "NOT_EVALUATED"
    min_observed_features: int = 1
    decision_policy: str = "validated_band"

    def predict_proba(self, frame):
        if not set(self.columns) <= set(frame.columns):
            raise IntegrityError("Input matrix is missing required feature columns.")
        if "species" not in frame or not set(frame.species) <= set(self.species):
            raise IntegrityError("Unsupported species; defer.")
        matrix = frame[[c for c in self.columns if c != "species"]].to_numpy(dtype=float)
        if np.isinf(matrix).any():
            raise IntegrityError('Infinite feature value; defer.')
        missing_cols = [c for c in self.columns if c.endswith('__missing')]
        if missing_cols:
            flags = frame[missing_cols].to_numpy(dtype=float)
            if not np.isin(flags, [0, 1]).all() or ((1-flags).sum(axis=1) < self.min_observed_features).any():
                raise IntegrityError('Invalid or insufficient observed AST panel; defer.')
        for missing in missing_cols:
            prefix = missing.removesuffix('__missing')
            if prefix + '__S' in self.columns:
                cols = [c for c in self.columns if c.startswith(prefix + '__')]
                values = frame[cols].to_numpy(dtype=float)
                if not np.isin(values, [0, 1]).all() or not (values.sum(axis=1) == 1).all():
                    raise IntegrityError('Invalid categorical AST encoding; defer.')
            else:
                bound = frame[prefix + '__log2_bound'].to_numpy(dtype=float)
                absent = frame[missing].to_numpy(dtype=float).astype(bool)
                if not np.array_equal(np.isnan(bound), absent):
                    raise IntegrityError('MIC bound and missingness disagree; defer.')
        raw = self.estimator.predict_proba(frame[self.columns])[:, 1]
        return self.calibrator.predict_proba(logit(raw))[:, 1]

    def decisions(self, probabilities):
        p = np.asarray(probabilities)
        if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
            raise IntegrityError("Probabilities must be finite in [0,1].")
        if getattr(self, 'decision_policy', 'validated_band') == 'research_binary':
            return np.where(p >= self.threshold, 'research_resistant', 'research_non_resistant')
        if getattr(self, 'interpretation_status', 'NOT_EVALUATED') not in {
            'EXPLORATORY_OPERATING_POINT_ONLY', 'SOFTWARE_DEMONSTRATION'}:
            return np.full(p.shape, "defer_model_not_validated")
        return np.where(p < self.low, "non_resistant_prediction",
                        np.where(p >= self.high, "resistant_prediction", "defer"))


def fit_and_evaluate(cohort, feature_columns, cfg, audit, out):
    cfg = validate_config(cfg)
    expected = {f"{d}__{suffix}" for d in cfg["features"] for suffix in
                (["S", "I", "R", "SDD", "missing"] if cfg.get("representation") == "categorical_ast" else
                 ["log2_bound", "left_censored", "right_censored", "strict_bound", "missing"])}
    if set(feature_columns) != expected or len(feature_columns) != len(expected):
        raise IntegrityError('Feature matrix differs from the reviewed antibiotic allowlist; possible leakage.')
    folder = Path(out)
    if cohort.empty:
        raise IntegrityError("No eligible isolates; inspect exclusions before training.")
    split = partitions(cohort, cfg)
    split.to_csv(folder / "cohort_with_splits.csv", index=False)
    split[["isolate_id", "group_id", "source_id", "lab_id", "country", "partition"]].to_csv(folder / "split_manifest.csv", index=False)
    train = split.loc[split.partition.eq("train")]
    cal = split.loc[split.partition.eq("calibration")]
    test = split.loc[split.partition.eq("test")]
    # No all-missing training feature is allowed to masquerade as an observed panel.
    absent = [c for c in feature_columns if c.endswith("__log2_bound") and train[c].isna().all()]
    if cfg.get("representation") == "categorical_ast":
        absent = [d for d in cfg["features"] if train[f"{d}__missing"].eq(1).all()]
    if absent and not cfg.get("feature_selection"):
        raise IntegrityError(f"Feature(s) never measured in training: {absent}; revise the panel before evaluation.")
    seed = cfg.get("seed", 42)
    cv, cv_design = development_folds(train, cfg)
    scores, fitted = [], {}
    oof_predictions = {}
    choices = candidates(feature_columns, seed)
    wants_xgb = cfg.get('include_xgboost', False) or 'xgboost' in cfg.get('model_families', [])
    if wants_xgb:
        choices += xgboost_candidates(feature_columns, seed)
    families = cfg.get('model_families')
    if families:
        prefix = {'random_forest': 'forest_', 'xgboost': 'xgboost_', 'logistic': 'logistic_', 'hist_gradient_boosting': 'boost_'}
        choices = [(n, m, c) for n, m, c in choices if n in {'prevalence', 'species_only', 'missingness_only'} or any(n.startswith(prefix[f]) for f in families)]
    updated = []
    for name, model, cols in choices:
        if name not in {'prevalence', 'species_only', 'missingness_only'}:
            steps = list(model.steps)
            if cfg.get('include_species'):
                cols = list(cols) + ['species']
                # Numeric and nominal transformations fit inside each CV training fold.
                encoder = ColumnTransformer([
                    ('numeric', Pipeline(steps[:-1]), make_column_selector(dtype_include=np.number)),
                    ('species', OneHotEncoder(handle_unknown='ignore', sparse_output=False), ['species'])])
                steps = [('encode', encoder), steps[-1]]
            if cfg.get('feature_selection'):
                steps.insert(0, ('panel', DrugPanelSelector(seed=seed, **cfg['feature_selection'])))
            model = Pipeline(steps)
        updated.append((name, model, cols))
    choices = updated
    with threadpool_limits(limits=2):
        for name, model, columns in choices:
            oof = np.zeros(len(train))
            fold_losses = []
            for fold_index, (tr, va) in enumerate(cv):
                print(f"Training development model {name}: fold {fold_index + 1} of {len(cv)}",flush=True)
                estimator = clone(model).fit(train.iloc[tr][columns], train.iloc[tr].y)
                oof[va] = estimator.predict_proba(train.iloc[va][columns])[:, 1]
                fold_losses.append(log_loss(train.iloc[va].y, oof[va], labels=[0,1]))
            score = {"model": name, **metrics(train.y, oof), "phase": cv_design, "mean_fold_log_loss": float(np.mean(fold_losses)), "worst_fold_log_loss": float(max(fold_losses))}
            operating_threshold = threshold_for_sensitivity(train.y, oof, cfg.get('sensitivity_target', .95))
            operating = metrics(train.y, oof, operating_threshold)
            score.update(development_operating_threshold=operating_threshold,
                         development_specificity_at_sensitivity=operating['specificity'],
                         development_sensitivity_at_threshold=operating['sensitivity'])
            scores.append(score)
            oof_predictions[name] = oof.copy()
            fitted[name] = (clone(model).fit(train[columns], train.y), columns)
            print(f"Development CV completed: {name}", flush=True)
        print('Selecting the model and calibrating with development data',flush=True)
        best = select_candidate(scores, cfg)
        estimator, columns = fitted[best]
        cal_raw = estimator.predict_proba(cal[columns])[:, 1]
        calibrator = LogisticRegression(C=1., max_iter=1000).fit(logit(cal_raw), cal.y)
        cal_prob = calibrator.predict_proba(logit(cal_raw))[:, 1]
        threshold = threshold_for_sensitivity(cal.y, cal_prob, cfg.get("sensitivity_target", .95))
        threshold_details = []
        if cfg.get('threshold_policy', 'calibration') == 'source_robust':
            if calibrator.coef_[0, 0] <= 0:
                raise IntegrityError('Calibration reversed the score ordering; source-robust transport needs a positive calibration slope.')
            oof_probability = calibrator.predict_proba(logit(oof_predictions[best]))[:, 1]
            threshold, threshold_details = transport_threshold(train, oof_probability, cal, cal_prob, cfg.get('sensitivity_target', .95))
            pd.DataFrame(threshold_details).to_csv(folder / 'development_thresholds.csv', index=False)
        halfwidth = cfg.get("deferral_halfwidth", .1)
        if not 0 <= halfwidth < .5:
            raise IntegrityError("deferral_halfwidth must be in [0,0.5).")
        bundle = ResearchModel(estimator, calibrator, columns, threshold,
                               max(0., threshold-halfwidth), min(1., threshold+halfwidth),
                               best, audit["evidence_status"], sorted(train.species.unique()))
        bundle.min_observed_features = cfg['min_observed_features']
        bundle.decision_policy = cfg.get('decision_policy', 'validated_band')
        selected_panel = estimator.named_steps.get('panel')
        if selected_panel is not None:
            selection_manifest = selected_panel.manifest()
            (folder / 'feature_selection.json').write_text(json.dumps(selection_manifest, indent=2))
        else:
            selection_manifest = {'fit_partition': 'prespecified_panel', 'selected_drugs': cfg['features']}
        # Persist selection and thresholds BEFORE evaluating holdout outcomes.
        lock = {"selected_model": best, "selection": "lowest equally weighted development-fold log loss; worst-fold tie break",
                "selection_cv": cv_design, "threshold": threshold, "deferral_low": bundle.low, "deferral_high": bundle.high,
                "threshold_policy": cfg.get("threshold_policy", "calibration"), "development_thresholds": threshold_details,
                "decision_policy": bundle.decision_policy, "feature_selection": selection_manifest, "task": cfg.get("task", "legacy_carbapenem_resistance"),
                "target": cfg["target"], "configuration": cfg, "input_sha256": audit["input_sha256"],
                "breakpoints_sha256": audit.get('breakpoints_sha256'),
                "split_sha256": sha256(folder / "split_manifest.csv"), "calibration": "held-out sigmoid",
                "evidence_status": audit["evidence_status"],
                "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                                "numpy": np.__version__, "pandas": pd.__version__}}
        if wants_xgb:
            import xgboost
            lock['environment']['xgboost'] = xgboost.__version__
        lock['selection_objective'] = cfg.get('selection_objective', 'log_loss')
        if lock['selection_objective'] == 'specificity_at_sensitivity':
            lock['selection'] = 'maximum pooled development out-of-fold specificity at the prespecified sensitivity target; fold log-loss tie breaks'
        (folder / "experiment_snapshot.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        (folder / "model_lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        joblib.dump(bundle, folder / "research_model.joblib")
        print('Evaluating the reserved holdout and computing uncertainty',flush=True)
        p = bundle.predict_proba(test)
        report = metrics(test.y, p, threshold)
        bundle.interpretation_status = (
            "EXPLORATORY_OPERATING_POINT_ONLY"
            if report['sensitivity'] >= cfg.get('sensitivity_target', .95)
            and report['specificity'] >= cfg.get('specificity_target', .5)
            else "OPERATING_POINT_FAILED")
        # Post-evaluation deployment eligibility cannot alter the frozen predictor or threshold.
        # Store it separately from the pre-test lock and retain it in the research bundle.
        joblib.dump(bundle, folder / "research_model.joblib")
        report['sensitivity_exact_95'] = exact_interval(report['tp'], report['tp'] + report['fn'])
        report['specificity_exact_95'] = exact_interval(report['tn'], report['tn'] + report['fp'])
        report['uncertainty_note'] = 'Bootstrap intervals can collapse at zero/all errors. Exact intervals assume independent isolates; neither resolves unrecorded patient clustering.'
        report["confidence_intervals"] = cluster_intervals(test.y, p, test.group_id, threshold,
                                                           seed, cfg.get("bootstrap_repeats", 200))
        predictions = test[["isolate_id", "source_id", "lab_id", "country", "region", "species", "mechanism", "group_id", "y", "target_sir"]].copy()
        predictions["p_resistant"] = p
        predictions["binary_prediction"] = (p >= threshold).astype(int)
        predictions["decision"] = bundle.decisions(p)
        predictions["evidence_status"] = audit["evidence_status"]
        predictions.to_csv(folder / "test_predictions.csv", index=False)
        predictions.loc[predictions.y.ne(predictions.binary_prediction)].to_csv(folder / "error_review.csv", index=False)
        pd.DataFrame(scores).to_csv(folder / "development_cv.csv", index=False)
        baseline_reports = []
        for name in ["prevalence", "species_only", "missingness_only"]:
            model, cols = fitted[name]
            bp_cal = model.predict_proba(cal[cols])[:, 1]
            bt = threshold_for_sensitivity(cal.y, bp_cal, cfg.get("sensitivity_target", .95))
            bp = model.predict_proba(test[cols])[:, 1]
            baseline_reports.append({"model": name, **metrics(test.y, bp, bt)})
        pd.DataFrame(baseline_reports).to_csv(folder / "holdout_baselines.csv", index=False)
        subgroups = []
        for column in ["source_id", "lab_id", "country", "region", "species", "mechanism"]:
            for value, part in predictions.groupby(column, dropna=False):
                subgroups.append({"grouping": column, "group": value,
                                  "interpretation": "exploratory; no multiplicity correction",
                                  **metrics(part.y, part.p_resistant, threshold)})
        pd.DataFrame(subgroups).to_csv(folder / "subgroup_metrics.csv", index=False)
        coverage = []
        for width in [0., .05, .1, .15, .2, .3]:
            lo, hi = max(0., threshold-width), min(1., threshold+width)
            accepted = (p < lo) | (p >= hi)
            decisions = np.where(p >= hi, 1, 0)
            resistant = np.asarray(test.y) == 1
            coverage.append({"halfwidth": width, "coverage": float(accepted.mean()),
                             "accepted_n": int(accepted.sum()),
                             "accepted_error": float((decisions[accepted] != np.asarray(test.y)[accepted]).mean()) if accepted.any() else None,
                             "resistant_called_nonresistant": int((resistant & (p < lo)).sum()),
                             "resistant_deferred": int((resistant & ~accepted).sum()),
                             "resistant_total": int(resistant.sum())})
        pd.DataFrame(coverage).to_csv(folder / "coverage_error.csv", index=False)
        # Jointly permute a drug's value/censor/missing columns, preserving its internal encoding.
        rng = np.random.default_rng(seed)
        importance = []
        base_loss = log_loss(test.y, p, labels=[0, 1])
        for drug in cfg["features"]:
            cols = [c for c in feature_columns if c.startswith(drug+"__")]
            differences = []
            for _ in range(5):
                altered = test.copy()
                altered[cols] = test[cols].to_numpy()[rng.permutation(len(test))]
                # A permutation is a counterfactual diagnostic, not a new eligible specimen.
                altered_raw = bundle.estimator.predict_proba(altered[bundle.columns])[:, 1]
                altered_p = bundle.calibrator.predict_proba(logit(altered_raw))[:, 1]
                differences.append(log_loss(test.y, altered_p, labels=[0, 1])-base_loss)
            importance.append({"drug": drug, "mean_log_loss_increase": float(np.mean(differences)),
                               "repeat_sd": float(np.std(differences)),
                               "meaning": "predictive reliance, not causal mechanism"})
        pd.DataFrame(importance).sort_values("mean_log_loss_increase", ascending=False).to_csv(folder / "grouped_permutation_importance.csv", index=False)
    report.update(selected_model=best, split_mode=cfg["split"]["mode"], evidence_status=audit["evidence_status"],
                  calibration_note="Calibration and operating threshold share a held-out development subset; holdout is untouched.",
                  small_sample_warning=bool(min(report["resistant"], report["nonresistant"]) < 200),
                  source_holdout=cfg["split"]["mode"] == "source",
                  independently_verified_external_validation=False,
                  clinical_validation=False, causal_discovery=False)
    report["partition_counts"] = split.groupby("partition").size().to_dict()
    report["all_eligible_isolates_used"] = len(split) == len(cohort)
    report["selection_cv"] = cv_design
    report["india_test_isolates"] = int(test.country.str.strip().str.casefold().eq("india").sum())
    report["india_validation_status"] = "NOT_ESTABLISHED"
    report["development_sensitivity_target"] = cfg.get("sensitivity_target", .95)
    report["development_specificity_target"] = cfg.get("specificity_target", .5)
    if not 0 <= report["development_specificity_target"] <= 1:
        raise IntegrityError("specificity_target must be between 0 and 1.")
    report["holdout_sensitivity_target_met"] = report["sensitivity"] >= report["development_sensitivity_target"]
    report["holdout_specificity_target_met"] = report["specificity"] >= report["development_specificity_target"]
    report["holdout_operating_target_met"] = report["holdout_sensitivity_target_met"] and report["holdout_specificity_target_met"]
    report["interpretation_status"] = ("OPERATING_POINT_FAILED" if not report["holdout_operating_target_met"]
                                       else "EXPLORATORY_OPERATING_POINT_ONLY")
    report['target'] = cfg['target']
    report['task'] = cfg.get('task', 'legacy_carbapenem_resistance')
    report['selected_drugs'] = selection_manifest['selected_drugs']
    report['prediction_species'] = bundle.species
    report['calibration_slope'] = float(calibrator.coef_[0, 0])
    report['calibration_direction_reversed'] = bool(calibrator.coef_[0, 0] < 0)
    report['threshold_policy'] = cfg.get('threshold_policy', 'calibration')
    report['decision_policy'] = bundle.decision_policy
    report['deferral_note'] = 'Fixed probability band is a research heuristic, not a coverage guarantee; failed operating points defer all new decisions.'
    if bundle.decision_policy == 'research_binary':
        report['deferral_note'] = 'Ungated binary research outputs are enabled; validation status remains visible and no clinical suitability is established.'
    (folder / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report, predictions
