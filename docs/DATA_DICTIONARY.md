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
| collection_date | Collection date; required for temporal splitting |
| host | Human host must be confirmed for the default cohort |
| specimen | Original specimen annotation |
| drug | Single antibiotic name or reviewed alias |
| measurement | Positive MIC value; embedded bounds accepted; combination ratios rejected |
| operator | =, ==, <, <=, >, >=; preserved rather than erased |
| units | mg/L or supported equivalent ug/mL; mm is rejected by the MIC path |
| method | MIC or supported dilution method |
| platform | Original platform, retained for curation |
| standard | Interpretation standard such as CLSI or EUCAST |
| standard_version | Reported release; blank requires explicit exploratory handling |
| reported_sir | Measured reported phenotype; S/R/I or recognized full name |
| ndm | positive, negative or unknown; not inferred from meropenem resistance |
| oxa48 | OXA-48-like evidence state, not any OXA family |
| mechanism_evidence | Required reference for every positive/negative annotation |
| evidence_class | measured_public, measured_authorized, or synthetic; cannot mix synthetic/real |
| accession | Original accession |
| source_row | Original file and row/accession pointer |

Patient IDs and all identifiers are excluded from feature inputs. Do not enter direct personal identifiers; use permitted study pseudonyms. Mechanisms are cohort metadata only. Positive for one mechanism with the other unknown is not called a confirmed single-mechanism isolate.

The included parser handles NCBI BioSample XML, not arbitrary ATLAS spreadsheet layouts. Convert authorized source files into this explicit schema and retain mapping/version records before use.
