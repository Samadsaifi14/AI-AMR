# Implementation plan for transportable carbapenem resistance prediction

Prepared for Samad and the ML on AMR project team • 4 October 2026

## Research decision

Build an isolate-level, phenotype-based study of whether non-carbapenem susceptibility measurements predict meropenem resistance across independent populations. Treat imipenem as a separately evaluated secondary target. Make NDM and OXA-48-like isolates the prespecified biological focus, with genotype used for cohort definition and analysis, never as a core predictor.

The central contribution should be evidence about which phenotype relationships transport across settings, where they fail, and when the model should defer. A new classifier with high internal accuracy alone would provide limited novelty. The discovery claim remains a hypothesis until independently replicated.

This is an implementation protocol, not a report of experiments already performed. No isolate dataset has yet been acquired or audited, no model has been trained, and no external performance is established. Calendar and sample targets below are planning assumptions.

## 1 Scientific question and scope

**Primary question:** Can routinely measured non-carbapenem AST results predict a withheld meropenem resistance result in an independent population, with useful discrimination, calibrated probabilities, and an explicitly measured false-negative rate?

**Biological question:** Do prediction relationships remain stable within NDM, OXA-48-like, and co-producing isolates across countries and species, or do they mainly reflect local population composition and testing practices?

**Practical use case:** retrospective completion of partially observed susceptibility panels and identification of uncertain cases for further testing. Earlier clinical prediction is a separate claim: it requires timestamps showing that input results were available before the target result and evidence that the difference changes a real workflow. Simultaneously measured AST results do not establish a time advantage.

Start with Enterobacterales and prespecified E. coli and K. pneumoniae analyses. Pool other Enterobacterales only with suitable labels, adequate representation, and species-specific reporting. Keep Pseudomonas and Acinetobacter for separately designed extensions. This narrows the brief's initial all-Gram-negative scope so that biological heterogeneity does not overwhelm the first study.

### Cohorts and the first decision gate

| Cohort | Purpose | Required evidence |
|---|---|---|
| Confirmed NDM or OXA-48-like Enterobacterales | Original CPE-focused prediction question | Independent mechanism confirmation, target AST, eligible input AST, both outcome classes |
| Broader Enterobacterales | Recommended fallback or parallel generalization cohort | Target AST and input panel; retain mechanisms as known, negative under a defined assay, or unknown |
| Independent external cohort | Test transportability | Separate recruitment source and documented overlap checks; compatible measurement and outcome definitions |
| Later temporal cohort | Test stability over time | Collection dates and no overlap with development |

Do not assume that CPE status means every carbapenem is phenotypically resistant. Conversely, a resistant phenotype does not prove carbapenemase production. Preserve mechanism and phenotype as separate variables [1].

Before modeling, tabulate S, I, R and unresolved results by target × species × mechanism × source × country × year. If the CPE-only cohort is nearly all resistant, an always-resistant rule may appear excellent while specificity is unmeasurable. Broaden the prediction cohort and retain the original CPE question as a subgroup analysis, or obtain a deliberately designed additional cohort. Record that scope change before evaluating models. Do not create artificial susceptible examples to rescue the design.

Do not name a country as the primary external target until counts and access are confirmed. India is a scientifically relevant intended setting, but India-specific claims require adequate Indian evaluation data. National mechanism percentages in the supplied related-work notes are not verified estimates for this protocol.

## 2 What the existing work changes

The supplied project brief establishes phenotype-only prediction and cross-region testing as the starting objective. The related-work notes are useful leads, but require correction and verification before manuscript use.

| Evidence | Interpretation for this study |
|---|---|
| MALCA [1] | Detects and types carbapenemases from disc diffusion measurements. Its endpoint differs from drug-specific resistance prediction. Its isolate data have controlled access, and the public implementation is illustrative rather than the full released model. |
| Valavarasu and colleagues [2] | Relevant ATLAS modeling precedent. The methods describe transforming outcomes into isolate-antibiotic records and using demographic and clinical features. They do not clearly establish the same withheld-target, other-AST-feature task. Inspect the code before attempting exact reproduction. |
| CarbaDetector [3] | Useful external-validation precedent for carbapenemase detection. It is not automatically a fair performance comparator for meropenem resistance prediction. |
| Earlier interpretative antibiogram work [4] | Prediction of untested susceptibility using cross-antibiotic information predates this project. Include a conditional-probability/Bayesian baseline; do not claim the basic idea as new. |

