# Implementation plan

Keep buildless HTML/CSS/JS and the Pyodide worker calling Python. Extend the existing bridge with checked batch preparation and the CLI with prepare-batch. Use the existing schema/configurations and provenance gates. Render large result tables in pages of 25 with complete exports retained. Provide static guide and resources pages, guided demo/upload entry points, and session-state feedback. Use native Python and browser runtime tests plus UI checks. Publish the verified source to the existing authorized main branch and check its Vercel production deployment.

Follow-up uses canonical Python stdout for cohort/fold phases and a main-thread elapsed clock. Preserve all scientific calculations and data gates. Verify session state, runtime train/evaluate and live browser results.
