# Training workflow repair — 2026-10-08

The existing production public-cohort train/evaluate operation completed in the cloud browser, but took several minutes with almost no intermediate feedback. The result was forest_depth8, 165 held-out isolates, 15 false negatives and 4 false positives. This confirms a functioning public-data execution path, not a resolution of every user-device failure or established clinical accuracy.

Changes: visible elapsed clock and canonical cohort/fold/report stages; explicit cancellation and runtime/input/display errors; block execution until source configuration loads; discard partially displayed outputs; prevent cancelled asynchronous input preparation from resetting a newer operation. Correct guide evidence_class examples to measured_authorized/measured_public/synthetic. Original optional CSS panel arrivals and four requested reference links (Godly, Transitions, Animos, Deck). Animos template details were unavailable, so no template assets are incorporated.

Validation: native Python 99 passed, 1 skipped (optional XGBoost not installed); build and generated-source/archive consistency passed; session UI regression checks passed, including pending configuration and result-rendering failure recovery. Canonical Pyodide runtime and live deployed UI checks recorded below after completion.

Scientific methods, selection, calibration, measured-label requirements and independent evaluation boundaries are preserved. Training completion does not mean operating targets have been met. No paid service or external patient-data upload was introduced.

Canonical framework Pyodide integration passed: public training/evaluation on 165 held-out isolates and dynamic prediction. Demo training/prediction, public source evaluation, Indian class-balance blocking and categorical/provenance gates passed in runtime verification.
