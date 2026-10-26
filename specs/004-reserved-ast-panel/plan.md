# Implementation Plan: Reserved-antibiotic AST prediction

## Summary

Add a local Excel-to-canonical-AST import path and a bounded exploratory training mode for a grouped 70/30 holdout. Train one model per reserved target from only the user’s non-reserved panel, using the existing canonical `amr_discovery` functions in CLI and browser runs. Keep uploaded inputs and trained runs under ignored local private storage.

## Technical Context

- **Language/runtime**: Python 3.11+ for canonical analysis; existing Pyodide browser runtime uses the same model module.
- **Existing code**: `amr_discovery/data.py` builds target-specific cohorts and enforces target exclusion; `amr_discovery/modeling.py` trains/evaluates; `browser_bridge.py` wires the browser to those functions; `web/app.js` stores the user configuration and session state.
- **Workbook input**: `.xlsx`, long format, one row per BioSample-antibiotic observation. The local adapter uses `openpyxl`; normalized CSV remains the browser upload format.
- **AST representation**: Reported S/R categories for the initial model. Preserve MIC values, operators and units in normalized source rows. Do not recalculate categories or erase censoring.
- **Data protection**: Keep the workbook, normalized CSV, manifests and fitted artifacts under `data/private/`; commit only code, configuration templates and documentation.
- **Validation**: Add parser, leakage, split and small-sample workflow coverage. Run the repository Python suite, static build, web tests and pinned Pyodide runtime checks.

## Constitution Check

1. **Measured inputs and provenance**: Pass. Import retains reported data and leaves unknown source/patient/lab/version/date fields empty.
2. **Training/test separation**: Pass. The target is excluded; grouping is checked; preprocessing is fit only on training data; test outcomes do not tune the estimator.
3. **Shared canonical implementation**: Pass. The browser bridge calls the same Python training function; the importer only converts workbook structure.
4. **Clear guidance and limits**: Pass. Results are stamped exploratory, retain error counts and state that clinical validity is not established.
5. **Private inputs and models**: Pass. The workbook and outputs stay in ignored `data/private/` and are excluded from static assets and exports.
6. **Verification**: Pass when completed. Required Python, build, UI and runtime checks will be run and recorded.

## Design Decisions

- **One target per experiment**: Meropenem, imipenem, colistin and ceftazidime-avibactam use separate configurations and outcomes.
- **Fixed predictor panel**: ceftriaxone, cefepime, ciprofloxacin, gentamicin, amoxicillin-clavulanate, cefotaxime and piperacillin-tazobactam. Unmeasured predictors are encoded as missing, never susceptible.
- **Small-sample exploratory mode**: A single prespecified regularized logistic estimator uses the grouped 70/30 split. This avoids cross-validation and threshold tuning on tiny resistant groups. The run is not treated as validated or clinically deployable.
- **Combination AST**: Reported categorical results remain usable under the source-reported standard; MIC combination ratios still require the existing review contract.
- **Missing targets**: Produce a blocked/unavailable result with counts. Do not fit a placeholder target.
- **Unknown provenance**: Use an explicit unknown-source token handled as unknown by the shared validator. Keep the source accession in the accession trace, do not convert submission/create date into collection date, and do not infer a lab identity from platform.

## Project Structure

- `amr_discovery/modeling.py`: grouped exploratory 70/30 fitting, predictions, metrics and run artifacts.
- `amr_discovery/data.py`: permit the reviewed categorical combination panel without requiring MIC-ratio metadata; keep MIC checks intact.
- `amr_discovery/workbook.py`: workbook column mapping and normalized observation generation.
- `amr_discovery/__main__.py`: `import-asts-workbook` CLI command.
- `configs/reserved_ast_exploratory.json`: shared target/panel template; target selectable per experiment.
- `web/index.html`, `web/app.js`: target option and one-click reserved panel configuration; continue accepting normalized CSV.
- `web/guide.html`: workbook conversion, training sequence and limits.
- `tests/`: importer, panel, grouping, missing target, metrics and browser contract coverage.
- `specs/004-reserved-ast-panel/`: specification, design, tasks and verification evidence.

## Risks and Mitigations

- Rare classes can yield a test fold with no resistant outcomes. Show sensitivity as unavailable rather than zero and preserve the count.
- A 70/30 split can vary for group-linked records. The split records actual counts and never moves a linked group across partitions.
- Unknown provenance can look like a meaningful source if filled with a fabricated value. Use the repository’s explicit unknown sentinel and keep source holdout unavailable.
- Combination MIC methods can depend on inhibitor concentration. This change permits only already-reported categorical AST; MIC comparability checks remain unchanged.

## Implementation Sequence

1. Implement and verify workbook normalization to canonical observations.
2. Add target-specific small-sample grouped fitting and artifacts to canonical model code.
3. Add target/panel configuration and browser controls that call the canonical implementation.
4. Update the guide and quickstart; run all required checks and a private local run on the supplied workbook.

## Out of Scope

- Publishing the supplied measurements, source-derived fitted models or run outputs.
- Inferring CLSI version, patient linkage, study identity, or lab-specific MIC corrections.
- Establishing Indian or clinical accuracy, optimizing against the held-out results, or automatically promoting any model.
- Training a target with no labels or inventing labels for missing antibiotic rows.
