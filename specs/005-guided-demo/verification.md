# Verification: Guided beginner workflow

**Date**: 2026-10-26

## Implementation review

- Home offers a synthetic one-action demo, guided import, and local resume/clear actions.
- CSV and first-worksheet XLSX are read in the browser. Long/wide suggestions, editable mappings, antibiotic-column selection, a preview and change log precede creation of a separate canonical analysis CSV.
- The original uploaded file and missing values are preserved. The browser does not send uploaded files to a service. Local IndexedDB stores the workflow and source when the browser permits it.
- Recipe counts come from recorded reported S/R labels. MIC values alone do not create class labels. The engine performs the full audit again after preliminary counts.
- Data-check status reflects engine audit output. Result badge reflects existing holdout and independent-evaluation gates. No accuracy headline is used.
- Results include a summary, confusion counts, exact confidence intervals, model comparisons and subgroup metrics by source and species. The former advanced tools are under Lab bench.
- Save my experiment downloads the ZIP and invokes the report's browser Print dialog for Save as PDF; the HTML report is also available separately.
- Guide copy covers import, review, Recipe, result layers, local resume and export.

## Checks completed

- `npm run build` completed and packaged the current browser application.
- JavaScript syntax checks completed for the app, onboarding, guided UI and import modules.
- Python syntax compilation completed for `browser_bridge.py`; `git diff --check` found no whitespace errors.

## Not run

Interactive browser and scientific runtime checks were not completed. The available browser preview could not access the local app, and the installed Playwright package had no browser executable available. No end-to-end success is claimed. XLSX support is limited to the first worksheet and relies on cached cell values; complex workbook features and date serial interpretation may require exporting to CSV. PDF creation depends on the browser's Print-to-PDF dialog. IndexedDB availability and quota vary by browser.
