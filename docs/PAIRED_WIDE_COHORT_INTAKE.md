# Paired wide cohort intake

The paired wide matrix is supported by the browser import and the explicit mapping at `configs/final_paired_amr_wide_matrix_mapping.json`.

## Browser workflow

1. Choose **Use my own data** and upload the supplied CSV.
2. The importer detects the `*_Phenotype` and `*_MIC_mgL` columns.
3. Keep both columns selected for each antibiotic. The browser merges them into one isolate-drug observation and preserves blank results.
4. Map the isolate ID to `#BioSample`, the species to `Scientific name`, source to the documented study or batch value, platform to `Laboratory typing platform`, and standard to `Testing standard`.
5. Set the source type to documented public measurements and run **Check my data** before selecting a target.

## Local workflow

```sh
python -m amr_discovery import-wide \
  --data final_paired_amr_wide_matrix.csv \
  --mapping configs/final_paired_amr_wide_matrix_mapping.json \
  --out data/private/final_paired_observations.csv

python -m amr_discovery run \
  --data data/private/final_paired_observations.csv \
  --config configs/final_paired_meropenem_exploratory.json \
  --out data/private/runs/final_paired_meropenem
```

The mapping does not invent country, host, collection date, patient linkage, testing method, CLSI edition, QC evidence, colistin, cefotaxime, or ceftazidime-avibactam measurements. These remain missing until documented source records provide them.

The supplied cohort supports only a meropenem feasibility run. It does not supply enough paired resistant isolates for imipenem or ceftazidime-avibactam, and it has no colistin column.