Correct the Scientific Reports DOI in the related-work notes to **10.1038/s41598-025-14078-w**. The listed 13452-8 link does not identify the supplied paper. Do not use the reported AUC from another endpoint/population as an expected performance target here.

A focused literature extension should record population, prediction time, target, inputs, patient grouping, independent sites, mechanism annotation, calibration, missing-panel evaluation, and code/data access for each candidate study. This review is targeted, not an exhaustive novelty search. Verify the remaining citations in the supplied notes before including them in a publication.

## 3 Prespecified hypotheses

1. **Incremental phenotype information:** non-carbapenem AST improves external predictions over species and prevalence baselines on exactly the same isolates.
2. **Transportability:** a compact, broadly available panel loses less performance across populations than a locally optimized full panel. This may be false; measure it.
3. **Mechanism-associated heterogeneity:** errors differ between NDM-only, OXA-48-like-only and co-producing isolates after accounting for measured species, source, year and testing differences.
4. **Selective prediction:** a prespecified deferral policy lowers error among accepted predictions while retaining useful coverage in independent cohorts.

Designate meropenem and one external comparison as confirmatory before opening external outcomes. Treat imipenem, additional panels, interactions and mechanism contrasts as secondary or exploratory, with multiplicity handling and explicit labels.

## 4 Data acquisition and feasibility

Prioritize a development source with many linked AST measurements per isolate and an independently collected validation source. A large table with only isolated drug results is less useful than a smaller linked panel.

| Candidate | Intended role | Gate before use |
|---|---|---|
| Pfizer ATLAS through Vivli | Development candidate | Approved access, dictionary, linked isolate IDs, target/panel availability, typing selection policy |
| Independent surveillance program through Vivli | External candidate | Eligible species, compatible panel, recruitment independence, overlap audit |
| Published isolate-level tables or collaborating laboratory | External and mechanism-focused candidate | Individual rows, assay details, recruitment criteria, rights to reuse, mechanism evidence |
| NCBI AST and linked BioSample records | Secondary external candidate and annotations | Measured phenotype distinguished from genomic prediction, clinical provenance, method QC, duplicate audit |
| BV-BRC | Additional candidate, not yet verified | Confirm export availability, phenotype provenance, shared records with other repositories |
| MALCA material | Methodology comparison or exploratory separate endpoint | Permission and appropriate isolate-level labels; disc diffusion is not interchangeable with MIC |

Vivli requires a research-purpose description and agreement to access terms [5]. The prepared acquisition request should ask for original isolate identifiers, patient/episode grouping where permitted, source/laboratory, dates, species, specimen, all AST values and operators, methods, interpretive standard/version, molecular results, typing eligibility criteria, and panel design. No access request has been sent.

NCBI AST values are submitter supplied and require our own method and plausibility checks [8]. Do not assume a repository annotation is a measured susceptibility result. Aggregate country resistance percentages cannot replace linked isolate-level outcomes and inputs.

**Feasibility deliverables:** source inventory; access status; data dictionary; source-overlap matrix; target and feature completeness; mechanism-testing denominator; per-stratum class counts; intended-use timing assessment. Access is a dependency, not a guaranteed two-week task.

## 5 Canonical data contract

Keep immutable raw data, normalized long-form observations and derived model matrices as separate layers. Retain identifiers for joining and leakage prevention; exclude them from model inputs.

| Entity | Minimum fields |
|---|---|
| Isolate | source_id, original_isolate_id, canonical_isolate_id, patient_group_if_available, episode, species_original, species_normalized, country, site, collection_date, specimen |
| AST observation | isolate_id, drug, raw_value, operator, numeric_bound, units, method, reported_SIR, standard, version, test_date, panel_id, quality_flag |
| Mechanism annotation | isolate_id, family, allele_if_known, present/absent/unknown, assay, assay_targets, evidence_source, typing_selection_rule |
| Derived outcome | isolate_id, target, harmonized_class, binary_R_label, breakpoint_version, derivation_reason, ambiguity_flag |
| Provenance | source_filename, source_row_or_accession, retrieval_date, license/access_terms, input_checksum, transform_version |
| Split assignment | isolate_id, duplicate_group, patient_group, partition, fold, split_reason, manifest_checksum |

Keep NDM and OXA-48-like as separate indicators so co-producers are retained. Do not equate a generic OXA field with OXA-48-like. Negative means tested negative under a documented assay; untested and unspecified results remain unknown. Preserve allele information when available without imputing it.

