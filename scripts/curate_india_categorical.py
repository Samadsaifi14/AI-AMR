"""Complete, traceable categorical AST import. No MIC/standard/gene inference."""
import argparse
import json
from pathlib import Path
import pandas as pd

GRAM_NEGATIVE = ['Escherichia coli','Klebsiella pneumoniae','Acinetobacter baumannii',
    'Pseudomonas aeruginosa','Proteus mirabilis','Burkholderia cepacia',
    'Providencia rettgeri','Enterobacter cloacae']
DRUGS = ['meropenem','imipenem','cefepime','ceftazidime','ciprofloxacin','gentamicin','amikacin','colistin']


def curate(path, out):
    d=pd.read_excel(path, header=2).dropna(subset=['Isolate ID'])
    if len(d)!=266 or d['Isolate ID'].duplicated().any():
        raise ValueError('Expected the complete 266-isolate supplement; inspect revisions.')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for i,r in d.iterrows():
        date=pd.to_datetime(r['Date'],unit='D',origin='1899-12-30') if isinstance(r['Date'],(int,float)) and pd.notna(r['Date']) else pd.to_datetime(r['Date'],errors='coerce')
        for drug in DRUGS:
            sir=str(r[drug.capitalize()]).strip() if pd.notna(r[drug.capitalize()]) else ''
            rows.append(dict(isolate_id=str(r['Biosample_accession']),source_id='PRJNA1273658',
                source_row=f'S data 1!row{i+4};published_id={r["Isolate ID"]}',species=r['Organism'],
                country='India',region=r['Geoclimatic Zone'],hospital_id='',patient_id='',duplicate_group='',
                collection_date=date.strftime('%Y-%m-%d') if pd.notna(date) else '',host='human',
                drug=drug,measurement='',operator='',units='',method='reported AST',
                standard='UNSPECIFIED_REPORTED',standard_version='',reported_sir=sir,
                evidence_class='measured_public',ndm='unknown',oxa48='unknown',mechanism_evidence=''))
    pd.DataFrame(rows).to_csv(out/'observations.csv',index=False)
    cfg=dict(target='meropenem',representation='categorical_ast',species=GRAM_NEGATIVE,
        features=DRUGS[2:],min_observed_features=3,human_only=True,label_mode='reported',endpoint='R_vs_S',
        standard='UNSPECIFIED_REPORTED',allow_unversioned_reported=True,seed=42,bootstrap_repeats=1000,
        sensitivity_target=.95,specificity_target=.5,deferral_halfwidth=.1,split={'mode':'internal'})
    for target in ['meropenem','imipenem']:
        (out/f'{target}_config.json').write_text(json.dumps({**cfg,'target':target},indent=2))
    (out/'provenance.json').write_text(json.dumps(dict(doi='10.1038/s44259-026-00185-9',
        rows=len(rows),published_isolates=len(d),row_subsampling=False,
        encoding='Nominal S/I/R/SDD/missing; no MIC values inferred.',
        limitations=['No per-isolate AST standard/version or hospital/patient identifiers supplied.',
                    'Regions are not independent studies or verified hospital holdouts.',
                    'Gene status remains unknown until sequence/AST identity and assays are curated.',
                    'All 266 rows retained; supported gram-negative scope is selected by configuration.']),indent=2))
    return cfg


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();curate(a.data,a.out)
