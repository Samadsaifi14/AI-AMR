import io
import pandas as pd

from browser_bridge import _normalise_wide_observations
from amr_discovery.data import REQUIRED


def test_wide_public_matrix_pairs_phenotype_and_mic_columns():
    source = pd.DataFrame([
        {
            "#BioSample": "SAMN000001",
            "Isolate": "ISO-1",
            "Scientific name": "Escherichia coli",
            "Laboratory typing platform": "Phoenix",
            "Testing standard": "CLSI",
            "meropenem_Phenotype": "resistant",
            "meropenem_MIC_mgL": ">=16",
            "cefepime_Phenotype": "susceptible",
            "cefepime_MIC_mgL": "1.0",
        }
    ]).to_csv(index=False)

    normalized_csv, changed = _normalise_wide_observations(source, {})
    assert changed is True
    normalized = pd.read_csv(io.StringIO(normalized_csv), dtype=str, keep_default_na=False)
    assert REQUIRED <= set(normalized.columns)
    assert len(normalized) == 2

    meropenem = normalized.loc[normalized["drug"] == "meropenem"].iloc[0]
    assert meropenem["isolate_id"] == "SAMN000001"
    assert meropenem["species"] == "Escherichia coli"
    assert meropenem["reported_sir"] == "resistant"
    assert meropenem["measurement"] == "16"
    assert meropenem["operator"] == ">="
    assert meropenem["units"] == "mg/L"
    assert meropenem["standard"] == "CLSI"
    assert meropenem["evidence_class"] == "measured_public"


def test_categorical_wide_matrix_does_not_fabricate_mic_values():
    source = pd.DataFrame([
        {
            "#BioSample": "SAMN000002",
            "Isolate": "ISO-2",
            "Scientific name": "Klebsiella pneumoniae",
            "meropenem_Phenotype": "susceptible",
            "cefepime_Phenotype": "resistant",
        }
    ]).to_csv(index=False)

    normalized_csv, changed = _normalise_wide_observations(source, {})
    assert changed is True
    normalized = pd.read_csv(io.StringIO(normalized_csv), dtype=str, keep_default_na=False)
    assert len(normalized) == 2
    assert normalized["measurement"].eq("").all()
    assert set(normalized["reported_sir"]) == {"susceptible", "resistant"}
