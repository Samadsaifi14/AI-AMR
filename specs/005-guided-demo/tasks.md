# Tasks: Guided first-run and stronger demo

**Input**: Design documents from `/specs/005-guided-demo/`

## Phase 1: Home and guided demo

- [x] T001 [US1] Replace the current welcome links with beginner Home cards and a concise 4-step journey in `web/index.html`.
- [x] T002 [US1] Make the demo action select the synthetic fixture, explain its contents, and start the canonical training flow in `web/onboarding.js`.
- [x] T003 [US1] Show plain-language demo verdict and false-negative/false-positive explanations from actual run metrics in `web/app.js`.
- [x] T004 [US1] Name first-load runtime stages and provide retry-oriented errors in `web/worker.js` and `web/app.js`.
- [x] T005 [US1] Style the Home cards, progress, and demo explainer responsively in `web/style.css`.

## Phase 2: Resume on this device

- [x] T006 [US2] Persist and restore workflow source, configuration, and uploaded CSV through IndexedDB with clear-storage and quota fallback in `web/onboarding.js`.
- [x] T007 [US2] Allow the restored local CSV to enter the existing upload workflow without fabricating a browser file input in `web/app.js`.
- [x] T008 [US2] Warn before closing during active computation and disclose local persistence on Home in `web/onboarding.js` and `web/index.html`.
- [x] T009 Document implementation evidence and remaining limitations in `specs/005-guided-demo/verification.md`.