## 6 Harmonization and quality control

**Measurement handling.** Normalize units and antibiotic names using a reviewed mapping. Preserve raw MIC operators: a value such as >8 is a bound, not an exact MIC of 8. For input features, use log2(bound) plus a censoring indicator as a pragmatic baseline and test sensitivity to off-scale values. For outcomes, assign a class only when the entire allowed interval lies within that class under the selected breakpoint. Otherwise retain an unresolved target and report its exclusion. Never impute target outcomes.

**Breakpoint policy.** Freeze one named, dated interpretation standard with microbiology review before outcome generation. Apply it only to compatible species-drug-method combinations. Keep original classifications alongside harmonized ones. Repeat key analyses under original classifications or an alternative justified standard to assess label sensitivity. No numeric clinical breakpoint is specified here without the applicable table and context.

Preserve S, I and R. The primary binary research endpoint can be R versus non-R under a single documented definition, but non-R must not be presented as standard-dose susceptible. EUCAST I means susceptible at increased exposure; it is not equivalent to CLSI intermediate. Do not pool the two I labels or silently group EUCAST I with R [6]. Report S/I/R composition and, if numbers allow, secondary multiclass results.

**Method compatibility.** Analyze MIC and zone-diameter data separately first. Do not convert zones to MICs using an assumed equation. Categorical harmonization is a secondary analysis only when species, method and interpretation are valid. Colistin is optional: exclude unreliable disc/gradient results from the primary panel; require documented acceptable MIC methodology [7].

**Duplicates and selection.** Link accession aliases across sources; identify repeat patient isolates and known outbreak/lineage groups where available. AST-identical isolates are not automatically duplicates. Use exact identifiers and provenance for definitive removal; place plausible duplicate groups together and run sensitivity analyses. Do not claim patient-independent validation if patient identifiers are unavailable.

**Missingness.** Distinguish untested, suppressed, failed, unknown-method and true missing records where possible. Start with an explicitly eligible shared panel. Compare native missing-value handling or training-only imputation plus missing indicators. Analyze selection into complete panels; a complete-case analysis can be biased. Do not fill absence with susceptibility or zero.

## 7 Feature design and biological interpretation

The primary model uses only eligible non-carbapenem AST measurements. Species is a prespecified added-feature model; country, source, year and mechanism are reserved for splits and analyses rather than the core phenotype model.

| Model input set | Question |
|---|---|
| Species or prevalence only | Does the model add anything beyond population composition? |
| One strongest eligible AST feature | Is a complex model necessary? |
| Non-carbapenem AST only | Does the phenotype panel contain transferable signal? |
| Non-carbapenem AST plus species | Does species context improve the panel? |
| Compact shared panel | Can performance survive practical panel constraints? |
| Expanded panel | What does broader testing add on the same evaluation isolates? |
| Other carbapenems added | Secondary easier task; quantify contribution separately |
| Metadata-only or missingness-only | Diagnostic control for source and testing-practice shortcuts |

For primary meropenem prediction, exclude meropenem MIC, its category, aliases, derived resistance summaries, all other carbapenem measurements, and any downstream interpretation that encodes the target. Apply the same policy to imipenem. Excluding all carbapenems makes the main scientific question more demanding; other-carbapenem inputs belong in a labeled secondary experiment.

Candidate non-carbapenem groups include cephalosporins, aztreonam, beta-lactam/inhibitor combinations, aminoglycosides and fluoroquinolones where measured validly. Choose the actual panel from development-set coverage and the intended workflow, not a desired story or external outcomes.

Mechanism-dependent beta-lactam patterns provide plausible hypotheses [1]. Non-beta-lactam signals may reflect linked resistance determinants, clonal composition or prescribing ecology; the phenotype data alone cannot distinguish these explanations. Use within-species and within-source analyses, held-out permutation importance, and repeated-fold feature stability. SHAP explains fitted predictions; it does not establish enzyme activity, gene linkage or causation.

## 8 Validation design

Freeze eligibility, outcomes, features and split manifests before model selection. Keep all observations from an isolate, patient group or confirmed duplicate group in one partition. If data are expanded to one row per isolate-drug, split groups before expansion.

Use grouped development folds for preprocessing, hyperparameters, feature selection and model comparison. Reserve separate development calibration data, or use rigorously cross-fitted predictions, for probability calibration and thresholds. No external test labels enter any of these operations.

