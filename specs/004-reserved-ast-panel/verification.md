# Verification: supplied reserved-antibiotic AST panel

## Import

- Workbook: user-supplied `asts (6).xlsx` (kept outside Git and the website bundle).
- Imported 2,555 source rows into 2,555 canonical observation rows; 0 import issues.
- Isolate grouping uses the workbook's `#BioSample` accession. Repeated drug rows for a BioSample remain one group and cannot cross the 70/30 split.
- The analysis includes *Escherichia coli* and *Klebsiella pneumoniae*. Other recorded species are excluded by the target configurations.
- The configured predictor panel is ceftriaxone, cefepime, ciprofloxacin, gentamicin, amoxicillin-clavulanate, cefotaxime, and piperacillin-tazobactam. Cefotaxime has no rows in the workbook and was omitted from fitted models using training-partition coverage only. The six observed predictors were used when available.
- The four reserved targets are evaluated separately; target AST rows are labels only and are not predictors.

## Target runs

| Target | Eligible isolates | Train / test | Test labels | Outcome |
| --- | ---: | ---: | --- | --- |
| Meropenem | 209 | 146 / 63 | 2 R, 61 S | Trained; 2/2 resistant test isolates detected, with 6 false positives. |
| Imipenem | 3 | 2 / 1 | 0 R, 1 S | Trained; sensitivity unavailable because the only resistant isolate remained in training. |
| Colistin | 4 | 3 / 1 | 1 R, 0 S | Trained; specificity unavailable because the test set has no susceptible isolate. |
| Ceftazidime-avibactam | 0 | — | No measured target rows | Training blocked; this target cannot be evaluated from this workbook. |

These runs confirm that the importer, isolate grouping, target-specific training path, holdout evaluation and blocked-target reporting work. They do not establish reliable performance. Patient linkage, lab identity, CLSI edition and source-study metadata were not supplied; resistance counts for imipenem and colistin are too small for useful evaluation. No clinical use or treatment decision is supported.

Private import and run artifacts are stored under ignored `data/private/` directories. They are excluded from Git and the generated source ZIP.

## Software checks

- `python -m pytest -q`: 117 passed, 1 skipped.
- `npm run build`: passed.
- `npm run test:web`: passed.
- `npm run test:runtime`: passed, including Pyodide batch preparation, train/predict, source holdout, categorical audit and broad framework runtime checks.
- `git diff --check`: passed.

