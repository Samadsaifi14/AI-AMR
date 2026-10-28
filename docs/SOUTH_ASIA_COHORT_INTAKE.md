# South Asia cohort intake

This cohort is a 360-isolate Excel workbook with one isolate per row and paired MIC and reported S/I/R columns for 16 antibiotics. The browser importer reads the first worksheet and can pair the `*_MIC_mg_L` and `*_SIR` columns into one isolate–drug observation.

## Use in the browser

1. Choose **Use my own data** and upload `South_Asia_AMR_Wide_Matrix.xlsx`.
2. Keep both result columns for each antibiotic. Check the suggested mappings, especially `#BioSample` as isolate ID, `Scientific name` as species, `Isolation source` as specimen, `Location` as the original location field, and `Testing standard` as standard.
3. Run **Check my data** and review exclusions and target counts before training.
4. For a South Asia analysis, include only rows whose location is India, Pakistan, or Nepal. The current browser flow does not filter rows by location, so make that subset in a local copy first or use the prepared local import workflow. Keep the original workbook unchanged.
5. Select meropenem or imipenem and use the matching exploratory recipe in `configs/`. Do not select colistin or ceftazidime-avibactam as a South Asia target with this panel.

## Cohort counts and limits

The workbook has 360 unique BioSample IDs and 360 unique isolate IDs. It includes 107 rows from India, Pakistan, or Nepal, but only **2 are from India** (both *E. coli*). It therefore cannot support an India-only model or India-specific performance claim.

Among South Asian *E. coli* and *K. pneumoniae* records, after requiring at least three of the six predictor-drug categories and keeping only reported resistant/susceptible target labels, there are 93 meropenem records (29 resistant, 64 susceptible) and 91 imipenem records (28 resistant, 63 susceptible). Intermediate results are excluded from these binary recipe counts. These counts are preliminary; the app may exclude more rows during data checks or its held-out split.

Colistin has only 24 matching resistant/susceptible labels in that species/geography subset (22 resistant, 2 susceptible), so the held-out workflow cannot assess both classes reliably. There are no matching South Asian ceftazidime-avibactam labels in the workbook.

## Data details still needed

The file includes CLSI/EUCAST labels but not their edition/year, and does not identify the AST method for most records. Platform is reported for 210 isolates, and the vendor for 205; these fields are mostly Vitek/BioMérieux where present. To improve comparability later, obtain the source publication or dataset citation, exact breakpoint-standard editions, AST method and panel details, laboratory/site identifiers, and any QC records. Do not fill these from assumptions.

The mapping preserves the original `Location` text in the region field. It does not convert composite values such as `India: Anna Nagar, Chennai, TN` into normalized countries or districts. The raw workbook stays with the user; only mapping, recipes, and intake guidance are committed to the repository.
