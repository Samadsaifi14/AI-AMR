"""Full-cohort, source-by-source exploratory validation; never a clinical certificate."""
from copy import deepcopy
import json
from pathlib import Path
import pandas as pd
from .data import IntegrityError
from .modeling import fit_and_evaluate
from .reporting import write_report
from .harmonization import known


def validation_suite(cohort, features, cfg, audit, out):
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    specifications = [("internal", {"mode": "internal"})]
    if len(cohort):
        specifications += [("source", {"mode": "source", "heldout": [str(source)]})
                           for source in sorted(cohort.source_id.unique())]
        labs = sorted(x for x in set(cohort.get('lab_id', pd.Series(dtype=str))) if known(x))
        if len(labs) > 1:
            specifications += [('lab', {'mode':'lab', 'heldout':[lab]}) for lab in labs]
        regions = sorted(x for x in set(cohort.get('region', pd.Series(dtype=str))) if known(x))
        if len(regions) > 1:
            specifications += [('region', {'mode':'region', 'heldout':[region]}) for region in regions]
    # Always attempt India, including when absent: the blocker is part of the result.
    india_names = sorted({str(c) for c in cohort.get("country", pd.Series(dtype=str))
                          if str(c).strip().casefold() == "india"})
    specifications.append(("India", {"mode": "country", "heldout": india_names or ["India"]}))
    records = []
    (folder / "suite_protocol.json").write_text(json.dumps({
        "configuration": cfg, "input_sha256": audit["input_sha256"],
        "experiments": specifications, "row_subsampling": False,
        "interpretation": "Exploratory repeated validation. No winner selected from test results; fresh external data required."
    }, indent=2))
    for index, (kind, split) in enumerate(specifications):
        run = folder / f"experiment_{index:03d}"
        run.mkdir(exist_ok=False)
        config = deepcopy(cfg)
        config["split"] = split
        (run / "configuration.json").write_text(json.dumps(config, indent=2))
        record = {"experiment": run.name, "kind": kind, "heldout": ", ".join(split.get("heldout", []))}
        eligible = cohort
        if kind == "source" and len(cohort):
            unknown = ~cohort.source_id.map(known)
            # Unknown source rows cannot support source independence; retain an explicit exclusion table.
            cohort.loc[unknown, ["isolate_id", "source_id"]].to_csv(run / "unknown_source_exclusions.csv", index=False)
            eligible = cohort.loc[~unknown].copy()
        record["input_eligible_n"] = len(cohort)
        record["experiment_eligible_n"] = len(eligible)
        record["unknown_source_excluded_n"] = len(cohort)-len(eligible)
        try:
            result, _ = fit_and_evaluate(eligible, features, config, audit, run)
            write_report(run, audit, result)
            record.update({key: result[key] for key in ["n", "fn", "fp", "sensitivity", "specificity", "auroc", "brier", "selected_model", "interpretation_status"]})
            record["status"] = "evaluated"
        except IntegrityError as error:
            record.update(status="blocked", reason=str(error))
            (run / "blocked.json").write_text(json.dumps(record, indent=2))
            write_report(run, audit, blocked=str(error))
        records.append(record)
        pd.DataFrame(records).to_csv(folder / "validation_summary.csv", index=False)
    result = {"experiments": records, "eligible_isolates": len(cohort), "row_subsampling": False,
              "india_validation_status": "NOT_ESTABLISHED", "clinical_validation": False,
              "note": "Source holdouts test transfer within the supplied collection, not independently verified external validation. Never choose a threshold from these test results."}
    (folder / "validation_summary.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
