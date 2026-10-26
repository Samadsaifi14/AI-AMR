# Tasks: Guided, beginner-friendly AMR workflow

**Input**: Design documents from `/specs/005-guided-demo/`

## M1 — Home, guided demo and resume

- [x] T001 Home cards explain demo, own data and resume paths.
- [x] T002 The demo loads the synthetic fixture and starts the canonical analysis.
- [x] T003 Result explanations use run metrics for missed resistance and false alarms.
- [x] T004 Runtime setup and failures use named stages and retry guidance.
- [x] T005 Responsive Home and run progress styles.
- [x] T006 IndexedDB stores and restores setup, upload, result and archive where quota allows.
- [x] T007 Restored CSV enters the existing analysis workflow without faking a file input.
- [x] T008 Local storage is disclosed and users can clear it; active runs warn on close.
- [x] T009 Implementation evidence and limitations are documented.

## M2 — Import and data review

- [x] T010 Import CSV and first-sheet XLSX files in the browser; detect long or wide layout.
- [x] T011 Show editable column mappings, antibiotic-column selection, preview and a visible mapping log.
- [x] T012 Build a separate canonical long-format analysis copy without changing source values or filling missing values.
- [x] T013 Expose Ready / Needs attention / Cannot run with exclusions and missing recorded details.
- [x] T014 Store the source file, accepted mapping and normalized copy locally; restore unfinished mapping work.

## M3 — Recipe, run and results

- [x] T015 Offer target choices with preliminary resistant/susceptible counts and minimum-count explanations.
- [x] T016 Offer a plain-language sensitivity/false-alarm goal and keep advanced settings collapsed.
- [x] T017 Show result badge from existing engine gates and explain missed resistance and false alarms.
- [x] T018 Group full detail behind an expandable disclosure, including confusion counts, uncertainty, source and species results.
- [x] T019 Move source comparison, drift, networks and version history into the Lab bench.

## M4 — Save and access

- [x] T020 Provide one ZIP plus browser Print-to-PDF action and separate HTML/ZIP downloads.
- [x] T021 Provide keyboard labels, status announcements, review checkboxes, reduced-motion behavior and responsive mapping controls.
- [x] T022 Update the user guide for CSV/XLSX, wide/long import, Recipe, result layers, local resume and PDF export.
- [x] T023 Record implementation limits and the fact that automated/browser verification was not run.
