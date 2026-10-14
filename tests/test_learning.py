import json
from pathlib import Path
import pandas as pd
import pytest
from amr_discovery.data import IntegrityError,build_cohort
from amr_discovery.learning import (profile,drift_report,release_evidence,identities,
                                   train_version,reserve_evaluation,promote_research,verify_version,
                                   write_registry,_registry,evaluate_version,digest)
from amr_discovery.data import sha256
from amr_discovery.export_import import import_ncbi_export


def demo():
    cfg=json.loads(Path('configs/demo.json').read_text())
    cohort,audit,_,_=build_cohort('data/fixtures/browser_demo.csv',cfg)
    return cfg,cohort,audit


def test_drift_uses_fixed_training_bins_and_does_not_change_reference():
    cfg,cohort,_=demo();reference=profile(cohort,cfg);before=json.dumps(reference,sort_keys=True)
    report=drift_report(reference,cohort,cfg)
    assert report['status']=='NO_HEURISTIC_ALERT'
    changed=cohort.copy();changed[f"{cfg['features'][0]}__log2_bound"]=100
    alert=drift_report(reference,changed,cfg)
    assert alert['status']=='REVIEW_REQUIRED'
    assert json.dumps(reference,sort_keys=True)==before
    assert not alert['clinical_validation']
    with pytest.raises(IntegrityError,match='configuration'):
        drift_report(reference,cohort,{**cfg,'target':'imipenem'})


def test_categorical_drift_tracks_missingness_and_unknown_species():
    cfg,cohort,_=demo();cfg={**cfg,'representation':'categorical_ast','features':['cefepime']}
    frame=cohort[['species']].copy()
    for category in ['S','I','R','SDD','missing']:frame['cefepime__'+category]=int(category=='S')
    ref=profile(frame,cfg);incoming=frame.copy();incoming['cefepime__S']=0;incoming['cefepime__missing']=1
    incoming['species']='Unsupported species'
    r=drift_report(ref,incoming,cfg)
    assert r['status']=='REVIEW_REQUIRED' and r['unseen_species']==['Unsupported species']
    assert r['features'][0]['missingness_change']>.9


def test_perfect_small_holdout_is_not_clinically_validated():
    r={'brier':.01,'sensitivity_exact_95':{'low':.63},'specificity_exact_95':{'low':.86},
       'identity_and_label_metadata_complete':False}
    evidence=release_evidence(r,{'synthetic':False})
    assert evidence['status']=='RESEARCH_ONLY_GATES_NOT_MET'
    assert not evidence['clinical_validation'] and not evidence['automatic_promotion']
    r['sensitivity_exact_95']['low']=.96;r['identity_and_label_metadata_complete']=True
    eligible=release_evidence(r,{'synthetic':False},independent=True)
    assert eligible['status']=='ELIGIBLE_FOR_RESEARCH_REVIEW'
    assert not eligible['clinical_validation']


def test_reserved_identity_cannot_be_trained_even_if_source_is_changed(tmp_path):
    cfg,cohort,_=demo();registry=tmp_path/'registry.json'
    registry.write_text(json.dumps({'schema':1,'versions':[],'reserved':[{'identities':identities(cohort),
                                'sources':['other_source'],'input_sha256':'another-file'}]}))
    config=tmp_path/'config.json';config.write_text(json.dumps(cfg))
    with pytest.raises(IntegrityError,match='reserved evaluation'):
        train_version('data/fixtures/browser_demo.csv',config,tmp_path/'run',registry)
    assert not (tmp_path/'run').exists()


def test_synthetic_reservation_and_unverified_promotion_are_blocked(tmp_path):
    cfg,_,_=demo();config=tmp_path/'config.json';config.write_text(json.dumps(cfg))
    with pytest.raises(IntegrityError,match='measured'):
        reserve_evaluation('data/fixtures/browser_demo.csv',config,tmp_path/'registry.json')
    with pytest.raises(IntegrityError,match='Unknown version'):
        promote_research(tmp_path/'registry.json','made-up')


