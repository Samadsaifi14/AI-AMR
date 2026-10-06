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
from .data import IntegrityError, sha256


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
            if (mode == "lab" and not df[col].map(known).all()) or df[col].isin(["", "NCBI_SOURCE_UNKNOWN"]).any():
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
    y, p = np.asarray(y, int), np.asarray(p, float)
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

    def predict_proba(self, frame):
        if not set(self.columns) <= set(frame.columns):
            raise IntegrityError("Input matrix is missing required feature columns.")
        if "species" in frame and not set(frame.species) <= set(self.species):
            raise IntegrityError("Unsupported species; defer.")
        raw = self.estimator.predict_proba(frame[self.columns])[:, 1]
        return self.calibrator.predict_proba(logit(raw))[:, 1]

    def decisions(self, probabilities):
        p = np.asarray(probabilities)
        return np.where(p < self.low, "non_resistant_prediction",
                        np.where(p >= self.high, "resistant_prediction", "defer"))


def fit_and_evaluate(cohort, feature_columns, cfg, audit, out):
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
    if absent:
        raise IntegrityError(f"Feature(s) never measured in training: {absent}; revise the panel before evaluation.")
    seed = cfg.get("seed", 42)
    cv, cv_design = development_folds(train, cfg)
    scores, fitted = [], {}
    with threadpool_limits(limits=2):
        for name, model, columns in candidates(feature_columns, seed):
            oof = np.zeros(len(train))
            fold_losses = []
            for tr, va in cv:
                estimator = clone(model).fit(train.iloc[tr][columns], train.iloc[tr].y)
                oof[va] = estimator.predict_proba(train.iloc[va][columns])[:, 1]
                fold_losses.append(log_loss(train.iloc[va].y, oof[va], labels=[0,1]))
            score = {"model": name, **metrics(train.y, oof), "phase": cv_design, "mean_fold_log_loss": float(np.mean(fold_losses)), "worst_fold_log_loss": float(max(fold_losses))}
            scores.append(score)
            fitted[name] = (clone(model).fit(train[columns], train.y), columns)
            print(f"Development CV completed: {name}", flush=True)
        eligible = [s for s in scores if s["model"] not in {"species_only", "missingness_only"}]
        best = min(eligible, key=lambda m: (m["mean_fold_log_loss"], m["worst_fold_log_loss"], m["model"]))["model"]
        estimator, columns = fitted[best]
        cal_raw = estimator.predict_proba(cal[columns])[:, 1]
        calibrator = LogisticRegression(C=1., max_iter=1000).fit(logit(cal_raw), cal.y)
        cal_prob = calibrator.predict_proba(logit(cal_raw))[:, 1]
        threshold = threshold_for_sensitivity(cal.y, cal_prob, cfg.get("sensitivity_target", .95))
        halfwidth = cfg.get("deferral_halfwidth", .1)
        if not 0 <= halfwidth < .5:
            raise IntegrityError("deferral_halfwidth must be in [0,0.5).")
        bundle = ResearchModel(estimator, calibrator, columns, threshold,
                               max(0., threshold-halfwidth), min(1., threshold+halfwidth),
                               best, audit["evidence_status"], cfg["species"])
        # Persist selection and thresholds BEFORE evaluating holdout outcomes.
        lock = {"selected_model": best, "selection": "lowest equally weighted development-fold log loss; worst-fold tie break",
                "selection_cv": cv_design, "threshold": threshold, "deferral_low": bundle.low, "deferral_high": bundle.high,
                "configuration": cfg, "input_sha256": audit["input_sha256"],
                "split_sha256": sha256(folder / "split_manifest.csv"), "calibration": "held-out sigmoid",
                "evidence_status": audit["evidence_status"],
                "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                                "numpy": np.__version__, "pandas": pd.__version__}}
        (folder / "model_lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        joblib.dump(bundle, folder / "research_model.joblib")
        p = bundle.predict_proba(test)
        report = metrics(test.y, p, threshold)
        report["confidence_intervals"] = cluster_intervals(test.y, p, test.group_id, threshold,
                                                           seed, cfg.get("bootstrap_repeats", 200))
        predictions = test[["isolate_id", "source_id", "lab_id", "country", "region", "species", "mechanism", "group_id", "y", "target_sir"]].copy()
        predictions["p_resistant"] = p
        predictions["binary_prediction"] = (p >= threshold).astype(int)
        predictions["decision"] = bundle.decisions(p)
        predictions["evidence_status"] = audit["evidence_status"]
        predictions.to_csv(folder / "test_predictions.csv", index=False)
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
                differences.append(log_loss(test.y, bundle.predict_proba(altered), labels=[0, 1])-base_loss)
            importance.append({"drug": drug, "mean_log_loss_increase": float(np.mean(differences)),
                               "repeat_sd": float(np.std(differences)),
                               "meaning": "predictive reliance, not causal mechanism"})
        pd.DataFrame(importance).to_csv(folder / "grouped_permutation_importance.csv", index=False)
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
    (folder / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report, predictions
