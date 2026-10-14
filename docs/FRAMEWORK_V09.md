# Collaborator MIC framework implementation (archived v0.9 design)

See [DYNAMIC_V10.md](DYNAMIC_V10.md) for the current dynamic settings and source-robust threshold policy.

The endpoint is antibiotic-specific resistance (R vs S by default), not carbapenemase classification. One eligible isolate becomes one row. The target's measurement/category and combinations containing that antibiotic are excluded from predictors. Mechanisms NDM, OXA-48-like, KPC, VIM and IMP are evidence-backed annotations for subgroup analysis; unassayed calls remain unknown. Geography, source, laboratory, identifiers and molecular annotations never become core predictors. Species is an optional explicitly encoded input, with a species-only control.

## Broad candidate panel

`configs/framework_native.json` prespecifies carbapenems other than the target, cephalosporins, aztreonam, aminoglycosides, fluoroquinolones, colistin and tigecycline. Add or remove reviewed antibiotics in the configuration; do not select a panel using final-test performance. The framework accepts explicitly supported antibiotic targets beyond meropenem/imipenem. The legacy mode keeps its previous restrictions so archived experiments remain reproducible.

Combination products need `combination_reviews[drug]` with `reviewed: true`, a citation and positive `fixed_inhibitor_mg_l`. Each observation must document that same concentration in `fixed_inhibitor_mg_l`. Only a scalar MIC of the antibacterial component in supported concentration units is accepted. Ratio-form MICs remain rejected. Combinations containing the target antibiotic cannot be predictors. Unsupported panels, drugs, tests or units must be curated explicitly.

## Training and validation

Patient/duplicate groups are separated into training, calibration and test partitions. In every development fold, the DrugPanelSelector fits coverage filtering (default at least 20%), observed-pair Spearman redundancy filtering (default absolute correlation at least 0.95, minimum ten paired bounds) and, if required, random-forest ranking of whole drug blocks (default ten drugs maximum). Imputation and species encoding are then fitted on that same fold's training rows. Categorical AST does not use numeric-bound correlation filtering. Coverage filtering is based on training-fold coverage, not guaranteed cross-source coverage. Correlation uses bounds and is an exploratory redundancy heuristic for censored measurements.

The selected candidate is refitted using only the training partition; calibration and operating thresholds use the calibration partition. The antibiotic list, filter decisions, configuration, runtime versions and threshold are frozen before final test scoring. Calibration/test data never choose the selected features. The recorded minimum observed count is checked against the planned input panel. Median imputation is a numerical model operation; it never turns an untested antibiotic into an observed laboratory value. Missingness and censoring flags remain part of each drug block.

RF and actual XGBoost are the primary native candidates. Set `model_families` to compare additional logistic or histogram boosting models explicitly. XGBoost is not available in the pinned browser runtime; the browser preset explicitly runs RF only and never substitutes another engine under an XGBoost label.

Source/country/region/laboratory holdouts are retrospective transport challenges. They are distinct from the independently acquired frozen-model external workflow. Repeated examination of existing cohorts does not create a new independent test. The current India cohorts remain validation-limited; this implementation does not establish India-wide accuracy or promise improved specificity.

## Run locally

```bash
python -m pip install -e '.[xgboost]'
python -m amr_discovery audit --data observations.csv --config configs/framework_native.json --out results/framework-audit
python -m amr_discovery run --data observations.csv --config configs/framework_native.json --out results/framework-run
python -m amr_discovery validate --data observations.csv --config configs/framework_native.json --out results/framework-all-sources
python -m amr_discovery freeze-external --run results/framework-run --out results/framework-external-protocol.json
python -m amr_discovery external --protocol results/framework-external-protocol.json --data independent-india-observations.csv --out results/framework-external
```

For clinical-label comparability, pin the documented AST standard/version and use strict provenance or reviewed breakpoint rules. Exploratory unversioned submitter labels are visible limitations, not harmonized truth. Disk zones are not converted to MICs. Actual laboratory dilution ladders are validated when supplied; no arbitrary correction factor is learned. The existing external protocol defaults to India, freezes artifacts, rejects recorded identity overlap and never refits the model.

## Outputs

- `cohort.csv`, `exclusions.csv`, `panel_coverage.csv`, `audit.json`: isolate-level matrix, eligibility decisions and descriptive source coverage.
- `feature_selection.json`, `model_lock.json`, `split_manifest.csv`: frozen training selection, runtime, thresholds and grouped partition provenance.
- `development_cv.csv`: training-only RF/XGBoost comparison.
- `test_predictions.csv`, `metrics.json`, `subgroup_metrics.csv`: held-out predictions, exact/cluster intervals and mechanism/source/species strata.
- `grouped_permutation_importance.csv`: ranked antibiotic reliance with all columns for each drug permuted together; post-test diagnostic only, never fed back into feature selection.
- `report.html`, curve figures and source tables: reproducible evidence to review.

In the web app, choose **Load broad MIC framework**, select an antibiotic endpoint, audit the panel and then train or validate all sources. Downloaded source includes both native and browser presets. The native preset includes actual XGBoost; browser execution rejects an explicit unsupported XGBoost request.

Implementation follows the supplied `AMR_ML_Model_Framework_for_CS_Collaborators.docx`, resolving its inconsistent mechanism-classification wording in favour of its explicit resistance-prediction scope. No new literature performance claim is inferred from this software implementation.
