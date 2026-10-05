# AI-AMR · AMR Research Lab

A browser-local team lab for measured antibiotic susceptibility research. It trains and evaluates meropenem resistance models, audits source observations, exports reproducible runs, and explores development-only gene co-occurrence and geographic proximity.

The existing publication is https://amr-research-lab.samads14122003.chatgpt.site. This repository is prepared for a separate Vercel deployment. Its Vercel URL will be recorded after deployment is confirmed.

**India accuracy and clinical validity are not established.** The public India BioSample cohort has one eligible resistant isolate and no eligible susceptible isolate. The public source-held-out test missed all 29 resistant isolates. The lab displays failed operating points rather than treating them as successful validation. It does not predict human genetics or ethnicity from location.

## Team workflow

Choose the synthetic fixture to test software behavior, or upload an authorized long-format AST CSV. Audit eligibility, pre-specify the split and operating threshold target, train, inspect the locked holdout result and export the ZIP before closing the tab. Each browser session processes its own data; there is no central database or shared persistent model. No paid inference API, server-side training or GPU service is used.

[Team instructions](docs/TEAM_LAB.md) · [Data dictionary](docs/DATA_DICTIONARY.md) · [Implementation plan](docs/ORIGINAL_IMPLEMENTATION_PLAN.md)

## Build the website

Requires Node 20 or newer. No frontend package dependencies are needed.

```sh
npm ci --ignore-scripts
npm run build
npm run test:web
```

The build generates `dist/python-sources.json` from the canonical Python modules; it does not maintain a second handwritten implementation. It copies source-derived public data and the synthetic fixture into static assets. `vercel.json` specifies the static output directory. Uploads remain in browser worker memory. Scientific packages download from the pinned Pyodide distribution on jsDelivr.

The website's download ZIP is the tested v0.2 scientific source snapshot. This repository also contains the Vercel configuration and repeatable build verification.

## Test the actual browser Python runtime

```sh
npm install --prefix test-runtime pyodide@0.29.3
npm run build
npm run test:runtime
```

This executes the same WebAssembly Python engine used by the browser, under Node. It tests synthetic training, source-derived reports and ZIP exports, test predictions, unknown gene calls, India sample gates and the public source holdout. It does not establish browser visual or click-through correctness.

## Run the local Python pipeline

Python 3.12 was used for the local pilot. Browser and local package versions are recorded separately; selection and numeric outputs can differ.

```sh
python -m pip install -r requirements-local.lock.txt
python -m pip install -e . --no-deps
python -m pip install pytest
python -m pytest -q
python scripts/materialize_data.py
python -m amr_discovery run --data data/raw/ncbi_kp_human/observations.csv --config configs/public_source_holdout.json --out results/NEW_SOURCE_RUN
```

Do not reuse a test set to tune model selection or thresholds. A new independently recruited cohort is required for confirmatory validation. Joblib files should only be loaded from trusted experiments with compatible package versions; the web app does not accept model-file uploads.

## GitHub and Vercel

GitHub repository: https://github.com/Samadsaifi14/AI-AMR. The public repository was supplied by the project owner. The tested source has been pushed. The Vercel project is connected at https://ai-amr.vercel.app/.

After the tested source has been pushed, link that repository in the existing Vercel Hobby workspace, with repository root as the project root. The build and output settings are already in `vercel.json`. Do not select paid add-ons or change the account's plan. A production deployment should only be reported as live after Vercel returns READY and the final URL is verified.

## Source provenance

`data/raw/` contains publicly retrieved BioSample records and Indian study supplements with request details and SHA-256 manifests. Original user-uploaded source documents and account credentials are not included. The Indian ICU candidates remain quarantined pending interpretation-standard/units and identity-link review; see their curation summary. No gene absence, patient coordinates or collection dates were invented.

Cached BioSample XML and redundant input copies are retained in `downloads/AMR_Discovery_Source.zip`. The main AST table is committed once as deterministic gzip; the web build expands it without modifying its contents. The original query and SHA-256 manifests remain in the repository.

## Full-cohort validation update

See [audit and ordered team tasks](docs/AUDIT_V03.md). Run `python -m amr_discovery validate --data <observations.csv> --config <reviewed.json> --out <new-folder>` to audit every source without subsampling. The website now provides **Validate all sources** and simple split controls. Complete wide CSV files can be normalized with `import-wide`; see the reviewed-mapping instructions. India accuracy is still unestablished.
