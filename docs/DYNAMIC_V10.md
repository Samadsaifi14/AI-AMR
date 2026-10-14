# Dynamic AMR experiments and threshold-transfer correction

The workspace now exposes the antibiotic panel, minimum measured panel, training coverage, optional maximum panel size, species input, sensitivity goal, threshold method and research decision mode as editable controls. Changing a setting invalidates the old session prediction form; **Train & evaluate** fits a fresh experiment. No manual freezing step is required. The default public preset is the broad dynamic framework. The ten-drug cap has been removed; all adequately covered, non-redundant planned antibiotics are retained by default. The reviewed input schema still excludes the target and molecular labels from the predictor matrix.

## Research predictions remain available

`decision_policy: research_binary` produces binary research predictions even when operating targets fail. The output remains clearly labelled exploratory and the failed validation status and actual errors are retained. Users can choose the legacy validation/uncertainty gate explicitly. Missing/invalid measurements, unsupported units and target leakage are still rejected. Removing those checks would change the scientific question or misrepresent the observations.

External evaluation accepts `external --run RUN --data DATA --out OUT`, automatically recording the selected run's evaluation snapshot. A separate freeze command is unnecessary. `snapshot-external` is available for reviewers; `freeze-external` remains a compatibility alias for existing scripts. Snapshots are audit records, not locks on creating new runs. External labels never retrain or recalibrate a model while that model is being evaluated. Each new dataset/design can be trained as a new experiment; previously evaluated data cannot be described as a fresh independent test.

## Threshold-transfer failure

The v0.9 source challenge's calibration-only threshold was 0.972 and missed all 29 resistant isolates. `threshold_policy: source_robust` computes sensitivity thresholds from training out-of-fold predictions and calibration outcomes, including each development source with positive isolates. It uses the lowest such threshold to protect lower-scoring development sources. Thresholds and source denominators are recorded in `development_thresholds.csv` before test scoring. Sparse source estimates are visible; the method does not guarantee performance on a new source or make confidence intervals disappear. A reversed sigmoid calibration slope blocks source-robust fitting because its score ordering would be inverted.

The sensitivity-first preset requests 100% development sensitivity and selects the candidate with greatest development OOF specificity at that goal. It does not select thresholds from final-test outcomes. RF/XGBoost are the native candidates; the browser runs actual RF and has no XGBoost engine. The final preset retains the full usable panel without the old top-ten restriction.

## Recorded retrospective result

On the already examined PRJNA278886 source challenge (165 isolates, 29 R and 136 S), the full-panel native model has AUROC 0.9649, sensitivity 26/29 = 89.66%, specificity 129/136 = 94.85%, 3 FN and 7 FP. This reduces the original missed resistance count from 29 to 3; it does **not** eliminate all missed resistance or achieve the requested sensitivity target. Development selected XGBoost depth 2; all 15 planned antibiotics passed training selection. `error_review.csv` retains every misclassified isolate for review. No isolate was removed or relabelled to improve the metric.

The first source-robust cap-ten design also produced 3 FN / 7 FP. Its complete all-source evaluation obtained 0 FN / 9 FP internally, 0 FN / 5 FP for PRJNA288601, and 0 FN / 13 FP for PRJNA308116 (zero specificity). The final full-panel design has 0 FN / 8 FP internally (85.19% specificity), 0 FN / 5 FP for PRJNA288601 (61.54% specificity), and 0 FN / 5 FP for PRJNA308116 (61.54% specificity). The original source still has 3 FN / 7 FP. All sixteen experiments, including twelve class-count/India blockers, are retained beside the source result. Source dependence and false-positive cost must be reported together. A repeated, inspected cohort remains retrospective exploratory evidence, even if its discrimination improves. No India-wide or clinical accuracy is established.

## Native commands

```bash
python -m pip install -e '.[xgboost]'
python -m amr_discovery run --data observations.csv --config configs/framework_native.json --out results/new-experiment
python -m amr_discovery validate --data observations.csv --config configs/framework_native.json --out results/new-suite
python -m amr_discovery external --run results/new-experiment --data new-independent-observations.csv --out results/new-external-evaluation
```

The detailed metrics, source summaries, selection decisions and runtime identities are downloadable with the source. The app starts with dynamic research output enabled; the UI never turns a failed sensitivity target into a validation success.

## Browser runtime difference

The final browser RF preset selects forest depth 8 on its pinned runtime, producing 14 TP / 15 FN and 132 TN / 4 FP on the same 165-isolate source challenge (48.28% sensitivity, 97.06% specificity). This is worse sensitivity than the native XGBoost result. The browser cannot run native XGBoost; do not describe the native result as browser performance. The browser dynamic training and ungated research-prediction flows passed runtime checks. Native Python is currently the stronger evaluated route. Neither route eliminates every false negative.
