import pytest

from amr_discovery.data import IntegrityError
from amr_discovery.workbook import normalize_rows


HEADERS = [
    "#BioSample", "Scientific name", "Antibiotic", "Resistance phenotype",
    "Measurement sign", "MIC (mg/L)", "Laboratory typing platform", "Testing standard",
    "Location", "Isolation source", "Vendor", "Create date",
]


def test_workbook_normalization_preserves_ast_and_unknown_provenance():
    rows, issues, counts = normalize_rows(HEADERS, [[
        "SAMN0001", "Escherichia coli", "amoxicillin-clavulanic acid", "resistant",
        ">=", 32, "Vitek", "CLSI", "USA:Boston", "urine", "vendor", "2026-01-01T00:00:00Z",
    ]], "AST")
    assert not issues
    row = rows[0]
    assert row["isolate_id"] == row["accession"] == "SAMN0001"
    assert row["drug"] == "amoxicillin-clavulanate"
    assert row["measurement"] == "32" and row["operator"] == ">="
    assert row["reported_sir"] == "resistant"
    assert row["country"] == "USA"
    assert row["source_id"] == "ncbi_source_unknown"
    assert row["collection_date"] == row["standard_version"] == row["lab_id"] == ""
    assert row["record_create_date"] == "2026-01-01T00:00:00Z"
    assert counts["drug_rows"] == {"amoxicillin-clavulanate": 1}


def test_workbook_normalization_accounts_for_bad_rows_instead_of_guessing():
    rows, issues, _ = normalize_rows(HEADERS, [[
        "SAMN0002", "Escherichia coli", "cefepime", "unexpected label", "=", 1,
        "Vitek", "CLSI", "USA:Boston", "blood", "vendor", "",
    ]], "AST")
    assert not rows
    assert issues == [{"source_row": 2, "reason": "unsupported_reported_phenotype", "value": "unexpected label"}]


def test_workbook_requires_reviewed_header_mapping():
    with pytest.raises(IntegrityError, match="missing required columns"):
        normalize_rows(["BioSample", "Drug"], [], "AST")
