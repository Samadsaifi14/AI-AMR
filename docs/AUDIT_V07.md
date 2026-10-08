# AMR project audit and retrospective reevaluation — 7 October 2026

## Decision

The pipeline is a research implementation, not a validated India prediction model. Its intended question remains: predict meropenem or imipenem R/S from other measured antibiotic phenotypes, with NDM/OXA-48-like annotation used for cohort selection and stratification, then test transfer to other sources/regions. Both MIC and categorical AST are allowed by the brief. More algorithms cannot repair missing susceptible isolates, missing mechanism annotations, undocumented laboratory methods, or domain shift.

This revision repairs verified implementation defects and adds a real native XGBoost comparison. It does **not** establish 100% reliability, improve every holdout, certify clinical use, or turn previously inspected data into independent validation.

## Resources and scope

Reviewed the supplied project brief and Related Published Work document, the original implementation plan, the Methods and availability sections of both attached full papers, canonical source modules, browser bridge/UI/build, importer, curation scripts, existing tests, configurations, historical evidence and available public observations. Resource hashes are in `RESOURCE_REVIEW_V07.json`. Older ZIP releases are historical snapshots; the current Git main checkout was the implementation audited. The additional public ICU candidate collection remains quarantined: 122 AST rows at isolate level, 854 long observations, unverified AST–gene joins and missing interpretation metadata. The separate India BioSample pilot has only one eligible resistant isolate. No additional raw ATLAS or MALCA isolate data were supplied by these documents.

- The brief explicitly permits MIC **or** categorical R/S panels. NDM/OXA-48-associated isolates are the starting mechanism cohort; a broad untyped Gram-negative collection does not satisfy that cohort definition.
- Valavarasu et al., DOI https://doi.org/10.1038/s41598-025-14078-w, used ATLAS, drug-row S/I/R classification and demographic/clinical features. The Related Published Work document supplies the wrong DOI for this attached paper. Its published AUC is not a target or expected accuracy for our different endpoint. ATLAS requires an authorized data request through https://amr.vivli.org/.
- Emeraud et al., DOI https://doi.org/10.1038/s41467-026-72713-0, is MALCA: inhibition-zone features, carbapenemase-type endpoints, training-fold preprocessing/selection, and an 8,514-isolate external evaluation. This is distinct from CarbaDetector and from carbapenem R/S prediction. MALCA individual-level datasets are controlled-access; its summary figures cannot be converted into training observations.
- Adopted the relevant principles: fixed endpoints and predictor allowlists, isolate/patient separation, development-only model selection, retained independent-source challenges, uncertainty and full cohort accounting. Did not copy reported performance or use synthetic oversampling to claim additional independent patients.

## Verified repairs

| Defect | Correction |
|---|---|
| Explicit quarantine flag was not enforced during cohort building | Isolates marked quarantined, proposed or requiring review are excluded before model eligibility, even in exploratory categorical mode. |
| Strict model quick prediction bypassed the lab/QC/version/panel contract | The compact browser form now rejects strict-model predictions and directs users to the frozen external CSV evaluation, which applies observation checks. Strict unlabeled quick prediction remains unsupported. |
| Failed or unevaluated model could issue an ordinary R/S decision | New research decisions defer for these models; raw probabilities and fixed-threshold holdout errors remain available for auditing. A passing internal operating point is still explicitly exploratory. |
| Configured but untrained species were offered for inference | Serialized model and browser selector use species actually seen in training; missing or unsupported species are rejected. |
| Encoded inference could accept missing panels or contradictory categories | Required features, finite values, nominal one-hot categories, MIC missingness and minimum panel coverage are checked. |
| Placeholder version/QC/identity fields could be treated as known | Common missing/placeholder markers are rejected; identity whitespace is trimmed and absent patient/duplicate/hospital markers remain absent. These checks cannot authenticate arbitrary fabricated metadata. |
| One hospital patient's isolates across publications could get separate groups | Recorded hospital–patient links now join components across sources, and external evaluation checks the same identity links. This requires consistently curated hospital IDs. Unknown patient identity still prevents a verified independence claim. |
| Invalid operating targets or bootstrap counts were rejected late or not at all | Configuration checks run before fitting. Normalized drug aliases propagate through CLI, browser and modelling. |
| Metric input silently truncated fractional labels | Metric functions reject nonbinary, misaligned, multidimensional or nonfinite inputs. |
| Perfect small test samples could show a degenerate bootstrap interval | Exact 95% sensitivity/specificity intervals now accompany cluster bootstrap in saved results, reports and dashboard. Exact intervals assume independent isolates. |
| External breakpoint rules were not bound to a training hash | New breakpoint-labelled model locks record rule hashes; external evaluation rejects changed or missing rules. |
| Colistin disk categories could enter predictors | Known colistin disk/gradient methods are rejected even in exploratory inputs, following the EUCAST warning. This targeted rule does not replace full microbiology review. |
| Wide importer unnecessarily required MICs for categorical data | Explicit `reported_sir` mappings now work without invented concentrations and preserve missing observations. |
| Brief requested XGBoost but only other boosted trees existed | Optional pinned native XGBoost candidates now compete inside the same development folds; their actual package version is recorded. Browser runtime does not claim to supply XGBoost. |
| Website source ZIP used an older scientific snapshot | Build generates the download from current source/configuration/resource files. Archived release files remain historical. |

