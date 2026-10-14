import io
import json
import pandas as pd
import pytest
from amr_discovery.batches import merge_observations,prepare_batch
from amr_discovery.data import IntegrityError
from pathlib import Path


def fixture():
    return Path('data/fixtures/browser_demo.csv').read_text()


def test_repeated_batch_does_not_inflate_data_and_keeps_hashes():
    csv=fixture()
    merged,m=merge_observations(csv,csv)
    assert m['rows']==len(pd.read_csv(io.StringIO(csv)))
    assert m['exact_duplicate_rows_removed']==m['rows']
    assert len(m['output_sha256'])==64
    assert m['status']=='PREPARED_NOT_AUDITED'
    assert len(m['inputs'])==2
    assert 'fresh independent' in m['next_step']


def test_conflicting_result_never_overwrites_original():
    original=pd.read_csv(io.StringIO(fixture()),dtype=str).fillna('')
    changed=original.iloc[:1].copy();changed.loc[changed.index[0],'measurement']='999'
    with pytest.raises(IntegrityError,match='conflicting rows'):
        merge_observations(changed.to_csv(index=False),original.to_csv(index=False))


def test_antibiotic_alias_does_not_bypass_identity_check():
    original=pd.read_csv(io.StringIO(fixture()),dtype=str).fillna('')
    original=original[original.drug.eq('meropenem')].iloc[:1]
    changed=original.copy();changed['drug']='MEM';changed['reported_sir']='R' if original.iloc[0].reported_sir!='R' else 'S'
    with pytest.raises(IntegrityError,match='conflicting rows'):
        merge_observations(changed.to_csv(index=False),original.to_csv(index=False))


def test_conflicting_lab_identity_is_rejected_even_for_distinct_drugs():
    original=pd.read_csv(io.StringIO(fixture()),dtype=str).fillna('')
    group=original[original.isolate_id.eq(original.iloc[0].isolate_id)].iloc[:2].copy()
    group['lab_id']=['labA','labB']
    with pytest.raises(IntegrityError,match='conflicting lab IDs'):
        merge_observations(group.to_csv(index=False))


@pytest.mark.parametrize('csv',['','isolate_id,drug\na,cefepime\n',fixture().splitlines()[0]+'\n'])
def test_incomplete_input_is_rejected(csv):
    with pytest.raises(IntegrityError):merge_observations(csv)


def test_immutable_output_directory_and_no_write_on_conflict(tmp_path):
    batch=tmp_path/'batch.csv';batch.write_text(fixture());out=tmp_path/'prepared'
    m=prepare_batch(batch,out)
    assert json.loads((out/'batch_manifest.json').read_text())==m
    with pytest.raises(FileExistsError):prepare_batch(batch,out)
    frame=pd.read_csv(batch,dtype=str).fillna('');frame=pd.concat([frame,frame.iloc[:1].assign(measurement='999')])
    batch.write_text(frame.to_csv(index=False))
    rejected=tmp_path/'rejected'
    with pytest.raises(IntegrityError):prepare_batch(batch,rejected)
    assert not rejected.exists()
