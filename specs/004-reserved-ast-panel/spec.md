# Feature Specification: Reserved-antibiotic AST prediction

**Feature Branch**: `004-reserved-ast-panel`

**Created**: 2026-10-26

**Status**: Draft

**Input**: Convert the supplied AST workbook into the existing AMR research workflow and train target-specific exploratory models using the selected non-reserved antibiotics to predict reserved-antibiotic results.

## User Scenarios & Testing

### User Story 1 - Import the AST workbook (Priority: P1)

A project user selects the supplied Excel AST workbook and creates a canonical observation file for the existing model. The import retains each isolate, organism, antibiotic, reported category, MIC bound and unit, platform, standard, location and accession trace. It does not invent missing collection dates, source studies, standard versions, laboratory IDs or patient links.

**Why this priority**: The workbook must enter the existing model without losing its isolate-to-antibiotic relationships or changing the reported measurements.

**Independent Test**: Import a workbook containing repeated BioSample IDs across different drugs and compare the canonical rows, metadata and source-row references with the workbook.

**Acceptance Scenarios**:

1. **Given** a valid workbook, **When** the user imports it, **Then** every source row is retained once with its original BioSample and antibiotic pairing.
2. **Given** an unsupported drug or invalid reported category, **When** the user imports it, **Then** the importer records the issue without silently mapping it to another antibiotic or phenotype.
3. **Given** absent source, collection-date, patient, lab or standard-version metadata, **When** the import completes, **Then** those fields remain explicitly unknown or blank.

### User Story 2 - Train reserved-antibiotic models (Priority: P1)

A user selects one reserved antibiotic as the target and trains an exploratory model from the defined non-reserved predictor panel. The target result and other reserved-antibiotic results never become predictors. Records are partitioned by isolate group into approximately 70% development and 30% test, and the exported report compares each prediction with the recorded target result.

**Why this priority**: This is the user’s initial modeling objective: estimate reserved-drug susceptibility from the measured non-reserved-drug panel.

**Independent Test**: On a fixture with paired target and predictor measurements, inspect the configuration, model matrix, split manifest and held-out predictions to confirm target exclusion, group separation and matching target labels.

**Acceptance Scenarios**:

1. **Given** a target with usable measured results, **When** the user trains, **Then** only the configured non-reserved antibiotics and optional organism identity enter the predictor matrix.
2. **Given** multiple drug rows for one isolate or linked group, **When** the data is split, **Then** all rows for that group remain on one side of the 70/30 boundary.
3. **Given** a requested target or predictor with no usable observations, **When** the user audits or trains, **Then** the report says that target or predictor is unavailable and does not fabricate labels.
4. **Given** rare target classes, **When** a split cannot contain both classes in development, **Then** the run reports the limitation and retains any computable single-class metrics as unavailable where appropriate.

### User Story 3 - Review and export each run (Priority: P2)

A user reviews the input accounting, target-specific class counts, split membership, error counts and run limitations, then exports the complete experiment for local reuse.

**Why this priority**: The user needs to understand which target models actually ran and reproduce each result.

**Independent Test**: Train a fixture and verify that the downloadable evidence includes configuration, input hash, train/test manifest, predictions, metrics and report.

**Acceptance Scenarios**:

1. **Given** a completed target run, **When** the user exports evidence, **Then** the bundle identifies the input and configuration hashes and contains the matching predictions and split manifest.
2. **Given** an exploratory run, **When** the result is shown, **Then** it remains explicitly marked exploratory and never states clinical validation.

## Edge Cases

