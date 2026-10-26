# Research decisions

## Decision: Use the existing reported categorical AST endpoint

**Rationale**: The workbook contains reported susceptible/resistant phenotypes and numeric MIC bounds with censoring signs, but does not document standard version. The initial task is to fit from the reported categories while preserving numeric source observations as metadata. Converting these categories into newly derived breakpoints would invent interpretation details.

**Alternatives considered**: Infer new S/I/R categories from MIC breakpoints; rejected because the CLSI edition and target-specific breakpoint rules are missing.

## Decision: Train one target-specific estimator per reserved drug

**Rationale**: A single multi-output model would obscure target-specific label coverage and could leak reserved target measurements into the features for other targets. Separate runs make the target outcome and missing-label state explicit.

**Alternatives considered**: One joint classifier for all reserved outcomes; rejected for this initial implementation because target labels and cohort sizes differ.

## Decision: Keep a fixed 70/30 grouped holdout and use one prespecified estimator

**Rationale**: User requested a 70/30 train/test workflow. The current target has small resistant counts, so nested model selection, calibration or threshold search is not supportable. A prespecified regularized logistic estimator avoids searching on the test labels. If a class has no test examples, its metrics are reported as unavailable.

**Alternatives considered**: Reuse the existing five-fold 60/20/20 pipeline; rejected because it neither matches the requested proportion nor can pass its minimum class-count gates with this upload. Lower every gate in the general validated workflow; rejected because that would weaken unrelated experiments.

## Decision: Import Excel locally and upload normalized CSV to the browser

**Rationale**: The project’s browser workflow accepts canonical CSV and executes the same Python model code in Pyodide. A local importer can use `openpyxl` without adding workbook dependencies to the static browser runtime or publishing the input file.

**Alternatives considered**: Add an XLSX parser dependency to the browser; rejected as unnecessary for the supplied workflow and more complex to verify.

## Decision: Treat missing source/standard metadata as unknown

**Rationale**: BioSample accession, record create date, location and Vitek platform do not establish the source study, collection date, actual laboratory, patient identity or interpretation edition. The importer retains the known raw fields and leaves the rest blank.

**Alternatives considered**: Infer source from accession prefix, collection date from create date, or lab identity from platform; rejected as unsupported.
