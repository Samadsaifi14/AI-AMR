"""Reproduce the full retrospective audit without changing sample-size gates or test thresholds."""
import json
import sys
import argparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from amr_discovery.data import build_cohort
from amr_discovery.validation import validation_suite
from amr_discovery.reporting import write_report

parser = argparse.ArgumentParser()
parser.add_argument('--out', default='results/audit_v07', help='New output directory; existing results are never overwritten')
args = parser.parse_args()
out = Path(args.out)
if not out.is_absolute():
    out = root/out
out.mkdir(exist_ok=False)
specs = [('public_all_sources', root/'data/raw/ncbi_kp_human/observations.csv',
          json.loads((root/'configs/public_xgboost_v07.json').read_text()), True)]
for drug in ['meropenem', 'imipenem']:
    cfg = json.loads((root/f'data/curated/india_categorical_v05/{drug}_config.json').read_text())
    data = root/'data/curated/india_categorical_v05/observations.csv'
    specs.append((f'india_{drug}', data, cfg, True))
    strict = dict(cfg, comparability_policy='strict', standard='EUCAST', standard_version='16.0',
                  allow_unversioned_reported=False)
    # This is an eligibility filter, never a claim that the historical measurements used this version.
    specs.append((f'india_{drug}_strict', data, strict, False))
    specs.append((f'india_{drug}_mechanism', data, dict(cfg, mechanism_cohort='NDM_OR_OXA48'), False))
specs.append(('india_biosample', root/'data/raw/ncbi_india/observations.csv',
              json.loads((root/'configs/public_pilot.json').read_text()), False))
specs.append(('india_icu_quarantine', root/'data/curated/india_surgical_icu_2026/candidate_observations_QUARANTINED.csv',
              dict(cfg, target='meropenem', standard='UNKNOWN_REVIEW_REQUIRED'), False))
summary = []
for name, data, cfg, fit in specs:
    folder = out/name
    folder.mkdir()
    cohort, audit, exclusions, features = build_cohort(data, cfg)
    cohort.to_csv(folder/'cohort.csv', index=False)
    exclusions.to_csv(folder/'exclusions.csv', index=False)
    (folder/'audit.json').write_text(json.dumps(audit, indent=2))
    (folder/'configuration.json').write_text(json.dumps(cfg, indent=2))
    write_report(folder, audit)
    record = {'cohort': name, 'eligible': len(cohort), 'class_counts': audit['class_counts'],
              'raw_isolates': audit['raw_isolates'], 'input_sha256': audit['input_sha256']}
    if fit:
        suite = validation_suite(cohort, features, cfg, audit, folder)
        record['experiments'] = suite['experiments']
    summary.append(record)
    (out/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(name, len(cohort), audit['class_counts'], flush=True)
