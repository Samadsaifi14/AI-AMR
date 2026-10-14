# Observation data dictionary

One row is a measured AST observation. Duplicate identical observations collapse; conflicting repeats are excluded, never averaged.

| Column | Meaning |
|---|---|
| isolate_id | Stable identifier, globally disambiguated across sources |
| source_id | Recruitment collection or BioProject identifier; not the repository name alone |
| patient_id | Optional source-scoped patient identifier; blank means unavailable |
| duplicate_group | Optional global identifier joining independently curated duplicates |
| species | Exact eligible species name |
| country | Collection country, not submission location |
| region | Observed geographical zone; a region is not an independent source or hospital |
| hospital_id | Verified recruitment hospital identifier; blank means unavailable |
| collection_date | Collection date; required for temporal splitting |
| host | Human host must be confirmed for the default cohort |
| specimen | Original specimen annotation |
| drug | Single antibiotic name or reviewed alias |
| measurement | MIC representation: positive numeric bound. Categorical AST: may be blank; no concentrations inferred |
| operator | =, ==, <, <=, >, >=; preserved rather than erased |
| units | mg/L or supported equivalent ug/mL; mm is rejected by the MIC path |
| method | MIC/dilution for numeric input; documented measured AST may use reported AST, disk diffusion or VITEK 2 in categorical input |
| platform | Original platform, retained for curation |
| standard | Interpretation standard such as CLSI or EUCAST |
| standard_version | Reported release; blank requires explicit exploratory handling |
| reported_sir | Measured reported phenotype; S/R/I/SDD or recognized full name. Blank is missing, never S |
| ndm | positive, negative or unknown; not inferred from meropenem resistance |
| oxa48 | OXA-48-like evidence state, not any OXA family |
| mechanism_evidence | Required reference for every positive/negative annotation |
| evidence_class | measured_public, measured_authorized, or synthetic; cannot mix synthetic/real |
| accession | Original accession |
| source_row | Original file and row/accession pointer |

Patient IDs and all identifiers are excluded from feature inputs. Do not enter direct personal identifiers; use permitted study pseudonyms. Mechanisms are cohort metadata only. Positive for one mechanism with the other unknown is not called a confirmed single-mechanism isolate.

The included parser handles NCBI BioSample XML, not arbitrary ATLAS spreadsheet layouts. Convert authorized source files into this explicit schema and retain mapping/version records before use.

Set `representation` to `mic` (default) or `categorical_ast`. Categorical predictors use five nominal states: S, I, R, SDD, missing. Target R-vs-S excludes I/SDD/missing. Breakpoint inference requires numeric MICs and is unavailable for categorical input. Unknown interpretation standards must remain explicitly unknown with exploratory handling, not invented CLSI/EUCAST metadata. The minimum observed panel still applies. Carbapenems and genotype/geography identifiers are blocked primary predictors in both representations.

## Laboratory comparability (v0.6)

Optional for exploratory imports; strict comparability requires documented values. `lab_id` is the actual testing laboratory, consistent across an isolate's panel; it is not inferred from source/region/hospital. `platform` identifies the instrument/system. `qc_reference` links the documented QC record and method suitability review. `panel_id` identifies the drug concentration panel. `tested_concentrations` is a JSON list of actual concentrations in the row's MIC units, e.g. `[0.5,1,2,4,8]` (quote this field in CSV); it is not inferred from the observed cohort range. Censored bounds must remain attached to their operator. Numeric panel checks apply only to discrete dilution data, not continuous gradient-strip results.

Configuration `comparability_policy` is `exploratory` (default) or `strict`. Strict mode requires `standard` EUCAST/CLSI and `standard_version`, lab, specific supported method and QC. Numeric strict mode also needs a documented ladder and panel ID. Categorical feature labels from another standard/version become missing and are counted; target mismatches exclude the isolate. Unknown interpretations remain exploratory, including when all rows carry the same unknown token. The strict profile checks documentation; independent analytical agreement must still be established. See `LAB_HARMONIZATION_V06.md`.
