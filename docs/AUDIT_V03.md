# India-focused AMR lab audit and implementation status

## Findings and changes

The original brief predicts bacterial isolate carbapenem resistance from other measured AST results. Genotypes annotate mechanisms; they do not enter the core model. The implementation plan correctly distinguishes this from MALCA's carbapenemase-detection endpoint and from the supplied ATLAS paper's multiclass surveillance prediction task. No paper's reported AUROC is a promised target for this dataset.

1. The initial screen defaulted to synthetic fixtures. It now defaults to measured public AST, retaining a clearly labeled synthetic software test.
2. A test count was easily confused with total training size. Results now display training/calibration/test counts and whether every eligible isolate was assigned. Fifteen-row previews do not truncate training.
3. Model selection used grouped within-source CV even during source transfer tests. Automatic selection now uses leave-one-development-source-out validation when at least three training sources are available. Fold log losses receive equal weight, with worst-fold loss as a tie break. Source/patient overlap blocks that analysis. Sparse source diversity falls back explicitly to grouped CV; it does not establish source transfer. Model choice and threshold remain frozen before final test outcomes.
4. Added all-source validation in browser and CLI, including an explicit India challenge. Every source is attempted; blocked and failed experiments are retained. Unknown source isolates have a dedicated exclusion file for source-transfer runs and remain available for internal evaluation. No random row subsampling.
5. Added a chunked wide-CSV importer with explicit reviewed metadata/drug mappings, all-row retention and checksums. It never infers MIC from categories or zone diameters. The example mapping is a template, NOT a verified ATLAS dictionary. Fill units, method, interpretation standard/version, evidence class and host from source documentation before use.
6. Added plain-language operating-point status, source/country counts and simple validation design controls. Advanced JSON remains available.

## Run a complete supplied dataset for free

Install the pinned local dependencies as described in README. Obtain authorized isolate-level data, review its dictionary, and adapt `configs/wide_mapping.example.json` to exact source headers. Use canonical long-format input directly if already available.

```bash
python -m amr_discovery import-wide --data data/private/full_source.csv --mapping configs/reviewed_mapping.json --out data/private/observations.csv
python -m amr_discovery audit --data data/private/observations.csv --config configs/reviewed_study.json --out results/full_audit
python -m amr_discovery validate --data data/private/observations.csv --config configs/reviewed_study.json --out results/full_validation
```

Output folders must be new to protect previous experiments. The importer reads chunks; cohort construction and model fitting still operate in memory. No million-isolate throughput claim has been tested. Profile RAM on the actual complete source; no paid service is required by the code. Browser uploads remain limited to 10 MB. The local CLI has no file-size/row cap but requires sufficient RAM and disk.

## What is not completed or established

- Approved ATLAS/Vivli raw data are not present. The supplied ATLAS paper describes 917,049 isolates; the current 1,804-BioSample acquisition is a separate convenience pilot. Data access: https://pmc.ncbi.nlm.nih.gov/articles/PMC12368220/ and https://amr.vivli.org/.
- The public phenotype cohort does not establish Indian transportability. The separate India acquisition has one eligible resistant isolate and no susceptible comparator.
- Indian ICU supplementary candidate data remain quarantined pending review of units, standards and proposed isolate joins. No unreviewed labels or synthetic susceptible samples were inserted to inflate sample size.
- NDM/OXA-48 biological contrasts require linked, independently measured mechanism annotations. Gene co-occurrence/geographic networks are separate exploratory outputs, not validated model features.
- Calibration and threshold share a development calibration subset; source-wise calibration robustness and separate prospective operating-point validation remain research tasks. Deferral width is prespecified, not a certified safety rule.
- Meropenem is primary; imipenem remains separately configurable. This is not a model for every antibiotic or every Gram-negative species.
- Compact-panel selection, missing-panel stress experiments, mechanistic replication, prospective evaluation and a reviewed external cohort remain open plan milestones. Neither these code changes nor passing software tests complete the whole discovery study.
- Repeated source challenges are exploratory internal-external validation of this collection. Do not select a winning model or threshold from the test summary. Already inspected holdouts cannot become fresh confirmatory evidence.

## Ordered team work

1. Data steward: acquire approved complete surveillance files and matched Indian AST; record access terms and overlap.
2. Microbiology lead: sign off dictionary, MIC units/methods, breakpoint version, S/I/R semantics and mechanism joins.
3. Modeling lead: run full audit and source suite; review all excluded/blocked strata and precision intervals.
4. Statistics lead: freeze panel, model-selection protocol, calibration and operating targets before a new independent Indian evaluation.
5. Independent evaluator: run the locked model on new Indian hospitals/time periods with patient/duplicate grouping and both outcome classes.
6. Team: assess failures and replicate supported mechanisms; only then consider clinical/prospective work.

## Operating gate correction

A sensitivity-only gate can reward predicting every isolate resistant. The exploratory default now requires sensitivity >=0.95 AND specificity >=0.50; both are explicit configurable research targets, not clinical acceptance standards. Confidence intervals and independent validation are still required. Older archived reports used sensitivity alone and are retained as historical outputs.

## Executed public-data results

Complete input: 1,804 BioSamples, 25,387 AST rows, 499 eligible isolates. Three source holdouts were evaluable after explicit exclusion of 17 unknown-source isolates. PRJNA278886: n=165, AUROC 0.8114, FN=29, FP=0. PRJNA288601: n=130, AUROC 0.6949, FN=0, FP=13 (specificity zero). PRJNA308116: n=42, AUROC 0.9456, FN=0, FP=12. None meets the combined research operating targets. India holdout unavailable. See VALIDATION_V03_RESULTS.json for every attempted/blocked comparison.
