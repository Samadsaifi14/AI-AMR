"""Offline HTML reports and scientific figures from saved source tables."""
import base64
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_curve, precision_recall_curve


def write_report(out, audit, metrics=None, blocked=None):
    out = Path(out)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 150})
    sections = []
    def table(title, frame):
        sections.append(f"<h2>{html.escape(title)}</h2>" + frame.to_html(index=False, escape=True, float_format=lambda v: f"{v:.3f}"))
    table("Cohort accounting", pd.DataFrame([{"measure": k, "value": audit[k]} for k in
          ["raw_rows", "raw_isolates", "eligible_isolates", "evidence_status", "label_mode", "endpoint", "patient_ids_available"]]))
    table("Exclusion events", pd.DataFrame([{"reason": k, "events": v} for k,v in audit["excluded_event_counts"].items()]))
    sections.append("<p>Exclusion events may include feature-level events; they are not a count of unique excluded isolates.</p>")
    cohort_path = out / "cohort.csv"
    if cohort_path.exists():
        df = pd.read_csv(cohort_path)
        if not df.empty:
            table("Eligible source and outcome counts", df.groupby(["source_id", "y"]).size().reset_index(name="n"))
            table("Mechanism annotation", df.groupby("mechanism").size().reset_index(name="n"))
    if metrics:
        table("Locked holdout results", pd.DataFrame([{"measure": k, "value": metrics[k]} for k in
              ["selected_model", "split_mode", "n", "resistant", "nonresistant", "auroc", "average_precision",
               "sensitivity", "specificity", "brier", "fn", "fp", "small_sample_warning"]]))
        intervals = [{"metric": k, **v} for k,v in metrics["confidence_intervals"].items()]
        table("Bootstrap uncertainty", pd.DataFrame(intervals))
        for name, title in [("holdout_baselines.csv", "Baseline comparison"),
                            ("subgroup_metrics.csv", "Exploratory subgroup results"),
                            ("coverage_error.csv", "Deferral coverage and errors"),
                            ("grouped_permutation_importance.csv", "Predictive feature reliance")]:
            table(title, pd.read_csv(out / name))
        p = pd.read_csv(out / "test_predictions.csv")
        fig, axes = plt.subplots(1, 3, figsize=(13, 3.7))
        fpr,tpr,_ = roc_curve(p.y,p.p_resistant)
        axes[0].plot(fpr,tpr,color="#2e6560"); axes[0].plot([0,1],[0,1],"--",color="gray")
        axes[0].set(xlabel="False positive rate",ylabel="True positive rate",title="ROC")
        precision,recall,_ = precision_recall_curve(p.y,p.p_resistant)
        axes[1].plot(recall,precision,color="#2e6560")
        axes[1].axhline(p.y.mean(),linestyle="--",color="gray")
        axes[1].set(xlabel="Recall",ylabel="Precision",title="Precision recall")
        observed,predicted = calibration_curve(p.y,p.p_resistant,n_bins=8,strategy="quantile")
        axes[2].plot(predicted,observed,"o-",color="#2e6560"); axes[2].plot([0,1],[0,1],"--",color="gray")
        axes[2].set(xlabel="Predicted resistance",ylabel="Observed resistance",title="Calibration",xlim=(0,1),ylim=(0,1))
        fig.suptitle(audit["evidence_status"].replace("_", " "),fontsize=12)
        fig.tight_layout()
        fig.savefig(out / "holdout_curves.png",bbox_inches="tight")
        fig.savefig(out / "holdout_curves.svg",bbox_inches="tight")
        plt.close(fig)
        pd.DataFrame({"fpr":fpr,"tpr":tpr}).to_csv(out / "roc_source.csv",index=False)
        pd.DataFrame({"precision":precision,"recall":recall}).to_csv(out / "pr_source.csv",index=False)
        pd.DataFrame({"predicted":predicted,"observed":observed}).to_csv(out / "calibration_source.csv",index=False)
        encoded = base64.b64encode((out / "holdout_curves.png").read_bytes()).decode()
        sections.insert(0, f'<figure><img alt="Holdout ROC precision recall and calibration curves" src="data:image/png;base64,{encoded}"><figcaption>Curves derived from retained holdout predictions. Research results only.</figcaption></figure>')
    title = "AMR research run"
    status = "TRAINING BLOCKED" if blocked else "AUDIT COMPLETE" if not metrics else metrics.get("interpretation_status", "RESEARCH RUN COMPLETE").replace("_", " ")
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{title}</title><style>body{{max-width:1120px;margin:40px auto;padding:0 24px;color:#243b39;background:#fafbf8;font:16px/1.55 Georgia,serif}}
    h1,h2{{font-family:Arial,sans-serif;line-height:1.25}}h2{{margin-top:36px}}table{{border-collapse:collapse;font:13px/1.4 Arial,sans-serif;max-width:100%;display:block;overflow:auto}}
    th,td{{border:1px solid #cbd5d1;padding:8px 11px;text-align:left}}th{{background:#e5eee9}}img{{width:100%;height:auto}}figure{{margin:28px 0}}code{{overflow-wrap:anywhere}}</style></head>
    <body><h1>{title}</h1><p><strong>{status} — {html.escape(audit['evidence_status'])}</strong></p>
    <p>This report evaluates software or exploratory measurements. It does not establish clinical suitability, biological causality, or independent replication.</p>
    {('<p><strong>Reason:</strong> '+html.escape(blocked)+'</p>') if blocked else ''}
    <p>Target data hash <code>{audit['input_sha256']}</code>. The input measurements and exclusions are retained beside this report.</p>
    {''.join(sections)}<h2>Interpretation limits</h2><ul>{''.join('<li>'+html.escape(x)+'</li>' for x in audit['limitations'])}</ul>
    <p>All computations run locally. No paid APIs, subscriptions or cloud compute are used by this software.</p></body></html>"""
    (out / "report.html").write_text(body,encoding="utf-8")
