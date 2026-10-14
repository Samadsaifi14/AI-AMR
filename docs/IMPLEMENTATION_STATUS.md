# Implementation status

The v0.1 release executes local data acquisition, QC, grouped model selection, calibration, holdout evaluation, deferral analysis and offline reporting. The original implementation plan is included for the full research scope.

## Current study

The acquisition query captures publicly indexed human-associated K. pneumoniae BioSamples with antibiograms. Human metadata are checked again during cohort construction. Query expansion also retrieves related species, which are excluded unless explicitly eligible. This is a public convenience collection, not a population prevalence survey.

The primary public pilot uses a declared five-drug panel and reported CLSI R versus S. It excludes I and other unresolved categories and is not breakpoint-harmonized. Mechanisms are unknown and patient grouping is unavailable. Internal isolation uses unique BioSample IDs; it cannot rule out repeated patients, outbreaks or related strains.

The BioProject holdout is an exploratory source-transfer experiment selected from feasibility counts before viewing its model performance. Shared laboratories, recruitment overlaps, patient duplicates and lineage dependence are not independently audited. Its results must not be described as completed external clinical validation.

## Implemented scientific checks

Measurement bounds, conflicting repeats, target leakage, unsupported species, human host eligibility, mechanism evidence, observed feature minimum, class variation and connected duplicate/patient groups. Metadata are never included in the phenotype predictor. Species and missingness are separate control models.

Model hyperparameters are compared using grouped inner folds on training data. The selected model is calibrated on a separate development subset. Operating thresholds use the same calibration subset; this can overfit development operating-point estimates. The holdout remains untouched for model selection. Bootstrap units are available connected groups, otherwise isolates, not sites; site-level uncertainty requires additional clusters and analysis.

## Deferred research work

- Independent NDM/OXA-48 assay evidence and typing-selection audit.
- Versioned, reviewed real breakpoint rules and richer boundary semantics.
- Independent collection validation with recruitment, patient and lineage overlap checks.
- Automated leave-country-out/source-to-source matrix and paired uncertainty for model differences.
- Species-adjusted biological interaction tests, multiplicity correction and replication.
- Nested automated panel selection, missing-panel stress tests and source reweighting.
- Calibration intercept/slope and prospective silent monitoring.
- Real-time result-availability timestamps and measured workflow value.
- Combination MICs, zone-diameter models, source-specific ATLAS/Vivli adapters.
- A user interface for sample predictions; this release produces research reports only.

No code should present these deferred items as completed. Negative or uncertain findings remain reportable. No model generated here is a replacement for laboratory AST or a demonstrated biological discovery.
