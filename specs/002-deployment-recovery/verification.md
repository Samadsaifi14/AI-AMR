# Verification — 2026-10-14

Recovery commit: 20dde302b4c8639d35ee08d6ce34331911015f5d. Production deployment: dpl_6vLvKwkmAyfQgKhMLvLRck83UVSP, READY, assigned to ai-amr.vercel.app.

Cause: c6ff178 removed the browser application; the replacement Python deployment failed on import with ModuleNotFoundError: fastapi. Its entrypoint had no homepage, loaded a JSON metrics report as a joblib model, and used a mismatched breakpoint dictionary key. The recovery serves the existing browser workflow; it does not enable that replacement API or certify its predictions.

Local checks: python -m pytest -q: 99 passed, 1 skipped; npm run build, npm run test:web and node scripts/verify-session-ui.mjs passed.

Live checks: homepage and guide loaded; Try a guided demo selected synthetic practice data; Audit data completed (237 eligible of 240 input isolates); Train & evaluate completed and enabled experiment ZIP export. Synthetic prediction with cefepime=16, ceftazidime=8 and ciprofloxacin=4 returned a finite estimate and preserved the defer/model-not-validated software-demonstration status. No clinical or India accuracy was established. No runtime log entries were found for the recovered static deployment.
