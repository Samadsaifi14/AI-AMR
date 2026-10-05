import json
import pandas as pd
import pytest
from amr_discovery.importer import import_wide
from amr_discovery.data import IntegrityError


def test_chunked_import_keeps_bounds_rows_and_column_alignment(tmp_path):
    raw=tmp_path/'raw.csv';raw.write_text('ID,MEM,FEP,SIR\na,>8,2,R\nb,1,,S\nc,4,<=1,I\n')
    mapping=tmp_path/'map.json';mapping.write_text(json.dumps({
        'metadata':{'isolate_id':'ID'},'constants':{'source_id':'study','species':'Klebsiella pneumoniae'},
        'drugs':{'meropenem':{'measurement':'MEM','reported_sir':'SIR'},'cefepime':{'measurement':'FEP'}}}))
    out=tmp_path/'out.csv';manifest=import_wide(raw,mapping,out,chunksize=1)
    data=pd.read_csv(out,keep_default_na=False)
    assert manifest['input_rows']==3 and manifest['output_rows']==6
    assert data.loc[data.drug.eq('meropenem'),'measurement'].tolist()==['>8','1','4']
    assert data.loc[data.drug.eq('cefepime'),'reported_sir'].tolist()==['','','']
    assert data.loc[data.drug.eq('cefepime'),'measurement'].tolist()==['2','','<=1']
    with pytest.raises(IntegrityError,match='exists'):
        import_wide(raw,mapping,out)
