"""Audit the COMPLETE public 266-isolate AST supplement without inventing MICs."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd


def audit_file(path, out):
    d = pd.read_excel(path, header=2)
    d = d.dropna(subset=['Isolate ID'])
    if len(d) != 266 or d['Isolate ID'].duplicated().any():
        raise ValueError('Expected 266 distinct published isolate IDs; inspect file revision.')
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    d.to_csv(out / 'all_266_published_rows.csv', index=False)
    supported = d.Organism.isin(['Escherichia coli', 'Klebsiella pneumoniae'])
    exclusions = pd.DataFrame({'isolate_id': d['Isolate ID'], 'species': d.Organism,
        'reason': ['no_numeric_MIC_panel' if x else 'unsupported_species' for x in supported]})
    exclusions.to_csv(out / 'exclusions.csv', index=False)
    panel = ['Cefepime','Ceftazidime','Ciprofloxacin','Gentamicin','Amikacin']
    symbols = sorted({str(v) for c in panel for v in d.loc[supported,c].dropna()})
    result = {'status': 'INCOMPATIBLE_WITH_FROZEN_MIC_MODEL', 'india_accuracy_established': False,
        'doi': '10.1038/s44259-026-00185-9', 'source_url': 'https://www.nature.com/articles/s44259-026-00185-9',
        'file_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'raw_isolates': len(d), 'row_subsampling': False, 'supported_species_isolates': int(supported.sum()),
        'eligible_MIC_isolates': 0, 'feature_symbols': symbols,
        'target_counts_supported_species': {t: d.loc[supported,t].fillna('missing').value_counts().to_dict()
                                            for t in ['Meropenem','Imipenem']},
        'species_counts': d.Organism.value_counts().to_dict(),
        'limitations': ['Published predictor fields contain susceptibility categories, not numeric MICs.',
                        'Do not map R/S/I/SDD to invented MIC concentrations.',
                        'No per-isolate AST standard/version or patient IDs in this supplement.',
                        'Resistance-selected tertiary-care cohort from two geographical zones; not national sampling.']}
    (out / 'audit.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--data', required=True);p.add_argument('--out', required=True)
    a=p.parse_args();print(json.dumps(audit_file(a.data,a.out),indent=2))
