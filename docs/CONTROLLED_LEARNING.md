# Controlled learning for AI AMR

New verified observations can train a new research version. The system does not learn from its own predictions, replace the current model automatically, or convert an internal accuracy score into clinical validation. The antibiotic being predicted is excluded from the predictor panel. Feature selection, imputation, model comparison and calibration remain inside development data.

## Browser workflow

Choose Your team's CSV and select the file. For an original NCBI AST export, use Import NCBI AST export. The importer matches accession, species, drug, standard, reported phenotype, MIC and censoring against the existing documented public acquisition. Unmatched observations stay quarantined. Submission date is not used as collection date. A platform name does not establish the laboratory method or standard version.

Review the target, interpretation standard, available predictor panel, and audit exclusions. Standard versions missing from a public export permit exploratory analysis only. CLSI and EUCAST labels are filtered separately, not pooled or silently reinterpreted. Save the imported CSV and manifest. Train and download the experiment ZIP: it contains the model, source hashes, configuration, feature selection, holdout predictions, errors, uncertainty, release evidence and a training-only reference profile.

The controlled learning section displays the new version and keeps up to 20 version summaries on your device. Browser history does not contain uploaded observations or serialized models. Full model reproducibility requires the experiment ZIP. Clearing browser data clears history. Uploaded data is not sent to the server.

To inspect a new canonical batch while preserving your current session model, select the incoming file in Check incoming data before retraining. The drift report compares it with fixed bins from the training partition. PSI of 0.2 or a missingness change of 0.10 triggers review. These descriptive heuristics do not guarantee safety or diagnose why a distribution changed. Current drift checks operate on eligible labeled cohorts; unlabelled surveillance is not supported by this workflow. New data does not trigger background fitting. To retrain, prepare and audit the batch and start a new experiment.

## Native versioned training

Use a de-identified private directory and install the documented dependencies plus the native XGBoost extra. Models are executable joblib serialization: load only trusted local models, never downloaded untrusted joblib files.

```bash
python -m pip install -e '.[xgboost]'
python -m amr_discovery import-ncbi-export --data asts.csv --reference documented_observations.csv --out data/private/imported
python -m amr_discovery learning-train --data data/private/imported/observations.csv --config reviewed_config.json --out data/private/version1 --registry data/private/registry.json
```

For the next reviewed batch, combine it with the original development observations using prepare-batch. Exact repeated rows are removed; conflicting observations are rejected, not overwritten. Preserve the original endpoint, configuration and untouched source boundary. Supply the previous version ID with --parent to record lineage and compute drift. A changed endpoint or design starts a new lineage.

```bash
python -m amr_discovery prepare-batch --data new_observations.csv --base development_observations.csv --out data/private/combined
python -m amr_discovery learning-train --data data/private/combined/observations.csv --config reviewed_config.json --out data/private/version2 --registry data/private/registry.json --parent VERSION1
python -m amr_discovery learning-compare --registry data/private/registry.json --champion VERSION1 --challenger VERSION2 --out data/private/paired_comparison.json
```

Comparison scores both frozen versions on the champion's same holdout and rejects known identity overlap with either version's development rows. It is retrospective comparison, not independent clinical evidence. Never move inspected test rows into development to improve the comparison score. Repeated internal splits may move rows between partitions; use a prespecified source boundary for meaningful comparisons across data updates.

## Reserve independent evaluation before learning

Reserve a fresh measured cohort before adding new training data. Its recorded isolate, patient and duplicate identities and study sources are excluded from future registered training. Missing patient identifiers limit the overlap check; biological independence must be reviewed. Reserve uses the reviewed label configuration; breakpoint-based reservations are currently unsupported, so use documented reported-label evaluation data.

```bash
python -m amr_discovery learning-reserve --data independent_observations.csv --config reviewed_config.json --registry data/private/registry.json
python -m amr_discovery learning-evaluate --registry data/private/registry.json --version VERSION1 --data independent_observations.csv --out data/private/independent_evaluation
```

Evaluation never refits, calibrates or searches thresholds. A reserved file can be inspected once through this registry. Known identities and sources must be absent from all registered versions. Once outcomes have been inspected, use fresh independent data for a new clinical evidence claim. A registry is a local auditable workflow, not a tamper-proof governance service; keep it under controlled access with backups.

Release review requires measured independent data, lower 95% sensitivity bound at least 0.95, lower 95% specificity bound at least 0.50, finite Brier score, and complete recorded patient, source, laboratory, QC and standard-version metadata. These are provisional conservative research gates, not clinical acceptance criteria agreed by clinicians. Finite Brier score records calibration evidence; it does not mean calibration is adequate. Exact intervals assume independent isolates and cannot repair unrecorded clustering.

```bash
python -m amr_discovery learning-promote --registry data/private/registry.json --version VERSION1
```

Promotion is explicit and research-only. It is blocked without passing independent evidence. No command establishes clinical suitability. Prospective evaluation, intended population/use, clinical oversight, reviewed laboratory provenance and agreed acceptance criteria remain necessary. The live website hosts code, not a centrally deployed patient-data-trained model. The legacy root API is unconfigured and returns HTTP 503 for predictions; its former fixed mechanism probabilities and unreviewed breakpoint shortcut have been removed. It is not the website runtime.

## Reference methods

The supplied collaborator framework specifies broad AST panels, RF/XGBoost, training-only feature selection, target exclusion and independent-source evaluation. MALCA (Emeraud et al., Nature Communications 2026, doi:10.1038/s41467-026-72713-0) uses disc-diffusion diameters for CPE detection and carbapenemase typing, a different endpoint. Its performance is not attributed to this model. TRIPOD+AI (Collins et al., BMJ 2024;385:e078378, doi:10.1136/bmj-2023-078378) informs transparent reporting of development and evaluation evidence.
