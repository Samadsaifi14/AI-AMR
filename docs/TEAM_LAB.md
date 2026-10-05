# Team lab: browser training and India validation

Live app: https://amr-research-lab.samads14122003.chatgpt.site

The app uses the same Python data, modeling and reporting modules as this package. It runs in a browser worker, with Pyodide 0.29.3. Uploaded CSV data, models and annotations remain in the device's in-memory filesystem. Scientific runtime packages download from jsDelivr; source and example public/synthetic datasets are served by the app. No paid model API or GPU service is called. Save your experiment ZIP before closing or refreshing the tab. There is no central database, experiment synchronization or persistent team account: share exported files through your team's existing approved file-sharing service.

## Run tasks in order

1. Test the software with the synthetic fixture. Never interpret its accuracy as biological evidence.
2. Audit your source-derived long-format CSV. Review each exclusion, species, outcome class, standard/version, missing panel and patient/source identity.
3. Pre-specify the model configuration and operating sensitivity target. Use source, country or temporal holdout when sufficient outcomes exist. Internal splitting alone does not establish site generalization.
4. Train and inspect source tables, baseline comparison, calibration, bootstrap intervals and false negatives. Model selection is grouped OOF log loss; calibration and threshold share a separate development subset. Test labels are not used to select models or thresholds.
5. Export the full ZIP and assign an independent reviewer. Record the input hash, split hash, environment, selection, threshold and limitations. A new configuration on the same test set is exploratory; reserve fresh data for confirmatory evaluation.
6. Test an isolate using independently measured non-carbapenem MICs. Models with failed operating points or synthetic evidence are research demonstrations only.
7. Explore documented gene and geographic annotations on training isolates only. Unknown gene calls are excluded from denominators; proximity does not imply transmission. These tables do not feed the deployed predictor. Their predictive integration requires matched data and an independently held-out ablation experiment.
8. Curate Indian susceptible and resistant isolates across hospitals/time periods before any India accuracy claim. Geography is collection context, not a person's genetics or ethnicity.

## Runtime verification

The exact pinned Pyodide runtime was tested under Node without a browser UI. End-to-end training/report/export, research prediction, unknown-call exclusion and India training blocking passed. The public source-held-out browser-runtime run selected boost_leaves15: n=165, AUROC=0.735928, sensitivity=0, specificity=0.992647, 29 false negatives. The earlier local run selected forest_depth4: AUROC=0.781440, sensitivity=0, specificity=1. Different tested package versions can change selection and outputs; the environment is included in model_lock.json. Both operating points failed.

Browser Python: 3.13.2; numpy 2.2.5; pandas 2.3.3; scikit-learn 1.7.0; matplotlib 3.8.4; joblib 1.4.2; threadpoolctl 3.5.0; scipy 1.14.1. A desktop browser is recommended. File upload limit: 10 MB; gene analysis: 100 genes / 10,000 isolates; spatial analysis: 1,000 training locations. Use the local package for larger datasets. No browser visual or click-through QA was available in this environment; JavaScript syntax, asset links and actual Python runtime were checked.

Joblib files are trusted research artifacts from your own run. Do not load arbitrary model files received from unknown sources. Browser-trained artifacts are not guaranteed portable to a different Python/sklearn runtime; recreate from the recorded configuration and data.

## New Indian evidence

The public India BioSample query retrieved two records and 29 AST rows. One resistant isolate passed the panel audit; no susceptible isolate passed. Training is blocked by class/sample gates.

Public supplements from the 2026 surgical ICU study (doi:10.1038/s41467-026-74764-9) were downloaded with hashes. Its patient AST sheet has 122 rows: 115 R, 6 S, 1 I for meropenem. Curated candidates comprise 854 observations, with 114 exact AST-to-WGS taxonomy matches. The gene table provides 2,162 unique raw positive gene calls. AMRFinder and AST IDs use different punctuation: 114 one-to-one numeric-ID correspondences were proposed for human review, not silently admitted as verified matches. Missing gene hits do not establish absence. Candidate observations remain quarantined because the examined source tables/methods did not establish the interpretation standard/version and MIC units. The selected single-hospital cohort does not represent India.

Recreate curation:

```bash
python -m pip install openpyxl
python scripts/curate_india_icu.py --raw data/raw/india_surgical_icu_2026 --out data/curated/india_surgical_icu_2026_NEW
```

Review candidate_identity_mapping_REVIEW_REQUIRED.csv and obtain verified AST interpretation information before merging. Keep geography as observed metadata; no patient coordinates or calendar dates were inferred.

Local topology command:

```bash
python -m amr_discovery topology --run results/YOUR_RUN --genes gene_calls.csv --geography documented_locations.csv --out results/YOUR_TOPOLOGY
```

Gene CSV: isolate_id,gene,status,evidence_reference. Geographic CSV: isolate_id,latitude,longitude,collection_date,location_reference. Dates must be complete YYYY-MM-DD; no centroid substitution. Edges are exploratory, within 25 km and 30 days by default.