MICs retain their concentration units and censoring operators. No arbitrary lab-specific rescaling was introduced. A strict provenance filter is not a laboratory agreement study or an automated species/drug/breakpoint applicability review.

## Full native reevaluation

Input: all 1,804 public BioSamples / 25,387 AST rows. The known-source protocol retains **482 isolates: 212 R and 270 S**, without subsampling. The earlier 499 count used a different source-eligibility setting. All 13 recorded sources were challenged, plus internal and India splits: four experiments evaluated, eleven blocked with retained reasons. Ten source tests lack the minimum class coverage; India is absent in this particular eligible collection. Patient identity remains incomplete.

Candidates: prevalence/species/missingness controls, logistic regression, Random Forest, histogram gradient boosting and native XGBoost (two configurations each for the primary learned families). Primary selection uses equally weighted development-fold log loss with a worst-fold tie break. Sigmoid calibration and threshold selection use a held-out development subset; no threshold was adjusted to repair test performance. This calibration subset is shared between calibration and threshold selection, so its apparent performance is not an independent estimate. All comparisons are retrospective because these public data have been inspected before.

| Challenge | Test n | Model selected on development data | Sensitivity | Specificity | AUROC | FN / FP | Outcome |
|---|---:|---|---:|---:|---:|---|---|
| Internal grouped split | 97 | Random Forest, depth 4 | 100.0% | 79.6% | 0.9724 | 0 / 11 | Exploratory operating point only |
| PRJNA278886 held out | 165 | XGBoost, depth 2 | 0.0% | 100.0% | 0.7977 | 29 / 0 | Failed |
| PRJNA288601 held out | 130 | Random Forest, depth 4 | 99.1% | 23.1% | 0.7909 | 1 / 10 | Failed |
| PRJNA308116 held out | 42 | Random Forest, depth 4 | 100.0% | 7.7% | 0.9271 | 0 / 12 | Failed |

The internal 43/43 resistant detections have a two-sided exact 95% sensitivity interval of **91.8–100%**, even before accounting for unrecorded patient clustering. High AUROC alongside failed operating thresholds demonstrates why ranking performance alone is insufficient. These results do not establish India performance. Do not choose a new model or threshold from this table and call the same table confirmatory validation.

## Indian cohorts and aim alignment

All **266 isolates / 2,128 observation rows** of the categorical supplement were retained in input audits. Configuration determines species/target/panel eligibility; no labels, gene absences, lab identities or MICs were invented.

| Cohort | Eligible | R | S | Result |
|---|---:|---:|---:|---|
| Meropenem, exploratory categorical | 213 | 198 | 15 | Internal/source/region challenges blocked |
| Imipenem, exploratory categorical | 186 | 177 | 9 | Internal/source/region challenges blocked |
| Strict lab-comparability filter, each target | 0 | 0 | 0 | Required documented interpretation/provenance unavailable |
| Confirmed NDM/OXA-48 cohort, each target | 0 | 0 | 0 | Mechanism annotations uncurated |

