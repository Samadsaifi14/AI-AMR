# Verification: Guided first-run and stronger demo

**Date**: 2026-10-26

## Completed implementation review

- Home now provides a single-action synthetic demo, own-data entry, and a conditional local-resume card.
- The demo uses the existing `demo` dataset and canonical `train` operation; the Python workflow still creates the audit, model, held-out evaluation, and export.
- Synthetic result counts are read from the run metrics and described as missed resistance and false alarms. No demo result counts are hard-coded.
- Progress messages name analysis-engine setup and map runtime output to check/train/test stages. Runtime errors direct users to retry or use the local Python guide.
- IndexedDB stores the selected source, configuration, selected upload CSV, and last completed result/export on this browser. The page discloses this, offers clear saved work, and warns before leaving during an active run. Resuming restores setup/input and the prior result/export; the model is not loaded for new predictions.
- The first-run guide matches the new flow and correctly distinguishes saved setup from the in-memory model.

## Not run

Automated browser, Python, build and runtime checks were not run in this change. No claim of successful end-to-end execution is made. The first-run CDN download and IndexedDB quota behavior remain dependent on the user's browser/network and need a browser run before release.
