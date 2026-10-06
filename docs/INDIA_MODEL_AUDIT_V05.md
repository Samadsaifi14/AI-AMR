# Audit against the supplied project brief and papers

## Main correction

The brief explicitly permits **MIC values or resistant/susceptible results per isolate per antibiotic**. The former MIC-only implementation was narrower than the intended study. Public Indian categorical AST can support a separate phenotype model without inventing MICs. This revision implements `representation: categorical_ast`, preserving nominal S, I, R, SDD and missing categories. The existing MIC representation and its validation rules remain separate.

The revised primary question is: **For an Indian clinical Gram-negative isolate, can its measured non-carbapenem AST panel predict reported meropenem R versus S?** Imipenem is a separate experiment. This is isolate-level prediction, not national resistance prevalence forecasting. NDM/OXA-48-like status defines a separately verified subgroup; gene calls never become primary model features.

## What the attached papers actually establish

| Source | Actual methods/endpoint | What to adopt | What cannot be transferred |
|---|---|---|---|
| Project brief, Dataset Scope and Modeling Approach | MIC **or** R/S phenotype inputs; carbapenem R/S target; mechanism annotation; source/region transfer | Explicit target, isolate-level panel, withheld answers, independent source testing | No required minimum accuracy or claim that the model is already validated |
| Valavarasu et al., Scientific Reports 2025, DOI [10.1038/s41598-025-14078-w](https://www.nature.com/articles/s41598-025-14078-w), Methods pp. 9–10 | ATLAS 917,049 isolates, 83 countries, 2004–2022; remove raw MICs and reshape drug/interpretation columns; S/I/R multiclass outcome; demographic/clinical features; 80:20 split; logistic, RF, XGBoost and other classifiers; balancing/tuning | Documented reported labels, explicit missingness, tree-model comparison, feature explanations, train-only balancing | Their reported AUC is not an estimate of our India-specific meropenem-panel accuracy. Their multiclass drug-row task is not identical to the brief's fixed-target, other-antibiotic panel task. The Methods do not establish an independent India-region validation of our model. |
| Emeraud et al., Nature Communications 2026, DOI [10.1038/s41467-026-72713-0](https://www.nature.com/articles/s41467-026-72713-0), Supervised ML design/Data preprocessing pp. 10–11 | Numeric disc diameters; target non-CPE or carbapenemase type; 50 stratified 70:30 splits; nested selection/RFE/tuning; train-fold resampling; blinded external 8,514-isolate validation | Isolate separation, train-only preprocessing/tuning, prespecified external challenge, mechanism/species stratification | CPE/type detection is a different endpoint from meropenem susceptibility. Disc diameters are not R/S categories or MIC concentrations. Carbapenem predictors useful for typing must not leak our target resistance phenotype. |

The Related Published Work document gives a different Scientific Reports link (`s41598-025-13452-8`) for the supplied Valavarasu paper; its actual DOI is `s41598-025-14078-w`. Its descriptions should not be used as substitutes for the full Methods. The provided Nature paper is MALCA, distinct from the separately mentioned CarbaDetector publication. Verify the remaining citations and epidemiological percentages before including them in a manuscript.

ATLAS raw data remain request-based through Vivli. MALCA's development/external isolate datasets are controlled-access under academic agreements; public source-data summaries do not replace the raw records. Neither attached PDF contains a downloadable India surveillance export that we can treat as approved training data.

## Current software audit and changes

| Finding | Revision/result |
|---|---|
| Numeric MICs required even when the brief allows categorical AST | Added separate nominal categorical representation; target label and predictors no longer need invented numeric concentrations |
| Only E. coli/K. pneumoniae supported by the previous pilot config | New Indian feasibility config explicitly includes the eight published Gram-negative species; species remains a baseline/stratum, not a core input |
| Unknown NDM/OXA-48 status could be mistaken for a producing cohort | Preserved unknown; separate `NDM_OR_OXA48` config admits no isolates without documented positive evidence |
| Geography not retained as a genuine split variable | Added `region` and `hospital_id` metadata and explicit region holdouts; source identity is still the publication/BioProject |
| Missing/SDD/intermediate could be collapsed into S | One-hot S/I/R/SDD/missing predictors; R-vs-S target excludes I/SDD/unresolved; EUCAST R-vs-nonR requires explicit semantics |
| Legacy evidence row said the new study was excluded from every model | App now distinguishes frozen MIC incompatibility from the new categorical model's eligible rows |
| Small-sample/failed-transfer warnings looked like software errors | Retained actual failures, with class counts and blocker reasons. These warnings describe missing research evidence. |
| XGBoost in brief but absent from browser pipeline | Existing candidate comparison includes Random Forest, histogram gradient boosting and logistic regression controls. Histogram gradient boosting is **not** XGBoost; no XGBoost result is claimed. A future native XGBoost comparison must use the same locked design. |

## Full Indian categorical curation

The complete Gheewalla et al. public Supplementary Data 1 (DOI [10.1038/s44259-026-00185-9](https://www.nature.com/articles/s44259-026-00185-9)) is retained: **266 isolates and 2,128 long-format observation rows**, eight drugs each, including explicit missing results. No row subsampling. Original BioSample/isolate identifiers and sheet row references are preserved. Dates use the workbook's Excel date encoding. Source is PRJNA1273658; Northern/Western are **regions within one publication**, not fabricated independent sources or hospitals.

The feasibility config includes E. coli, K. pneumoniae, A. baumannii, P. aeruginosa, P. mirabilis, B. cepacia, P. rettgeri and E. cloacae. There are 218 published Gram-negative isolates; 48 Gram-positive isolates are retained in the import and explicitly excluded from this configured scope. Species pooling here is an exploratory feasibility analysis, not evidence of a shared biological mechanism.

| Full-data experiment | Meropenem | Imipenem |
|---|---:|---:|
| Published isolates audited | 266 | 266 |
| Eligible target + ≥3 of six predictor results | 213 | 186 |
| Resistant / susceptible | 198 / 15 | 177 / 9 |
| Missing/unresolved target exclusions, supported scope | 1 | 32 |
| Insufficient predictor panel exclusions | 4 | 0 |
| Northern eligible R/S | 127 / 13 | 106 / 7 |
| Western eligible R/S | 71 / 2 | 71 / 2 |
| Internal training | Blocked: only 15 S | Blocked: only 9 S |
| Regional transfer, both directions | Both attempted and blocked | Both attempted and blocked |
| Independent-source external test | Unavailable: only one acquired study | Unavailable: only one acquired study |

Predictors are cefepime, ceftazidime, ciprofloxacin, gentamicin, amikacin and colistin categories. **All carbapenem predictors are blocked**, including the alternate target. Drug names and target are fixed before splits; no country, hospital, region, patient identifier, gene status or resistance-selection category enters the primary feature matrix.

The paper's selection favours resistant isolates. On the meropenem eligible cohort, always predicting resistant gives 198/213 = **92.96% accuracy, 100% sensitivity and 0% specificity**. That is not a useful resistance classifier. Oversampling 15 susceptible isolates does not create additional independent validation observations.

Per-isolate AST method details, standard/version, hospital and patient identifiers are not supplied in this workbook. `reported AST` describes the documented clinical AST reports; `UNSPECIFIED_REPORTED` explicitly avoids asserting CLSI/EUCAST harmonization. Gene states remain unknown, and the strict NDM/OXA-48 subgroup audit admits zero isolates. The broad Gram-negative cohort is therefore **not yet the brief's confirmed carbapenemase-producing cohort**.

## Implementation and reproducibility

```bash
python scripts/curate_india_categorical.py --data data/raw/india_npj_2026/supplementary_data_1.xlsx --out <new-curated-folder>
python -m amr_discovery validate --data <new-curated-folder>/observations.csv --config <new-curated-folder>/meropenem_config.json --out <new-meropenem-results>
python -m amr_discovery validate --data <new-curated-folder>/observations.csv --config <new-curated-folder>/imipenem_config.json --out <new-imipenem-results>
```

All internal/source/region/India attempts and blockers are retained under `results/india_categorical_v05_meropenem` and `results/india_categorical_v05_imipenem`. Browser users can select **Indian study — complete categorical AST collection**, audit the full data, select the target in JSON, and run all source/region attempts. Uploaded categorical data use the same long-format schema and `representation: categorical_ast`. Prediction forms offer categorical results for this representation and numeric values for MIC models.

The existing minimum class counts protect separation of training, calibration and testing; they are software floors, not a sufficient sample-size justification. They have not been reduced to manufacture a model or favourable result. Resampling, if introduced later, belongs inside training folds only. Patient/duplicate groups and hospital/time boundaries must be resolved before external accuracy claims.

## Study design needed to complete the brief

1. Acquire representative Indian isolate-level AST panels with both R and S outcomes, hospital, region, time and de-identified patient/duplicate IDs; preserve selection criteria and interpretation versions.
2. Verify measured NDM/OXA-48-like annotations with exact AST–gene identity joins; keep a broad surveillance cohort and a prespecified positive-mechanism cohort distinct.
3. Prespecify species/target/panel, endpoint handling, harmonization rules, primary metrics and sample-size/precision requirements. Use separate meropenem and imipenem models.
4. Fit preprocessing and optional class balancing only inside development folds. Compare logistic controls, Random Forest and boosted trees; select and calibrate on development data only.
5. Freeze the model and operating point. Evaluate a new hospital/time/source cohort untouched by selection; report sensitivity, specificity, AUROC, precision, calibration, counts, subgroup coverage and uncertainty.
6. Treat cross-region results from one study as regional transfer evidence, not independent-source or nationwide clinical validation. If a model is revised after failures, acquire another untouched external test.

This revision corrects the model specification and makes the complete public categorical dataset usable for audit. It does not make the existing small, resistance-selected data sufficient for an India-wide accuracy claim.

## Verification record

50 native Python tests passed, including categorical training/prediction, label-leakage checks, nominal missing/SDD handling, region separation and zero-eligible audit rendering. Static asset/module/link/syntax checks passed. The current pinned browser-runtime source challenge retained all 165 test isolates: AUROC 0.754437, sensitivity 0.034483, specificity 0.970588, FN=28, FP=4, model boost_leaves7. It still fails the operating point. Exact configuration/environment and metrics are retained in `BROWSER_SOURCE_V05_RESULT.json`; the v0.2 browser result remains labelled as archived. No test-selected threshold changes or winner claims were made.
