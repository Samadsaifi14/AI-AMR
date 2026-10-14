# First execution findings

These are exploratory research runs on public measured data, not validated clinical results or a mechanism discovery.

The NCBI query returned 1,804 BioSamples with 25,387 antibiogram rows. Curation retained 499 isolates for the initial CLSI reported R-versus-S pilot, comprising 229 resistant and 270 susceptible isolates. Unknown source records were additionally excluded for the BioProject holdout experiment.

| Evaluation | Holdout n | Resistant | Susceptible | AUROC | Sensitivity at frozen threshold | Specificity |
|---|---:|---:|---:|---:|---:|---:|
| Internal isolate holdout | 100 | 46 | 54 | 0.962 | 0.978 | 0.741 |
| PRJNA278886 source holdout | 165 | 29 | 136 | 0.781 | 0.000 | 1.000 |

Each model was selected by grouped development cross-validation; the internal and source holdouts consequently selected different models. These are two exploratory experiments, not a paired estimate of one frozen model's degradation. Source holdout selected a shallow random forest; internal holdout selected logistic regression. The source model's frozen operating point called every held-out isolate non-resistant and missed all 29 resistant isolates.

The internal AUROC bootstrap interval was approximately 0.919 to 0.991. The source holdout interval was approximately 0.702 to 0.846. These isolate/component intervals do not quantify site-level generalization uncertainty or unknown patient/lineage dependence.

This is evidence of a failure of the chosen source-transfer experiment, particularly its transported calibration and operating threshold. It does not prove a particular biological cause. Acquisition selection, measurement differences, population composition, censored values and missing panels are candidate explanations requiring controlled follow-up.

Patient identifiers and curated mechanism annotations are unavailable. The model is not NDM/OXA-48-specific. Breakpoint versions are often unspecified, and original CLSI labels were used rather than reinterpreting measurements. The dataset is not representative of any country's population.

## Next experiments

1. Compare source-specific measurement ranges, censoring and missingness without altering the retained heldout result.
2. Audit target interpretation standards and assay protocols using source publications.
3. Obtain another compatible collection with known mechanisms and a documented recruitment frame.
4. Preregister a fresh validation split and a separate local calibration subset for an adaptation experiment.
5. Evaluate adaptation on new untouched outcomes; never advertise a threshold tuned on this failed holdout as independent validation.

An honest failed transfer is a useful first result. It establishes the need for the study's core scientific question rather than resolving it.
