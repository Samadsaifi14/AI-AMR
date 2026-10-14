# India validation acquisition and external challenge — 5 October 2026

**India accuracy is not established.** A new acquisition audited all 266 rows of a published Indian study. An unchanged previously fitted public-source model was also challenged on every eligible isolate in the existing India BioSample file: one resistant isolate, incorrectly predicted susceptible at the locked operating point. No result was hidden, no threshold was tuned, and no additional isolates were fabricated.

## Acquired full Indian study

Gheewalla et al., *Genomic landscape of antimicrobial resistance in India: findings from a multi-species surveillance study*, npj Antimicrobials and Resistance (2026), DOI [10.1038/s44259-026-00185-9](https://www.nature.com/articles/s44259-026-00185-9). Supplementary Data 1 was downloaded in full (82,353 bytes). SHA-256: `0ea263f9af2b1ef9c7e5d145cb50efbf2b5df08ec96bcd0224452cffec375823`.

| Full-file audit | Result |
|---|---|
| Distinct isolates | 266; no row subsampling |
| Supported species | 69 K. pneumoniae and 47 E. coli |
| Meropenem reported outcomes, supported species | 108 R / 8 S |
| Imipenem reported outcomes, supported species | 106 R / 7 S / 3 missing |
| Published predictor values | R, S, I, SDD; numeric MICs absent |
| Eligible for frozen numeric-MIC model | 0 |

The supplement is useful measured categorical AST evidence. It is incompatible with the existing MIC feature representation. R/S/I/SDD must not be converted into invented concentrations. A new categorical-feature model would be a separate development experiment requiring a separate, untouched external test. The article describes resistance-based selection at tertiary centres in Northern and Western India; this collection does not establish nationally representative accuracy. The supplement does not provide per-isolate standard/version or patient identifiers.

Reproduce the complete audit:

```bash
python scripts/audit_india_npj.py --data data/raw/india_npj_2026/supplementary_data_1.xlsx --out <new-audit-folder>
```

The repository retains every published isolate row, per-isolate exclusions and audit JSON in `data/curated/india_npj_2026/`. Source remains public at the publisher; the raw workbook is not required for running the app.

## Frozen-model exploratory challenge

The previously completed primary source challenge (`full_validation_v03_reviewed/experiment_004`, logistic_C0.1) was used without refitting. Its meropenem threshold was 0.7820232701098387. Model, configuration and split hashes are recorded in `EXTERNAL_PROTOCOL_V04.json`; results are in `INDIA_EXTERNAL_RESULT_V04.json`. This is retrospective exploratory evidence: the India cohort was already inspected, and the protocol was not prospectively registered before acquisition. It cannot become a prospective validation by relabelling it.

All two BioSamples / 29 AST observations were audited. One isolate met MIC-panel eligibility. It received probability R 0.09264 and was missed (FN=1, TP=0). Sensitivity's exact two-sided 95% interval is 0–0.975. AUROC and specificity cannot be estimated without susceptible isolates. Missing patient IDs and unversioned labels further limit interpretation. Bootstrap intervals collapse with one isolate and must not be interpreted as certainty.

## Additional source checks

| Source | What was verified | Outstanding requirement |
|---|---|---|
| [ICMR NHRDR AMRSN 2017–2022](https://nhrdr.icmr.org.in/datasets/icmr-antimicrobial-resistance-surveillance-network-dataset) | Portal explicitly says raw data will not be shared, only query outcomes; sample/metadata require login | Authorized matched isolate-level access; aggregate reports do not replace MIC panels |
| [NRAMRB catalogue](https://nramrb.org.in/catalogue) | Public strain details contain numeric antimicrobial results and SIR; examined K. pneumoniae records omit units, AST method and interpretation version | Dataset export and verified dictionary, independent patient/duplicate identities and susceptible controls; catalogue not yet acquired/audited in full |
| Indian surgical ICU supplement, DOI 10.1038/s41467-026-74764-9 | Complete supplements previously acquired; 122 patient AST rows, 115 R / 6 S / 1 I | Units/standard review and verified genome–AST identity links; candidates remain quarantined |
| User's ATLAS surveillance source | Published paper reviewed; approved isolate-level surveillance file not supplied | Authorized raw export and matching metadata |

No data request, email or access-controlled dataset download was made.

## External evaluation now implemented

Before a **new** external dataset is examined, freeze one development-selected model and register the protocol with the independent evaluator. The CLI checks frozen model/configuration/split hashes, prevents isolate/source/duplicate overlap, requires India country metadata, audits the full input and saves predictions before scoring. It never calls training, calibration or threshold selection. Do not load joblib artifacts from strangers: use a trusted local fitted run.

```bash
python -m amr_discovery freeze-external --run <trusted-fitted-run> --out <new-protocol.json>
python -m amr_discovery external --protocol <new-protocol.json> --data <authorized-india-observations.csv> --out <new-results-folder>
```

The prespecified exploratory evidence gates require the **lower** endpoints of two-sided 95% exact intervals to reach sensitivity 0.95 and specificity 0.50, plus complete identity/label metadata and no repeated recorded patients/duplicate groups. These are separate binomial intervals, not a simultaneous confidence region. Cluster bootstrap and source/species strata are also exported. Gates cannot be relaxed through the protocol. Even a passing selected cohort is not national or clinical certification; `india_accuracy_established` remains false pending independently reviewed sampling and clinical evidence.

For scale, even 72 independent resistant isolates with **zero** misses are needed for a two-sided exact 95% sensitivity lower bound above 0.95. Errors require more. This is an illustrative mathematical minimum, not a national study sample-size justification. Multiple hospitals, regions, dates, susceptible controls, patient/duplicate IDs and a statistician-reviewed design are required. Repeated patients cannot be counted as independent successes.

## Data needed to finish the research milestone

Provide the approved surveillance export or new independent hospital data with stable isolate/source IDs; confirmed human specimens; collection date, hospital/state and de-identified patient/duplicate identifiers; species; measured meropenem (and separately imipenem) outcomes; numeric cefepime, ceftazidime, ciprofloxacin, gentamicin and amikacin MICs with censoring operators, units, method and interpretation standard/version. Preserve missing values. Use `observation_template.csv` and the data dictionary; `import-wide` processes complete exports using an explicit mapping. Gene annotations need separate assay/sequence evidence and exact identity joins; they are not primary predictors.

Obtaining suitable evidence and passing an untouched external test remain unfinished. Software changes cannot substitute for those observations.