def test_model_tampering_is_detected_before_deserialization(tmp_path):
    file=tmp_path/'research_model.joblib';file.write_text('untrusted')
    with pytest.raises(IntegrityError,match='incomplete|changed'):
        verify_version({'run':str(tmp_path),'hashes':{'research_model.joblib':'wrong-hash'}})


def test_import_never_invents_source_host_method_or_collection_date():
    exported=pd.DataFrame([{'#BioSample':'SAMN1','Scientific name':'Klebsiella pneumoniae',
        'Antibiotic':'meropenem','Resistance phenotype':'resistant','Measurement sign':'>=',
        'MIC (mg/L)':'8','Testing standard':'CLSI','Create date':'2025-01-01',
        'Laboratory typing platform':'Vitek','Location':'India: Pune'}]).to_csv(index=False)
    content,m=import_ncbi_export(exported)
    row=pd.read_csv(__import__('io').StringIO(content),keep_default_na=False).iloc[0]
    assert row.method=='unknown' and row.source_id=='unknown' and row.host==''
    assert row.collection_date=='' and row.submission_date=='2025-01-01'
    assert m['quarantined_rows']==1


def test_matching_accession_without_matching_observation_is_quarantined():
    reference=pd.read_csv('data/fixtures/browser_demo.csv',dtype=str,keep_default_na=False).iloc[:1].copy()
    row=reference.iloc[0]
    exported=pd.DataFrame([{'#BioSample':row.isolate_id,'Scientific name':row.species,'Antibiotic':row.drug,
         'Resistance phenotype':row.reported_sir,'Measurement sign':row.operator,
         'MIC (mg/L)':'999','Testing standard':row.standard}]).to_csv(index=False)
    _,m=import_ncbi_export(exported,reference.to_csv(index=False))
    assert m['matched_rows']==0 and m['quarantined_rows']==1


def test_portable_registry_and_rejected_promotion_preserve_active_version(tmp_path):
    run=tmp_path/'version1';run.mkdir()
    names=['research_model.joblib','model_lock.json','cohort_with_splits.csv','metrics.json','reference_profile.json']
    for name in names:(run/name).write_text('fixture')
    version={'version_id':'candidate','run':str(run),'hashes':{n:sha256(run/n) for n in names}}
    registry=tmp_path/'registry.json'
    write_registry(registry,{'schema':1,'versions':[version],'reserved':[],'evaluations':[],
                             'active_research_version':'original'})
    assert json.loads(registry.read_text())['versions'][0]['run']=='version1'
    assert verify_version(_registry(registry)['versions'][0])==run
    with pytest.raises(IntegrityError,match='promotion blocked'):
        promote_research(registry,'candidate')
    assert _registry(registry)['active_research_version']=='original'


def test_reused_source_rejected_before_model_deserialization(tmp_path,monkeypatch):
    cfg,cohort,_=demo();run=tmp_path/'run';run.mkdir()
    raw=pd.read_csv('data/fixtures/browser_demo.csv',dtype=str,keep_default_na=False)
    # Contract fixture only: no training or scientific result is produced.
    raw['evidence_class']='measured_authorized';raw['isolate_id']='new-'+raw.isolate_id
    data=tmp_path/'incoming.csv';raw.to_csv(data,index=False)
    (run/'configuration.json').write_text(json.dumps(cfg))
    cohort.assign(partition='train').to_csv(run/'cohort_with_splits.csv',index=False)
    for name in ['research_model.joblib','model_lock.json','metrics.json','reference_profile.json']:(run/name).write_text('fixture')
    names=['research_model.joblib','model_lock.json','cohort_with_splits.csv','metrics.json','reference_profile.json']
    version={'version_id':'v1','run':str(run),'hashes':{n:sha256(run/n) for n in names},'identities':[]}
    registry=tmp_path/'registry.json'
    write_registry(registry,{'schema':1,'versions':[version],'reserved':[{'input_sha256':sha256(data),
                    'configuration_sha256':digest(cfg)}],'evaluations':[]})
    monkeypatch.setattr('joblib.load',lambda path:pytest.fail('Must not deserialize a model for an overlapping source'))
    with pytest.raises(IntegrityError,match='sources overlap'):
        evaluate_version(registry,'v1',data,tmp_path/'evaluation')
    assert not (tmp_path/'evaluation').exists()