- The workbook contains cefotaxime and ceftazidime-avibactam as requested but the supplied file has no rows for either drug.
- A requested reserved target can have zero measured outcomes or too few labels to distribute across development and testing.
- An isolate has only some predictor drugs measured; untested categories remain missing and are not imputed as susceptible.
- Different organism names, whitespace, malformed MIC values, duplicate isolate-drug rows, unsupported labels or invalid operators appear in the workbook.
- A patient or duplicate-group link joins otherwise distinct isolate IDs; all linked isolates must remain in one partition.
- A workbook contains records for other Klebsiella species; the configured cohort includes only *Escherichia coli* and *Klebsiella pneumoniae* unless the user changes the reviewed species scope.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST import the supplied workbook format into the existing canonical AST observation schema.
- **FR-002**: The system MUST preserve BioSample/isolate identity across antibiotic rows and retain the original MIC value, censoring operator, unit, reported phenotype, species, platform, standard, location and source-row trace.
- **FR-003**: The system MUST leave unsupported or unavailable provenance fields unknown rather than infer them from submission dates, geography, platform or accession format.
- **FR-004**: The system MUST support the user’s predictor panel: ceftriaxone, cefepime, ciprofloxacin, gentamicin, amoxicillin-clavulanate, cefotaxime and piperacillin-tazobactam.
- **FR-005**: The system MUST support separate targets for meropenem, imipenem, colistin and ceftazidime-avibactam.
- **FR-006**: Each target-specific model MUST exclude the target drug and all reserved-drug measurements from its predictor matrix.
- **FR-007**: The system MUST provide a grouped 70/30 development/test split and record every isolate group’s partition.
- **FR-008**: The system MUST train from measured reported susceptibility categories without turning categories or censored MIC bounds into invented exact values.
- **FR-009**: The system MUST support an explicitly labelled exploratory small-sample run while retaining target-leakage, group-separation and private-data controls.
- **FR-010**: The system MUST show target-specific available, excluded and class counts, plus confusion counts and metrics with unavailable denominators shown as unavailable.
- **FR-011**: The system MUST keep the uploaded workbook, normalized observations, fitted models and run outputs in ignored local private storage by default.
- **FR-012**: The system MUST export a reproducible target-specific run bundle containing configuration, hashes, split manifest, predictions, metrics and a human-readable report.
- **FR-013**: The system MUST show missing target coverage instead of emitting a trained model when that target has no labels.

### Key Entities

- **AST observation**: One measured isolate-antibiotic result with reported category, optional MIC bound/operator/unit, standard and method provenance.
- **Isolate group**: One isolate and any linked patient or duplicate isolates that must remain together during partitioning.
- **Target experiment**: A single reserved antibiotic endpoint, prespecified predictor panel, configuration, grouped split, fitted estimator and held-out results.
- **Import manifest**: Input and output hashes, row counts, source-column mapping and import warnings.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 2,555 source observation rows from the supplied workbook are either represented in the normalized output or individually identified in an import issue report; none are silently discarded.
- **SC-002**: Every trained target run assigns each eligible isolate group to exactly one partition, with the test share within 5 percentage points of 30% when a valid split exists.
- **SC-003**: Automated leakage checks confirm that the target drug and other reserved drugs are absent from the model matrix for every target run.
- **SC-004**: The run report presents recorded R/S counts, false-negative and false-positive counts, and marks unavailable metrics when the test set lacks their denominator.
- **SC-005**: The four target requests each produce either a reproducible run bundle or an explicit target-unavailable/training-blocked report.
- **SC-006**: Uploaded measurements and fitted models are absent from the public repository and static website bundle.

## Assumptions

- The reported AST categories are the initial endpoint; MIC values and censoring are retained as source evidence but are not reinterpreted into new categories.
- The supplied file’s CLSI labels are analyzed as reported because no CLSI edition is supplied; the run is therefore exploratory.
- The current dataset is a user-provided development batch. Its source study and patient-level links remain unknown unless separately documented.
- The app continues to use the existing canonical Python model code; a local importer may prepare the workbook before the normalized CSV is uploaded to the browser workflow.
- Models are trained separately for each reserved target. Missing targets do not inherit predictions from another target.
- Exploratory execution does not establish clinical validity or accuracy for India.
