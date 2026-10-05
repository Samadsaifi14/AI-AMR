"""Extract public AST/genomic supplements without inventing missing standards.

Usage: python scripts/curate_india_icu.py --raw data/raw/india_surgical_icu_2026 --out data/curated/india_surgical_icu_2026
Requires the optional openpyxl reader. Output observations are QUARANTINED.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import pandas as pd

ARTICLE='https://www.nature.com/articles/s41467-026-74764-9'
DRUGS={'Ceftazidime':'ceftazidime','Cefipime':'cefepime','Ciprofloxacin':'ciprofloxacin',
       'Gentamicin':'gentamicin','Amikacin':'amikacin','Meropenem':'meropenem','Imipenem':'imipenem'}

def curate(raw,out):
    raw,out=Path(raw),Path(out);out.mkdir(parents=True,exist_ok=False)
    astfile=raw/'41467_2026_74764_MOESM4_ESM.xlsx'
    genfile=raw/'41467_2026_74764_MOESM5_ESM.xlsx'
    ast=pd.read_excel(astfile,sheet_name='Patient isolates AST',header=1,dtype=str).fillna('')
    wgs=pd.read_excel(genfile,sheet_name='WGS Results',header=1,dtype=str).fillna('')
    wgs=wgs[wgs.Sink_or_patient.eq('Patient')]
    if wgs.Sample.duplicated().any():raise ValueError('Duplicate WGS sample ID')
    hits=pd.read_excel(genfile,sheet_name='AMRFinder',dtype=str).fillna('')
    taxa=wgs.set_index('Sample')['WGS identification'].to_dict()
    accessions=wgs.set_index('Sample')['Biosample accession'].to_dict()
    rows,genes=[],[]
    # Only exact sample identifiers are joined. No silent punctuation normalization.
    for i,r in ast.iterrows():
        sample=r['WGS ID'];isolate=f'INDIA_ICU2026:{sample}'
        if not sample:continue
        matched=hits[hits['Name.x'].eq(sample)]
        ndm='positive' if matched['Gene symbol'].str.startswith('blaNDM-').any() else 'unknown'
        for drug,name in DRUGS.items():
            if not r[drug].strip():continue
            rows.append(dict(isolate_id=isolate,source_id='INDIA_ICU2026_SINGLE_HOSPITAL',patient_id=r['CRESCENT ID'],
                duplicate_group='',species=taxa.get(sample,''),country='India',collection_date='',host='Homo sapiens',
                specimen='patient rectal swab',drug=name,measurement=r[drug],operator='',units='',method='MIC',
                platform='VITEK2 AST N406',standard='UNKNOWN_REVIEW_REQUIRED',standard_version='',
                reported_sir=r[drug+'_Interpretation'],ndm=ndm,oxa48='unknown',
                mechanism_evidence=ARTICLE+'#MOESM5; AMRFinder exact sample join' if ndm=='positive' else 'not_curated',
                evidence_class='measured_public',accession=accessions.get(sample,''),
                source_row=f'{astfile.name}:Patient isolates AST:Excel row {i+3}',
                curation_status='QUARANTINED_STANDARD_VERSION_AND_UNITS_REVIEW_REQUIRED'))
        for gene in sorted(set(matched['Gene symbol'])-{''}):
            genes.append(dict(isolate_id=isolate,gene=gene,status='positive',
                evidence_reference=ARTICLE+'#MOESM5; '+genfile.name+'; AMRFinder'))
    pd.DataFrame(rows).to_csv(out/'candidate_observations_QUARANTINED.csv',index=False)
    pd.DataFrame(genes,columns=['isolate_id','gene','status','evidence_reference']).to_csv(out/'positive_gene_calls.csv',index=False)
    # Retain all raw gene calls separately. A proposed identifier correspondence
    # is exported for human review, never silently admitted as a verified join.
    raw_genes=hits[['Name.x','Gene symbol']].drop_duplicates().rename(columns={'Name.x':'raw_sample_id','Gene symbol':'gene'})
    raw_genes['status']='positive'
    raw_genes['evidence_reference']=ARTICLE+'#MOESM5; AMRFinder'
    raw_genes.to_csv(out/'unlinked_positive_gene_calls.csv',index=False)
    def key(s):
        m=re.fullmatch(r'K[-_]?(\d+)',s)
        return int(m[1]) if m else None
    proposals=[]
    raw_names=sorted(set(hits['Name.x']))
    for sample in sorted(set(ast['WGS ID'])-{''}):
        candidates=[name for name in raw_names if key(sample) is not None and key(name)==key(sample)]
        if len(candidates)==1:
            proposals.append({'ast_sample_id':sample,'amrfinder_sample_id':candidates[0],
                              'status':'PROPOSED_NOT_VERIFIED','basis':'Unique numeric K identifier; punctuation differs; review against source needed.'})
    pd.DataFrame(proposals).to_csv(out/'candidate_identity_mapping_REVIEW_REQUIRED.csv',index=False)
    summary=dict(article=ARTICLE,ast_patient_rows=len(ast),exact_wgs_taxonomy_matches=int(ast['WGS ID'].isin(taxa).sum()),
        raw_meropenem_sir_counts=ast.Meropenem_Interpretation.value_counts().to_dict(),
        observation_rows=len(rows),positive_gene_calls=len(genes),unique_gene_annotated_isolates=len({g['isolate_id'] for g in genes}),
        raw_positive_gene_calls=len(raw_genes),proposed_unverified_identity_matches=len(proposals),
        status='QUARANTINED',training_admissible=False,
        reasons=['Resistance-selected single-hospital cohort; not representative of India.',
                 'Interpretation standard/version and MIC units not documented in examined tables/methods; independent review needed.',
                 'No negative gene calls inferred from missing AMRFinder hits.',
                 'No complete calendar collection dates or patient locations inferred.',
                 'Exact sample matches only; no speculative identity normalization.'],
        input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [astfile,genfile]})
    (out/'curation_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--out',required=True)
    args=p.parse_args();curate(args.raw,args.out)
