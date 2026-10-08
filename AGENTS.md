# AMR project development

Use the canonical `amr_discovery` modules in both CLI and browser; do not duplicate scientific calculations in JavaScript. Keep changes on main when publishing within the authorized project scope.

Use the installed project-local Spec Kit skills under `.agents/skills` for bounded feature work. Record requirements, plan, tasks and actual verification in `specs/`. Read `docs/REEL_EVIDENCE.md` before adopting social-media suggestions.

Preserve target-antibiotic leakage controls, training-only preprocessing and predictor selection, patient/source grouping, measured labels, censoring, units and laboratory provenance. Never tune on evaluation outcomes or promise 100% future accuracy. New data batches are prepared, audited and trained as new experiments; fresh independent cohorts stay outside development merging.

Keep patient data under ignored `data/private/`; never publish private inputs or models. Browser uploads stay on-device. Do not add analytics, scraping credentials, databases or paid services without a specific authorized requirement.

Run `python -m pytest -q`, `npm run build`, `npm run test:web` and appropriate runtime checks for changed contracts. Verify UI source/configuration changes clear old models and exports. Keep beginner guide instructions aligned with actual commands. Motion must be optional and respect reduced-motion preferences.