| Evaluation | Evidence supported | Limitation |
|---|---|---|
| Grouped internal holdout | New groups from the development sampling frame | Does not establish cross-country generalization |
| Leave-country-out evaluation | Geographic holdout within the available source | Centralized AST can limit laboratory diversity |
| Later temporal holdout | Generalization to a later period | May retain the same collection practices |
| Independent program or hospital | Cross-source transfer | Requires harmonization and overlap checks |
| Prospective silent evaluation | Behavior on newly arriving local data | Clinical benefit still requires a separate study |

Do not label a country split from one centrally tested surveillance program as independent laboratory validation. If source and country are confounded, report combined domain shift; their individual effects are not identifiable.

Audit external schema and compatibility before evaluation, but do not select models using external outcome distributions or performance. Have a separate curator prepare locked outcomes if feasible. Local recalibration is a secondary adaptation experiment: allocate a distinct local calibration subset and evaluate on an untouched local test subset. Report zero-shot and adapted results separately.

## 9 Model implementation and optimization

Use a small model ladder: prevalence baseline; conditional-probability or regularized logistic model; random forest; gradient-boosted trees. Do not begin with deep learning, a large ensemble or an LLM predictor. The difficult work is data validity and transportability.

Start with modest bounded searches, for example 20-40 configurations per nonlinear model, using grouped inner validation and early stopping where available. Compare ordinary and class-weighted fitting; evaluate at natural prevalence. Avoid synthetic resampling by default because it can create implausible mixed susceptibility profiles. Any resampling must occur within training folds only and receive an ablation.

Select the development model using a prespecified combination of probability quality and operating-point performance. Report AUROC and PR-AUC, but do not choose a model solely for a small AUROC gain. Calibrate the final probabilities with development-only predictions; compare sigmoid and, only with sufficient data, isotonic calibration. Calibration can deteriorate after transport.

Reduce the panel inside training folds. Compare compact and expanded panels on identical eligible isolates and separately report each panel's population coverage. A reasonable exploratory compact-panel goal is within 0.02 AUROC of the expanded model in development, accompanied by no material operating-point degradation; this is a proposed study margin, not a clinical standard.

## 10 Metrics, uncertainty and sample planning

Report each target, cohort and major subgroup separately: n, R/non-R/S/I counts, AUROC, PR-AUC, balanced accuracy, sensitivity, specificity, PPV, NPV, Brier score, log loss, calibration intercept/slope and reliability curves. Accuracy is secondary. PR-AUC and predictive values depend on prevalence; show that context.

At a frozen binary threshold, report FN/R as the false-negative fraction among resistant isolates. For a three-output system, separately report resistant isolates accepted as non-resistant, resistant isolates deferred, and accepted coverage. Formal AST very-major-error terminology should only be used with the corresponding categorical reference and denominator definition.

Use paired confidence intervals for model differences on the same test isolates. Bootstrap at the highest defensible independent level, such as patient or site, rather than treating correlated rows as independent. If there are few sites, emphasize site-specific results and the uncertainty in site-level generalization.

For illustration, estimating 95% sensitivity within approximately ±3 percentage points requires about 203 independent resistant observations using n = 1.96² × 0.95 × 0.05 / 0.03². A similar specificity calculation requires its own non-resistant denominator. This normal approximation is planning guidance, not a sufficient sample-size justification: clustering, exclusions and rare strata increase requirements, and final intervals should use an appropriate binomial or clustered method. With zero errors in 100 independent cases, the approximate 95% upper error bound is still 3%.

Target at least roughly 200 observations of each binary class in the primary external comparison if feasible, with formal precision planning after the pilot. Tiny NDM/OXA/species subgroups remain exploratory. Training adequacy must be evaluated using grouped learning curves and model stability; there is no universal adequate total sample count.

## 11 Discovery analysis and deferral

Build a source-to-source transfer matrix and identify where error increases. Sequentially examine harmonized labels, shared panel availability, species mixture, collection period and known mechanism composition. Matching or reweighting analyses require overlapping covariate support and sensitivity checks. They describe associations under assumptions; they do not causally partition failure into biological components.

Analyze mechanism effects only among adequately characterized isolates, while documenting who was selected for genotyping. Typed isolates can be enriched for resistance. Do not infer that unknown isolates are mechanism-negative or generalize a selectively typed subset to all isolates without justification.

