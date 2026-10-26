# Tasks: Reserved-antibiotic AST prediction

## Phase 1: Input and configuration

- [x] T001 [US1] Implement workbook column mapping and observation preservation in `amr_discovery/workbook.py`.
- [x] T002 [US1] Add the `import-asts-workbook` CLI command and private output manifest in `amr_discovery/__main__.py`.
- [x] T003 [US1] Add import tests for BioSample grouping, censoring, unsupported values and unknown provenance in `tests/test_workbook.py`.
- [x] T004 [US2] Add per-target exploratory configurations for the exact predictor panel in `configs/reserved_ast_*.json`.
- [x] T005 [US2] Permit categorical reported combination predictors while retaining MIC combination review requirements in `amr_discovery/data.py` and `tests/test_framework.py`.

## Phase 2: Exploratory grouped training

- [x] T006 [US2] Implement the small-sample grouped 70/30 split and fixed exploratory estimator in `amr_discovery/modeling.py`.
- [x] T007 [US2] Preserve raw model probabilities when the exploratory estimator has no calibration model in `amr_discovery/modeling.py`.
- [x] T008 [US2] Add tests for target exclusion, group separation, 70/30 proportions, rare-class handling and missing targets in `tests/test_exploratory_split.py`.
- [x] T009 [US2] Ensure training exports include model lock, predictions, errors, baselines, feature reliance and report-compatible metrics in `amr_discovery/modeling.py`.

## Phase 3: Browser workflow and user instructions

- [x] T010 [US2] Add ceftazidime-avibactam as a selectable target and a reserved-panel configuration action in `web/index.html` and `web/app.js`.
- [x] T011 [US2] Add the local workbook import and four-target run instructions to `web/guide.html`.
- [x] T012 [US3] Ensure the browser bridge returns the exploratory run artifacts through the existing canonical path in `browser_bridge.py`.
- [x] T013 [US3] Add browser/runtime coverage for the reserved panel and exploratory run output in `tests/` and `verify-runtime.mjs`.

## Phase 4: Private supplied-data run and verification

- [x] T014 [US3] Import the supplied workbook into ignored `data/private/` storage and verify all source rows are accounted for.
- [x] T015 [US3] Run all four target configurations into distinct ignored `data/private/runs/` directories and record each completed or unavailable result in `specs/004-reserved-ast-panel/verification.md`.
- [x] T016 [US3] Run the required Python, build, web and pinned runtime checks and confirm private files are absent from Git and the website source bundle.
- [x] T017 [US3] Record final verification results and mark completed work in `specs/004-reserved-ast-panel/tasks.md`.

## Dependencies

- T001 → T002 → T003 → T014.
- T004 and T005 → T006.
- T006 → T007 → T008 → T009 → T015.
- T010 → T012 → T013.
- T011 supports both US1 and US3 and can be completed alongside the browser changes.
- T014 and T015 → T016 → T017.

## Implementation strategy

Complete the local import and target-specific trainer first, then connect the same configuration to the browser. Run the supplied workbook only in ignored private storage. Keep a target-specific blocked/unavailable record for any target that lacks labels or cannot be split; do not synthesize missing data.
