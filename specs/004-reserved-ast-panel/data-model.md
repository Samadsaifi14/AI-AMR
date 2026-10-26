# Data model

## Source workbook row

Represents one supplied BioSample-antibiotic measurement.

- BioSample accession: stable identifier repeated across drug rows; used as `isolate_id`.
- Species: exact recorded scientific name.
- Drug: normalized through a reviewed alias mapping; original spelling retained in the import manifest.
- Reported phenotype: original susceptible/resistant text, preserved as a measured categorical AST result.
- MIC: original numeric value, comparison operator and `mg/L` unit; never converted to an exact value when censored.
- Platform and vendor: platform retained in `platform`; vendor retained in the normalized source metadata/manifest.
- Standard and version: reported `CLSI`; version remains blank because the workbook does not state one.
- Location and collection date: country parsed only where explicitly stated in the location; create date is not used as collection date.
- Source trace: accession plus source worksheet/row pointer.

## Canonical AST observation

One normalized row per source observation. Required fields are the existing canonical schema: `isolate_id`, `source_id`, `species`, `drug`, `measurement`, `operator`, `units`, `method`, `standard`, `standard_version`, `reported_sir`, and `evidence_class`. Optional fields include accession, source row, country, platform, specimen, host, lab and patient identifiers.

Constraints:

- Source/isolate/drug keys must be unique after import; conflicts stop training and remain visible.
- `measurement` and `operator` preserve the source value and censoring sign.
- Missing categories are blank/missing, never susceptible.
- Unknown provenance uses the project’s recognized unknown marker rather than a fabricated cohort or laboratory identity.

## Target experiment

One target drug, one eligible isolate row, configured non-reserved predictor panel, one train/test partition, and corresponding prediction evidence.

- Targets: meropenem, imipenem, colistin, ceftazidime-avibactam.
- Predictors: ceftriaxone, cefepime, ciprofloxacin, gentamicin, amoxicillin-clavulanate, cefotaxime, piperacillin-tazobactam; optional species indicator.
- Reserved drug observations are never predictors.
- Group identifier connects duplicate/patient-linked isolates for a single partition assignment.
- Metrics use the held-out target label; absent class denominators are `null`/unavailable.

## Import manifest

Input and output SHA-256, source and normalized row counts, source column mapping, included/excluded row counts, unknown metadata inventory, drug mapping and import warnings. The manifest is local with the private input.