Prespecify two or three biologically motivated interaction tests and a replication cohort. Favor patterns that survive species-stratified analysis, source adjustment, alternative feature encodings and independent replication. A signal that vanishes under these controls is still informative about model failure, but is not a new resistance mechanism.

Use a simple first deferral policy: no prediction for an unsupported species, incompatible method, insufficient panel or out-of-scope input; defer intermediate-confidence predictions using thresholds fixed in development. Report coverage-error curves in every cohort. High model confidence does not guarantee correctness under shift. Conformal prediction is an optional later comparison, with no assumption that nominal coverage survives arbitrary distribution changes.

For discordant or uncertain cases, the next research step is independent review of AST, provenance and existing molecular evidence by microbiology collaborators. Any later experimental validation requires its own approved design. The current deliverable is computational evidence and a ranked set of hypotheses, not a demonstrated causal mechanism.

## 12 Engineering structure and compute

Use Python with a reproducibly locked environment, columnar storage such as Parquet, explicit schema validation, a configuration-driven workflow and reproducible reporting. Package versions should be chosen and pinned at implementation, after compatibility checks.

Suggested modules: ingestion; schema; drug/species normalization; MIC parsing; breakpoint interpretation; duplicate resolution; cohort construction; split generation; feature construction; model fitting; calibration; evaluation; explanation; reporting. Notebooks should explore results, while reusable modules generate authoritative artifacts.

Each run records input hashes, inclusion/exclusion counts, breakpoint version, feature allowlist, split checksum, configuration, seed, code revision, model artifact, probabilities, threshold decisions and metrics. Keep restricted raw data outside public Git; share scripts, metadata and licensed derived outputs as permitted.

Mandatory checks: isolate/patient overlap across splits; forbidden target features; missing-as-zero errors; MIC bound parsing; incompatible labels; genotype unknown-versus-negative handling; transformations fitted outside training; prediction/label alignment; and metric denominators. Use synthetic fixtures for software checks only, never performance evidence.

Your previously described 16 GB laptop is a reasonable pilot environment for a compact panel and CPU tree models. It is not a guaranteed full-dataset runtime. Avoid dense repeated copies of a melted multi-million-row table; load relevant columns and species, use efficient dtypes and cache normalized data. Measure memory/time on 10k and 100k isolates before scaling. Move to larger RAM only if profiling requires it. GPU use is optional, not a prerequisite.

Deliver a command-line research workflow and report first. Build a demonstration interface after the scientific gates pass. Any interface must show the model version, supported population, missing inputs, resistance probability and deferral state, without presenting research predictions as verified AST results.

## 13 Schedule and responsibilities

The following 14-week sequence assumes data access arrives early and a microbiology reviewer is available. If access stalls, schema and pipeline work can continue, but biological conclusions cannot.

| Period | Work | Owner | Exit artifact |
|---|---|---|---|
| Weeks 1-2 | Protocol, literature corrections, source inventory, access preparation, pilot counts | Samad and biology/data lead | Feasibility memo and frozen question |
| Weeks 3-4 | Normalize measurements, audit labels, duplicates and mechanisms | Data lead with microbiology review | Versioned cohort and QC report |
| Weeks 5-6 | Freeze splits; implement simple and tree baselines | ML collaborator | Reproducible baseline benchmark |
| Weeks 7-8 | Nested tuning, calibration, panel ablation, missingness tests | ML collaborator and data lead | Frozen model and threshold specification |
| Weeks 9-10 | Locked external and temporal evaluation | Evaluation lead | External results with uncertainty |
| Weeks 11-12 | Mechanism subgroups, transfer analysis, replication checks | Joint biology and ML review | Supported findings and failure analysis |
| Weeks 13-14 | Reproduction run, figures, model/data cards and manuscript outline | Joint team | Auditable research release |

If one person fills all roles, preserve the same separation through frozen configurations and delayed access to held-out labels.

## 14 Decision gates and fallback routes

| Gate | Pass condition | If it fails |
|---|---|---|
| Data feasibility | Linked target and eligible panel with sufficient class variation | Change source, narrow target, or explicitly broaden CPE cohort |
| Label integrity | Traceable measured target and compatible interpretation | Quarantine ambiguous rows or analyze a narrower compatible subset |
| Independence | Defensible group separation and source-overlap audit | Describe weaker validation accurately; seek additional source |
| Incremental value | Improvement over simple baselines with uncertainty reported | Retain simpler model or publish a methodological null result |
| External transport | Useful operating point and calibration on locked cohort | Diagnose shift; test separately labeled adaptation |
| Biological replication | Prespecified association persists in an independent cohort | Keep it exploratory; do not claim discovery |
| Workflow value | Inputs arrive in time and output improves a measured workflow | Limit claim to retrospective panel completion or research triage |

