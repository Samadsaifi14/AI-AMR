# Laboratory comparability decision — v0.6

Decision: use categorical AST as the primary India research model, under one documented interpretation standard and version. Keep numeric MICs as a separate, reviewed sensitivity analysis. Train separate meropenem and imipenem endpoints from other antibiotic phenotypes. Do not pool unspecified labels into a harmonized research claim.

MIC is a concentration, not a dilution tube number. Different concentration ranges produce different censoring limits; measurement methods, quality control and interpretation standards also affect comparability. A universal lab-specific multiplier cannot establish agreement. EUCAST describes reference broth microdilution and standardized/calibrated testing, with routine and extended QC. Its MIC distributions guidance acknowledges typical variation of a doubling dilution. That tolerance is not a license to shift each laboratory's results until they agree.

## What the software now checks

- Categorical predictors must match the configured target standard and its version (or an explicitly pinned version). Incompatible predictor labels become missing with an exclusion event; the minimum-panel gate still applies. A pinned target-version mismatch excludes the isolate.
- `comparability_policy: strict` requires an explicitly pinned EUCAST/CLSI version, identified testing lab, a supported specific AST method and documented QC reference. Unspecified `reported AST` and generic `MIC` methods are insufficient in strict mode. These fields document provenance; the program cannot verify a laboratory's actual analytical performance.
- Numeric observations with a supplied concentration ladder must have positive, increasing concentrations and a reported bound on that ladder. Nonuniform ladders are allowed. Strict numeric mode also requires the panel ID and actual tested concentrations. Bounds remain bounds: `>=16` is not rewritten as an exact MIC of 16.
- Units `mg/L` and `µg/mL` are equivalent. Zones in mm, mixed MIC units and arbitrary dilution indices are not silently converted.
- Audit output inventories missing lab/QC/standard/version fields and each lab–method–standard–version–drug combination, panels, units and censored rows.
- Laboratory holdout uses `lab_id`, rejects unknown labs and preserves patient/duplicate separation. All-source validation adds all available laboratory challenges when at least two identified labs exist. Laboratory identifiers never enter the phenotype feature matrix.

The strict configuration is a template. Replace its version and lab placeholders with documented values, use the revised CSV template and audit the entire file. Do not fill unknown fields with guessed values. The default public-data runs remain exploratory for reproducibility.

## Study protocol needed to resolve laboratory differences

1. Obtain per-observation lab, AST method/platform, QC reference, standard/version, panel ID and actual tested concentration ladder when MICs exist. Retain raw values and operator, source row and original report. A source study, hospital or geographical region is not automatically a testing laboratory.
2. A microbiology reviewer selects the interpretation standard/version and verifies species/drug/method-specific applicability and relevant footnotes. Use documented matching categories directly. To reinterpret historical MICs, use reviewed rules and interval reasoning; an interval crossing a breakpoint stays unresolved. Do not translate old S/R labels without the underlying measurements. The present strict path accepts reported categories; it does not automatically re-interpret all predictor MICs.
3. Before pooling methods, establish agreement using paired, independently tested isolates against an appropriate reference method, with prespecified essential/categorical agreement and error analysis, especially near breakpoints. This paired laboratory study is additional work; metadata filters alone do not complete it.
4. Develop and calibrate only within development sites, then freeze the model and threshold. Prespecify fresh Indian hospital/laboratory and time holdouts, adequate R and S counts for the intended interval precision, and sensitivity/specificity/calibration targets. Report all laboratories and uncertainty, including failed challenges. A resistance-enriched cohort cannot establish national predictive values without representative sampling.
5. Compare the categorical primary model with an interval-aware MIC sensitivity analysis on independently reviewed measurements. Do not divide by each lab's maximum or center on each lab's population mean: these operations can erase true differences in resistant populations. No such correction is applied here.

## Full Indian supplement

All 266 isolates / 2,128 AST rows remain in the input audit. The exploratory categorical cohorts previously retained 213 meropenem and 186 imipenem isolates. The public supplement supplies no per-isolate lab/QC/breakpoint-version documentation adequate for the strict protocol. Strict mode must exclude these undocumented results; this is not a new validation result or proof that the measurements are wrong. Request the original laboratory metadata and recruit additional independently matched susceptible and resistant isolates. No data or MICs were invented.

## Primary guidance

- https://www.eucast.org/bacteria/methodology-and-instructions/mic-determination/
- https://www.eucast.org/bacteria/methodology-and-instructions/disk-diffusion-and-quality-control/
- https://www.eucast.org/bacteria/mic-and-zone-distributions-ecoffs/
- https://www.eucast.org/bacteria/clinical-breakpoints-and-interpretation/clinical-breakpoint-tables/

Validation results and full-cohort provenance audit are recorded with this revision. Software checks do not establish Indian clinical accuracy.

## Revision verification

- 58 Python tests passed, including interpretation mismatch, strict lab/QC/version filters, actual dilution ladders, equivalent units, preserved censoring and laboratory holdout separation. The 8 harmonization tests also passed after making their fixtures explicitly string-typed.
- Static build checks passed: canonical Python source packaging, asset links, unique IDs and JavaScript syntax.
- Pinned Pyodide runtime passed demo fit/predict, public source challenge, complete Indian categorical audit, all regional blockers and the strict provenance audit (`BROWSER_RUNTIME_TESTS_PASSED`). Scientific-package cache files used by the local verifier are checked against the pinned manifest SHA-256 before loading.
- Complete results/configuration/exclusion tables are in `results/lab_comparability_v06/`. Input is the unchanged 266-isolate / 2,128-row categorical dataset; relevant target/predictor provenance audit covers 1,862 rows per endpoint. All 1,862 lack identified lab, standard/version and QC documentation. Strict eligibility is 0 for both targets. No accuracy improvement is claimed from these filters.
