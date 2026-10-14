# Controlled learning verification

2026-10-14. Python suite: 110 passed. Static build, asset/source integrity and session UI checks passed. Native XGBoost CPU 3.0.5 compared with RF using development predictions only. Uploaded data and fitted models are excluded from Git and the site's source archive.

Uploaded export: 2626 rows, 1066 isolates, 2363 exact observation matches and 263 quarantined rows. Separate CLSI and EUCAST internal analyses used 234 and 186 eligible isolates. CLSI test: 47 (8 R/39 S), AUROC 0.9936, sensitivity 1.000, specificity 0.9744, 0 FN/1 FP; sensitivity exact lower 95% bound 0.6306. EUCAST test: 37 (12 R/25 S), AUROC 0.9800, sensitivity 1.000, specificity 0.8400, 0 FN/4 FP; sensitivity lower bound 0.7354. Both selected forest_depth4. Source PRJNA278886 challenge blocked at 3 resistant held-out isolates. No clinical or Indian accuracy is established. Research promotion was executed and correctly blocked for the internal CLSI version.

Safety contracts verified: provenance quarantine; reserved-identity training exclusion; fixed training drift bins; categorical missingness shifts; changed configuration rejection; incomplete/tampered version detection; portable relative registry paths; rejected promotion preserves the active version; reused sources are rejected before deserializing models. Live verification is recorded after deployment.
