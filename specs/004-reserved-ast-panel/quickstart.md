# Quickstart: supplied AST workbook

1. Install the project’s local dependencies, including the optional workbook reader.
2. Keep the workbook under `data/private/` and import it:

   ```bash
   python -m pip install -e '.[workbooks]'
   python -m amr_discovery import-asts-workbook \
     --data 'data/private/asts (6).xlsx' \
     --out data/private/asts_20261026
   ```

3. Run the model separately for each reserved target. Each output path must be new:

   ```bash
   python -m amr_discovery run --data data/private/asts_20261026/observations.csv \
     --config configs/reserved_ast_meropenem.json --out data/private/runs/meropenem
   python -m amr_discovery run --data data/private/asts_20261026/observations.csv \
     --config configs/reserved_ast_imipenem.json --out data/private/runs/imipenem
   python -m amr_discovery run --data data/private/asts_20261026/observations.csv \
     --config configs/reserved_ast_colistin.json --out data/private/runs/colistin
   python -m amr_discovery run --data data/private/asts_20261026/observations.csv \
     --config configs/reserved_ast_ceftazidime_avibactam.json --out data/private/runs/ceftazidime_avibactam
   ```

4. Review each `report.html`, `metrics.json`, `test_predictions.csv`, `split_manifest.csv`, and `exclusions.csv`. A target with no outcomes is reported as unavailable. A target with few positive examples still runs where a grouped holdout can be formed, but stays exploratory.
5. To use the browser, upload the generated `observations.csv`, choose **Load reserved prediction panel**, choose the target and run Audit, then Train & evaluate. The upload stays in the browser tab and is not added to static data assets.

Expected acceptance checks:

- All 2,555 workbook observations are accounted for in the import manifest.
- Predictor columns contain only the listed non-reserved antibiotics and optional species.
- The target result is absent from the predictor matrix.
- Isolate groups do not cross the approximate 70/30 boundary.
- The report includes errors and unavailable metrics for single-class test partitions.
