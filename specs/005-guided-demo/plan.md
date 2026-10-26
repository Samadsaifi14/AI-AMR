# Implementation Plan: Guided first-run and stronger demo

**Branch**: `005-guided-demo` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

## Summary

Make the synthetic demo a one-action guided training flow, explain the real run outputs in plain language, name runtime setup stages, and save/resume the current browser workflow locally. Continue using the existing HTML/CSS/JavaScript shell and canonical Python worker for all scientific computation.

## Technical Context

**Language/Version**: Browser JavaScript and HTML/CSS; Python 3.12 source executed through pinned Pyodide 0.29.3
**Primary Dependencies**: Existing app scripts, Web Worker, Pyodide, IndexedDB API
**Storage**: Browser IndexedDB for workflow state and optional uploaded CSV; browser memory remains fallback
**Testing**: Existing `npm run build`, `npm run test:web`, browser runtime checks, and `python -m pytest -q` are defined by the project; do not change scientific contracts
**Target Platform**: Modern desktop browsers, responsive mobile presentation
**Project Type**: Static browser research application
**Constraints**: All uploaded content stays on-device; do not claim the local cache is encrypted or permanent; demo outputs remain synthetic; respect reduced motion
**Scale/Scope**: Home, one demo journey, one local resume checkpoint

## Constitution Check

- Canonical Python remains the source of scientific behavior: PASS.
- Target leakage, held-out evaluation, labels, provenance, and uncertainty controls stay unchanged: PASS.
- Browser-local files remain local: PASS; persistence must disclose local storage and expose clear action.
- No clinical or accuracy claim is added: PASS.

## Project Structure

```text
web/index.html        # Home cards, stepper, progress/result explanation
web/onboarding.js     # Guided demo, local save/resume, close warning
web/app.js            # Resume restored upload and actual demo result rendering
web/worker.js         # Clear named runtime loading stages
web/style.css         # Responsive Home and guided demo styling
specs/005-guided-demo # Specification, plan, tasks, and verification notes
```

## Implementation Notes

The demo starts the current synthetic source and invokes the existing `train` operation, which performs its own full cohort audit. No metric values are hard-coded. IndexedDB stores the current source, configuration, selected upload, and last completed result/export as a local checkpoint. A restored result can be reviewed and downloaded, but the fitted model is not loaded for new predictions; the user must rerun the experiment. Browser warning is limited to active unsaved computation.

## Risks

- Browser storage quotas vary and may reject a large CSV; keep the workflow usable and show a clear fallback.
- The Pyodide runtime downloads a sizable first-run package set; avoid a fixed short duration promise.
- The synthetic demo's model may report a failed operating target; explain this honestly as software demonstration behavior.
