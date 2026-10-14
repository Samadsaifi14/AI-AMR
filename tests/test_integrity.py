import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from amr_discovery.data import (parse_mic, interpret_mic, MIC, binary_label, validate_config,
                                build_cohort, construct_groups, IntegrityError, load_rules)
from amr_discovery.demo import generate_demo
from amr_discovery.modeling import partitions, metrics, threshold_for_sensitivity
from amr_discovery.ncbi import parse_biosamples

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def config():
    return json.loads((ROOT / "configs/demo.json").read_text())

@pytest.mark.parametrize("value,operator,units,bound,op",[("<=0.5","","mg/L",.5,"<="),
    ("2",">","ug/mL",2,">"),("≥8","","µg/ml",8,">="),("1e-1","==","mg/L",.1,"=")])
def test_preserve_mic_bounds(value,operator,units,bound,op):
    m=parse_mic(value,operator,units)
    assert m.bound==bound and m.operator==op

@pytest.mark.parametrize("value,op,unit",[("0","","mg/L"),("-1","","mg/L"),("8/4","","mg/L"),
    ("nan","","mg/L"),("10","","mm"),("<2",">","mg/L"),("2048","","mg/L")])
def test_reject_invalid_mic(value,op,unit):
    with pytest.raises(IntegrityError): parse_mic(value,op,unit)

def test_censor_intervals_not_invented_points():
    assert interpret_mic(MIC(8,">"),1,4)=="R"
    assert interpret_mic(MIC(1,"<="),1,4)=="S"
    assert interpret_mic(MIC(2,">"),1,4) is None
    assert interpret_mic(MIC(4,"<"),1,4) is None
    assert interpret_mic(MIC(2,"="),1,4)=="I"
    assert binary_label("I","R_vs_S") is None
    assert binary_label("I","R_vs_nonR")==0

@pytest.mark.parametrize("forbidden",["MEM","meropenem-vaborbactam","imipenem","ndm","country"])
def test_forbidden_features(config,forbidden):
    config["features"]=[forbidden]
    with pytest.raises(IntegrityError): validate_config(config)

def test_no_clsi_intermediate_as_eucast(config):
    config["standard"]="CLSI"
    with pytest.raises(IntegrityError): validate_config(config)

def test_unreviewed_breakpoints_rejected_for_real(config):
    with pytest.raises(IntegrityError):
        load_rules(ROOT / "configs/reviewed_breakpoints_template.json",config,False)

def test_connected_groups_include_transitive_duplicate_links():
    df=pd.DataFrame([
        dict(isolate_id="A",source_id="S",patient_id="p",duplicate_group=""),
        dict(isolate_id="B",source_id="S",patient_id="p",duplicate_group="d"),
        dict(isolate_id="C",source_id="T",patient_id="q",duplicate_group="d"),
        dict(isolate_id="D",source_id="T",patient_id="p",duplicate_group="")])
    g=construct_groups(df)
    assert g[0]==g[1]==g[2] and g[3]!=g[0]

def test_demo_real_mixture_rejected(tmp_path,config):
    file=generate_demo(tmp_path / "demo",100)
    raw=pd.read_csv(file,keep_default_na=False)
    raw.loc[0,"evidence_class"]="measured_public"
    raw.to_csv(file,index=False)
    with pytest.raises(IntegrityError,match="cannot be combined"):build_cohort(file,config)

def test_missing_features_remain_missing_and_target_excluded(tmp_path,config):
    file=generate_demo(tmp_path / "demo",100)
    raw=pd.read_csv(file,keep_default_na=False)
    iso=raw.iloc[0].isolate_id
    raw=raw.loc[~((raw.isolate_id==iso)&(raw.drug=="amikacin"))]
    raw.to_csv(file,index=False)
    df,audit,_,features=build_cohort(file,config)
    row=df.loc[df.isolate_id==iso].iloc[0]
    assert np.isnan(row["amikacin__log2_bound"]) and row["amikacin__missing"]==1
    assert not any("meropenem" in c or "ndm" in c for c in features)
    assert audit["synthetic"]

def test_replicates_never_averaged(tmp_path,config):
    file=generate_demo(tmp_path / "demo",100)
    raw=pd.read_csv(file,keep_default_na=False)
    record=raw.iloc[[0]].copy();record["measurement"]="16"
    pd.concat([raw,record]).to_csv(file,index=False)
    df,audit,_,_=build_cohort(file,config)
    assert raw.iloc[0].isolate_id not in set(df.isolate_id)
    assert audit["excluded_event_counts"]["conflicting_replicates"]==1

def test_unknown_mechanisms_not_negative(tmp_path,config):
    df,_,_,_=build_cohort(generate_demo(tmp_path / "demo",100),config)
    assert "unknown" in set(df.mechanism)
    assert "both_assayed_negative" not in set(df.mechanism)

def test_group_split_independence(tmp_path,config):
    df,_,_,_=build_cohort(generate_demo(tmp_path / "demo",800),config)
    split=partitions(df,config)
    assert split.groupby("group_id").partition.nunique().max()==1
    assert set(split.loc[split.partition=="test","source_id"])=={"DEMO_B"}
    assert not (split.loc[split.partition=="train","source_id"]=="DEMO_B").any()

def test_insufficient_class_counts_block_training(config):
    df=pd.DataFrame({"y":[1]*50,"group_id":[str(i) for i in range(50)]})
    config["split"]={"mode":"internal"}
    with pytest.raises(IntegrityError):partitions(df,config)

def test_metrics_denominators():
    m=metrics([1,1,1,0,0],[.9,.8,.2,.1,.7],.5)
    assert m["fn"]==1 and m["fp"]==1
    assert m["false_negative_fraction_R"]==pytest.approx(1/3)
    assert m["specificity"]==.5
    assert metrics([1,1],[.9,.8])["specificity"] is None

def test_threshold_uses_requested_sensitivity():
    y=np.array([1,1,1,1,0,0]);p=np.array([.1,.2,.5,.9,.15,.6])
    t=threshold_for_sensitivity(y,p,.75)
    assert ((p>=t)&(y==1)).sum()/4 >=.75
    assert t==.2

def test_ncbi_xml_uses_project_label_and_preserves_operator():
    xml=b'''<BioSampleSet><BioSample accession="SAMN1"><Description><Organism taxonomy_name="Klebsiella pneumoniae"/>
    <Table class="Antibiogram.1.0"><Header><Cell>Antibiotic</Cell><Cell>Measurement</Cell><Cell>Measurement sign</Cell>
    </Header><Body><Row><Cell>meropenem</Cell><Cell>8</Cell><Cell>&gt;</Cell></Row></Body></Table></Description>
    <Links><Link target="bioproject" label="PRJNA1">1</Link></Links></BioSample></BioSampleSet>'''
    r=parse_biosamples(xml)[0]
    assert r["source_id"]=="PRJNA1" and r["operator"]==">" and r["ndm"]=="unknown"