Do not set a universal clinical acceptance threshold before the intended action and consequences are defined. Candidate research operating points, such as thresholds targeting 95% sensitivity in development, should be evaluated with external confidence intervals and coverage rather than declared safe from their point estimates.

## 15 Figures and publication package

Prepare a cohort flowchart; coverage and class-count matrix; source-to-source transfer heatmap; PR/ROC curves; calibration plots; operating-point errors with confidence intervals; species/mechanism forest plot; compact-panel trade-off; coverage-error curve; and replicated feature-association analysis. Every figure must have a machine-readable source table and reproducible script.

The release should contain the protocol, eligibility rules, data dictionary, QC exclusions, split manifests or permitted hashes, environment lockfile, trained model where permitted, evaluation scripts, data/model cards, known limitations and source-access instructions. Assess performance on real retained data; synthetic examples document software behavior only.

**Strongest defensible future claim:** a defined phenotype panel predicts a specific carbapenem outcome across specified independent populations, with quantified failure modes and independently replicated mechanism-associated differences. A genuinely new biological mechanism, universal generalization, treatment benefit and replacement of laboratory AST would each require additional evidence.

## 16 First ten working days

1. Freeze the target, organism scope, prediction time and no-carbapenem input policy.
2. Correct the bibliography and extend the comparison matrix to earlier cross-antibiogram methods.
3. Prepare source requests and record access conditions; verify independent-source candidates.
4. Implement the data dictionary, provenance ledger and drug/species mappings.
5. Extract a pilot panel and count target classes, mechanisms and source overlap.
6. Review MIC operators, standards, methods and uncertain labels with a microbiologist.
7. Decide whether the CPE-only question is feasible or needs a prespecified broader cohort.
8. Create immutable group split manifests and reserve the external cohort.
9. Run the prevalence, species-only, one-feature and logistic baselines on development data.
10. Review the feasibility report and learning curves before expanding model complexity.

## References and source status

The four supplied documents were read as project inputs. The project brief and related-work notes are planning documents, not primary scientific evidence. References below support the specific background and data-access statements; proposed experiments and gates are recommendations developed for this project.

1. Emeraud C et al. Direct carbapenemase typing from disc diffusion antibiograms with MALCA. Nature Communications (2026). https://doi.org/10.1038/s41467-026-72713-0 — supplied full PDF reviewed, including methods and access restrictions.
2. Valavarasu S, Sangu Y, Mahapatra T. Prediction of antibiotic resistance from antibiotic susceptibility testing results from surveillance data using machine learning. Scientific Reports (2025). https://doi.org/10.1038/s41598-025-14078-w — supplied full PDF and publisher methods reviewed.
3. Muhsal LK et al. CarbaDetector. Nature Communications (2025). https://doi.org/10.1038/s41467-025-66183-z — publisher record retrieved; exact numerical comparisons are not used in this protocol.
4. Andreassen S et al. Interpretative reading of the antibiogram—a semi-naïve Bayesian approach. Artificial Intelligence in Medicine (2015). https://doi.org/10.1016/j.artmed.2015.08.004 ; author institution record: https://vbn.aau.dk/en/publications/interpretative-reading-of-the-antibiogram-a-semi-na%C3%AFve-bayesian-a/ — abstract-level precedent; not a full methodological replication.
5. Vivli AMR. Data Request Process Overview. https://amr.vivli.org/resources/data-request-process-overview/ — access requirements checked 4 October 2026.
6. EUCAST. Definitions of S I and R. https://www.eucast.org/bacteria/clinical-breakpoints-and-interpretation/definition-of-s-i-and-r/ — category semantics checked 4 October 2026.
7. EUCAST. Colistin gradient tests and disks have no place in susceptibility testing. https://www.eucast.org/news-detail/colistin-gradient-tests-and-disks-have-no-place-in-susceptibility-testing/ — method warning checked 4 October 2026.
8. NCBI. Antibiotic Susceptibility Test Browser. https://www.ncbi.nlm.nih.gov/pathogens/ast/ — submitter-provided phenotype provenance and QC limitations checked 4 October 2026.
