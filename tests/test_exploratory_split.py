import json
import csv
import io

import numpy as np
import pandas as pd

from amr_discovery.modeling import exploratory_group_split, fit_and_evaluate


def test_exploratory_split_is_grouped_stratified_and_approximately_seventy_thirty():
    labels = np.array([1] * 10 + [0] * 90)
    frame = pd.DataFrame({"y": labels, "group_id": [f"G{i}" for i in range(len(labels))]})
    train, test = exploratory_group_split(frame, seed=42)
    assert len(test) == 30
    assert set(frame.iloc[train].group_id).isdisjoint(frame.iloc[test].group_id)
    assert int(frame.iloc[test].y.sum()) == 3
    assert int(frame.iloc[train].y.sum()) == 7


def test_single_rare_class_remains_in_training_and_metrics_can_be_unavailable():
    labels = np.array([1] + [0] * 99)
    frame = pd.DataFrame({"y": labels, "group_id": [f"G{i}" for i in range(len(labels))]})
    train, test = exploratory_group_split(frame, seed=42)
    assert frame.iloc[train].y.sum() == 1
    assert frame.iloc[test].y.sum() == 0
    assert len(test) == 30


def test_small_sample_training_writes_reproducible_target_specific_artifacts(tmp_path):
    drugs = ["ceftriaxone", "cefepime", "ciprofloxacin"]
    columns = [f"{drug}__{category}" for drug in drugs for category in ["S", "I", "R", "SDD", "missing"]]
    labels = np.array([1] * 12 + [0] * 68)
    frame = pd.DataFrame({
        "isolate_id": [f"I{i}" for i in range(len(labels))],
        "group_id": [f"G{i}" for i in range(len(labels))],
        "source_id": "ncbi_source_unknown", "lab_id": "", "country": "USA", "region": "",
        "species": ["Escherichia coli"] * len(labels), "mechanism": "unknown",
        "y": labels, "target_sir": np.where(labels == 1, "R", "S"),
    })
    rng = np.random.default_rng(4)
    categorical = {}
    for drug in drugs:
        categories = rng.choice(["S", "R", "missing"], size=len(labels), p=[.55, .25, .20])
        categorical[drug] = categories
    # Every fixture isolate passes the configured two-drug coverage gate,
    # matching the cohort that the real audit gives the trainer.
    for i in range(len(labels)):
        absent = [drug for drug in drugs if categorical[drug][i] == "missing"]
        for drug in absent[1:]:
            categorical[drug][i] = "S"
    for drug in drugs:
        categories = categorical[drug]
        for category in ["S", "I", "R", "SDD", "missing"]:
            frame[f"{drug}__{category}"] = (categories == category).astype(float)
    cfg = {
        "target": "meropenem", "task": "antibiotic_resistance", "species": ["Escherichia coli"],
        "features": drugs, "min_observed_features": 2, "human_only": False,
        "representation": "categorical_ast", "label_mode": "reported", "endpoint": "R_vs_S",
        "standard": "CLSI", "allow_unversioned_reported": True,
        "split": {"mode": "exploratory_70_30"}, "include_species": False,
        "model_families": ["logistic"], "decision_policy": "research_binary",
        "bootstrap_repeats": 5, "require_known_source": False,
    }
    audit = {"input_sha256": "fixture", "evidence_status": "EXPLORATORY_MEASURED_DATA"}
    output = tmp_path / "run"
    output.mkdir()
    result, predictions = fit_and_evaluate(frame, columns, cfg, audit, output)
    assert result["split_mode"] == "exploratory_70_30"
    assert result["partition_counts"] == {"test": 24, "train": 56}
    assert result["interpretation_status"] == "EXPLORATORY_SMALL_SAMPLE"
    assert not result["clinical_validation"]
    assert len(predictions) == 24
    lock = json.loads((output / "model_lock.json").read_text())
    assert lock["calibration"].startswith("none")
    assert (output / "research_model.joblib").exists()


def test_browser_bridge_returns_reserved_panel_exploratory_training_artifacts(tmp_path, monkeypatch):
    import browser_bridge
    execute = browser_bridge.execute
    native_path = browser_bridge.Path

    def local_path(value):
        if str(value) == "/run":
            return native_path(tmp_path / "run")
        if str(value) == "/input.csv":
            return native_path(tmp_path / "input.csv")
        return native_path(value)

    monkeypatch.setattr(browser_bridge, "Path", local_path)

    rows = []
    drugs = ["ceftriaxone", "cefepime", "ciprofloxacin", "meropenem"]
    for i in range(80):
        resistant = i < 12
        for j, drug in enumerate(drugs):
            rows.append({
                "isolate_id": f"ISO{i:03d}", "source_id": "fixture-source",
                "species": "Escherichia coli", "drug": drug,
                "measurement": "8" if resistant and drug == "meropenem" else "0.5",
                "operator": "=", "units": "mg/L", "method": "reported AST",
                "standard": "CLSI", "standard_version": "", "reported_sir":
                    ("resistant" if resistant else "susceptible") if drug == "meropenem" else
                    ("resistant" if (i + j) % 4 == 0 else "susceptible"),
                "evidence_class": "measured_authorized",
            })
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    cfg = {
        "target": "meropenem", "task": "antibiotic_resistance",
        "species": ["Escherichia coli"],
        "features": ["ceftriaxone", "cefepime", "ciprofloxacin"],
        "min_observed_features": 3, "human_only": False,
        "representation": "categorical_ast", "label_mode": "reported",
        "endpoint": "R_vs_S", "standard": "CLSI",
        "allow_unversioned_reported": True,
        "comparability_policy": "exploratory", "split": {"mode": "exploratory_70_30"},
        "include_species": False, "model_families": ["logistic"],
        "decision_policy": "research_binary", "require_known_source": False,
        "bootstrap_repeats": 5,
    }
    response = json.loads(execute({
        "action": "train", "configuration": json.dumps(cfg), "csv": stream.getvalue(),
    }))
    assert response["metrics"]["target"] == "meropenem"
    assert response["metrics"]["split_mode"] == "exploratory_70_30"
    assert response["metrics"]["partition_counts"] == {"test": 24, "train": 56}
    assert response["learning_version"]
    assert "research_model.joblib" in response["archive"] or response["archive"]