The strict reevaluation pins EUCAST 16.0 only as a requested filter. It does not relabel the historical data or assert that the original labs used that version. Always predicting R would score 92.96% on the eligible Indian meropenem cohort, with **zero specificity**. That is not a useful model. Oversampling does not remedy the lack of independent susceptible examples.

The scientific aim is therefore **partially implemented but not empirically fulfilled**: phenotype processing and research comparison work; confirmed-mechanism India training and credible cross-source validation remain blocked by data/evidence.

## What is needed next

1. Obtain authorized Indian isolate-level datasets with both R and S outcomes, documented recruitment, other-antibiotic panels, species, collection time, consistently identified hospital/lab, de-identified patient links and repeat-isolate rules.
2. Obtain measured NDM/OXA-48 evidence and verify isolate-to-assay joins. Keep unknown calls unknown and broad surveillance separate from the confirmed-mechanism analysis.
3. Have a microbiology reviewer approve species–drug–method applicability, standard/version and relevant breakpoint footnotes. Review colistin testing specifically; metadata completeness alone does not establish validity. Use paired testing/reference-method comparison to investigate lab differences.
4. Prespecify an India development cohort, an independent calibration/operating-point protocol and fresh hospital/time/source tests before inspecting outcomes. Determine class counts using desired confidence-interval precision, not arbitrary software floors. Separate species analyses if pooling is not supported.
5. Compare the planned model families using development data only, freeze the selected model and threshold, then evaluate the untouched cohort. Report calibration, sensitivity, specificity, predictive values, missingness, class/source strata and uncertainty. Audit transport failures rather than suppressing them.

No additional optimization on already observed tests can substitute for step 4. The current deferral band is a heuristic, not conformal coverage or an accuracy guarantee. Clinical use and national representativeness remain outside the established evidence.

## Reproduction and verification

```bash
python -m pip install -r requirements-local.lock.txt
python -m pip install -e '.[xgboost]'
python -m pip install pytest
python -m pytest -q
python scripts/materialize_data.py
python scripts/reevaluate_v07.py --out results/reproduction_v07  # must not already exist
npm ci --ignore-scripts
npm run build
npm run test:web
npm install --prefix test-runtime pyodide@0.29.3
npm run test:runtime
```

`results/audit_v07/summary.json` and each experiment's configuration, audit, split manifest, development comparison, model lock, predictions, baseline/stratum tables and report retain the evidence. Fitted Joblib files remain local under the existing repository exclusion rule; hashes of retained outputs identify the exact run. Reproducible source and recorded package versions do not guarantee bitwise equality across native and WebAssembly environments.

Final verification: **81 Python tests passed**, static build/source-archive checks passed, and pinned Pyodide runtime checks passed. All four fitted native experiment metrics reproduced exactly. The browser source holdout still failed: AUROC 0.7544, sensitivity 3.45%, 28 false negatives among 29 resistant isolates. No live visual or deployment verification is claimed. Details and hashes are recorded in `VERIFICATION_V07.json`.

## Primary methodological references

- EUCAST breakpoints and category definitions: https://www.eucast.org/bacteria/clinical-breakpoints-and-interpretation/clinical-breakpoint-tables/
- EUCAST MIC methodology: https://www.eucast.org/bacteria/methodology-and-instructions/mic-determination/
- EUCAST laboratory methodology/QC: https://www.eucast.org/bacteria/methodology-and-instructions/disk-diffusion-and-quality-control/
- EUCAST colistin warning: https://www.eucast.org/news-detail/colistin-gradient-tests-and-disks-have-no-place-in-susceptibility-testing/
- EUCAST guidance including colistin testing: https://www.eucast.org/bacteria/guidance-documents/
- XGBoost official Python API: https://xgboost.readthedocs.io/en/stable/python/python_api.html
