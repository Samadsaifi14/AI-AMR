"""Observation-level comparability checks; never estimate a lab correction factor."""
import json
import math
from .data import IntegrityError, parse_mic


UNKNOWN = {"", "unknown", "unspecified", "unspecified_reported", "not reported", "na", "nan",
           "none", "null", "n/a", "not_curated", "ncbi_source_unknown"}


def known(value):
    text = str(value).strip().lower()
    return text not in UNKNOWN and not text.startswith(("replace_", "placeholder", "<"))


def provenance_issue(row, cfg, categorical):
    # EUCAST explicitly rejects colistin disk/gradient susceptibility tests.
    # Do not let a categorical label conceal a known incompatible measurement method.
    if row.get('drug', '') == 'colistin' and row.method.strip().lower() in {
        'disk diffusion', 'disc diffusion', 'gradient diffusion', 'etest', 'e-test'}:
        return 'drug_method_incompatible'
    if not categorical and row.tested_concentrations.strip():
        issue = dilution_issue(row)
        if issue:
            return issue
    if not known(row.lab_id):
        return "lab_unknown"
    if not known(row.qc_reference):
        return "QC_undocumented"
    if row.method.strip().lower() in {"mic", "reported ast", ""}:
        return "method_unspecified"
    if not categorical and (not known(row.panel_id) or not row.tested_concentrations.strip()):
        return "dilution_panel_unknown"
    return None


def dilution_issue(row):
    try:
        # Actual tested concentration ladder, in the row's documented MIC units.
        # Unequal spacing is allowed. There is no assumed twofold ladder.
        values = json.loads(row.tested_concentrations)
        if not isinstance(values, list) or len(values) < 2 or any(isinstance(v, bool) for v in values):
            raise ValueError()
        ladder = [parse_mic(str(v), "=", row.units).bound for v in values]
        if any(a >= b for a, b in zip(ladder, ladder[1:])):
            raise ValueError()
        mic = parse_mic(row.measurement, row.operator, row.units)
        if not any(math.isclose(mic.bound, v, rel_tol=1e-9) for v in ladder):
            raise ValueError()
    except (ValueError, TypeError, IntegrityError):
        return "dilution_panel_invalid"
    return None


def comparability_audit(raw, cfg):
    panel = raw.loc[raw.drug.isin([cfg['target']] + cfg['features'])].copy()
    fields = ['lab_id', 'standard', 'standard_version', 'qc_reference']
    missing = {field: int((~panel[field].map(known)).sum()) for field in fields}
    groups = []
    for keys, rows in panel.groupby(['lab_id', 'method', 'standard', 'standard_version', 'drug'], dropna=False):
        groups.append(dict(zip(['lab_id', 'method', 'standard', 'standard_version', 'drug'], keys),
                           observations=len(rows), panels=sorted(set(rows.panel_id) - {''}),
                           units=sorted(set(rows.units) - {''}),
                           bounds_with_operators=int((rows.operator.str.contains('[<>]', regex=True) |
                                                      rows.measurement.str.contains('[<>≤≥]', regex=True)).sum())))
    categorical = cfg.get('representation', 'mic') == 'categorical_ast'
    issues = panel.apply(lambda row: provenance_issue(row, cfg, categorical), axis=1)
    return {'policy': cfg.get('comparability_policy', 'exploratory'),
            'status': 'STRICT_PROVENANCE_FILTER' if cfg.get('comparability_policy') == 'strict' else 'EXPLORATORY_NOT_HARMONIZED',
            'missing_provenance_rows': missing,
            'provenance_issue_counts': issues.dropna().value_counts().to_dict(),
            'lab_method_drug_groups': groups,
            'interpretation': 'Provenance checks are not analytical agreement or clinical validation. No lab-specific scaling applied.'}
