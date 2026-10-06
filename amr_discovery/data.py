"""Auditable MIC parsing, explicit target labels and phenotype feature allowlists."""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
import hashlib
import json
import math
import re
from pathlib import Path
import numpy as np
import pandas as pd

CARBAPENEMS = {"meropenem", "imipenem", "ertapenem", "doripenem", "biapenem", "panipenem", "tebipenem"}
ALIASES = {"mem": "meropenem", "ipm": "imipenem", "ert": "ertapenem", "etp": "ertapenem",
           "dor": "doripenem", "fep": "cefepime", "caz": "ceftazidime", "ctx": "cefotaxime",
           "cro": "ceftriaxone", "cip": "ciprofloxacin", "amk": "amikacin", "gen": "gentamicin",
           "atm": "aztreonam", "lvx": "levofloxacin", "tob": "tobramycin"}
SIR = {"susceptible": "S", "sensitive": "S", "s": "S", "resistant": "R", "r": "R",
       "intermediate": "I", "i": "I", "susceptible, increased exposure": "I",
       "sdd": "SDD", "susceptible dose dependent": "SDD"}
AST_CATEGORIES = ("S", "I", "R", "SDD", "missing")
MIC_METHODS = {"mic", "broth dilution", "broth microdilution", "frozen broth microdilution",
               "microdilution", "microbroth dilution", "agar dilution"}
AST_METHODS = MIC_METHODS | {"reported ast", "disk diffusion", "vitek 2", "vitek2"}
HUMANS = {"homo sapiens", "human", "humans"}
REQUIRED = {"isolate_id", "source_id", "species", "drug", "measurement", "operator", "units",
            "method", "standard", "standard_version", "reported_sir", "evidence_class"}


class IntegrityError(ValueError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def drug_name(value):
    value = str(value).strip().lower().replace("_", "-")
    return ALIASES.get(value, value)


def validate_config(cfg):
    if cfg.get("representation", "mic") not in {"mic", "categorical_ast"}:
        raise IntegrityError("Representation must be mic or categorical_ast.")
    if cfg.get("representation") == "categorical_ast" and cfg.get("label_mode") != "reported":
        raise IntegrityError("Categorical AST requires measured reported labels; no MIC breakpoint conversion.")
    if cfg.get("comparability_policy", "exploratory") not in {"exploratory", "strict"}:
        raise IntegrityError("Comparability policy must be exploratory or strict.")
    if cfg.get("comparability_policy") == "strict":
        if cfg.get("standard") not in {"EUCAST", "CLSI"} or not str(cfg.get("standard_version", "")).strip():
            raise IntegrityError("Strict comparability requires EUCAST/CLSI and a pinned standard_version.")
        if cfg.get("label_mode") != "reported":
            raise IntegrityError("Strict comparability currently accepts documented reported AST only.")
    if cfg.get("target") not in {"meropenem", "imipenem"}:
        raise IntegrityError("Target must be explicitly meropenem or imipenem.")
    if cfg.get("label_mode") not in {"reported", "breakpoints"}:
        raise IntegrityError("Choose reported or reviewed breakpoints label mode.")
    if cfg.get("endpoint") not in {"R_vs_S", "R_vs_nonR"}:
        raise IntegrityError("Endpoint must be explicit.")
    if not cfg.get("standard"):
        raise IntegrityError("A single interpretation standard is required.")
    if cfg["endpoint"] == "R_vs_nonR" and cfg["standard"] != "EUCAST":
        raise IntegrityError("R_vs_nonR is supported only under EUCAST semantics; use R_vs_S otherwise.")
    drugs = [drug_name(x) for x in cfg.get("features", [])]
    if not drugs or len(set(drugs)) != len(drugs):
        raise IntegrityError("Provide a nonempty unique feature drug allowlist.")
    for name in drugs:
        if any(c in name for c in CARBAPENEMS) or name in {"ndm", "oxa48", "species", "country"}:
            raise IntegrityError(f"Forbidden primary feature: {name}")
        if "/" in name or "-" in name:
            raise IntegrityError("v0.1 accepts single-drug MIC features only; combination ratios require review.")
    if cfg.get("include_species", False):
        raise IntegrityError("Core models are phenotype-only; species is implemented as a separate baseline.")
    if not 1 <= cfg.get("min_observed_features", 1) <= len(drugs):
        raise IntegrityError("Invalid minimum feature count.")
    cfg = dict(cfg)
    cfg["features"] = drugs
    return cfg


def encode_ast(drug, value):
    """Nominal encoding; missing and SDD are never converted to susceptible."""
    text = str(value).strip().lower()
    category = SIR.get(text, "missing" if text in {"", "na", "nan", "unknown", "not tested"} else None)
    if category is None:
        raise IntegrityError(f"Unsupported categorical AST: {value!r}")
    return {f"{drug}__{c}": float(c == category) for c in AST_CATEGORIES}, category != "missing"


@dataclass(frozen=True)
class MIC:
    bound: float
    operator: str

    @property
    def log2(self):
        return math.log2(self.bound)


def parse_mic(value, operator="", units="mg/L") -> MIC:
    text = str(value).strip().replace("≤", "<=").replace("≥", ">=")
    match = re.fullmatch(r"\s*(<=|>=|==|<|>|=)?\s*([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*", text)
    if not match:
        raise IntegrityError(f"Unsupported MIC value {value!r}; combinations/ranges are not collapsed.")
    explicit = str(operator).strip().replace("≤", "<=").replace("≥", ">=")
    explicit = {"==": "="}.get(explicit, explicit)
    embedded = {"==": "="}.get(match[1], match[1])
    if explicit and embedded and explicit != embedded:
        raise IntegrityError("Conflicting embedded and separate MIC operators.")
    op = explicit or embedded or "="
    if op not in {"<", "<=", "=", ">", ">="}:
        raise IntegrityError(f"Unsupported MIC operator: {op}")
    unit = str(units).strip().lower().replace("μ", "u").replace("µ", "u")
    factors = {"mg/l": 1, "ug/ml": 1, "microgram/milliliter": 1,
               "micrograms/milliliter": 1, "microgram/millilitre": 1}
    if unit not in factors:
        raise IntegrityError(f"Unsupported MIC unit: {units}; no MIC/zone conversion.")
    bound = float(match[2]) * factors[unit]
    if not math.isfinite(bound) or not 0 < bound <= 1024:
        raise IntegrityError("MIC must be positive, finite and at most 1024 mg/L.")
    return MIC(bound, op)


def interpret_mic(mic: MIC, s_max: float, r_min: float) -> str | None:
    """S <= s_max, R >= r_min, I between; only label an entirely contained interval."""
    if not 0 < s_max < r_min:
        raise IntegrityError("Breakpoint rules require 0 < s_max < r_min.")
    x, op = mic.bound, mic.operator
    if op == "=":
        return "S" if x <= s_max else "R" if x >= r_min else "I"
    if op in {"<", "<="}:
        return "S" if x <= s_max else None
    if op in {">", ">="}:
        return "R" if x >= r_min else None
    return None


def binary_label(sir, endpoint):
    if sir == "R":
        return 1
    if sir == "S" or (sir == "I" and endpoint == "R_vs_nonR"):
        return 0
    return None


def load_rules(path, cfg, synthetic):
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    if not synthetic and (not rules.get("reviewed") or rules.get("synthetic_only")):
        raise IntegrityError("Real-data MIC labels require reviewed, non-synthetic breakpoint rules.")
    if not rules.get("citation") or not rules.get("version"):
        raise IntegrityError("Breakpoint citation and version are required.")
    if rules.get("standard") != cfg["standard"]:
        raise IntegrityError("Breakpoint standard differs from study configuration.")
    return rules


def construct_groups(cohort):
    """Connected components across global isolates, source-patients and curated duplicates."""
    parent = list(range(len(cohort)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(cohort.to_dict("records")):
        tokens = ["isolate:" + row["isolate_id"]]
        if row.get("patient_id"):
            tokens.append("patient:" + row["source_id"] + ":" + row["patient_id"])
        if row.get("duplicate_group"):
            tokens.append("duplicate:" + row["duplicate_group"])
        for token in tokens:
            if token in seen:
                parent[root(i)] = root(seen[token])
            else:
                seen[token] = i
    return ["G" + str(root(i)) for i in range(len(cohort))]


def build_cohort(path, config, breakpoint_file=None):
    cfg = validate_config(config)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    if REQUIRED - set(raw.columns):
        raise IntegrityError(f"Missing columns: {sorted(REQUIRED - set(raw.columns))}")
    if raw.empty:
        raise IntegrityError("No observations in input.")
    if raw["isolate_id"].str.strip().eq("").any():
        raise IntegrityError("Empty isolate identifier.")
    evidence = set(raw.evidence_class)
    synthetic = evidence == {"synthetic"}
    if "synthetic" in evidence and not synthetic:
        raise IntegrityError("Synthetic and real observations cannot be combined.")
    if not synthetic and not evidence <= {"measured_public", "measured_authorized"}:
        raise IntegrityError("Only documented measured phenotypes are allowed.")
    rules = load_rules(breakpoint_file, cfg, synthetic) if cfg["label_mode"] == "breakpoints" else None
    if not synthetic and cfg["label_mode"] == "reported" and cfg.get("comparability_policy") != "strict" and not cfg.get("allow_unversioned_reported", False):
        if raw.loc[raw.drug.map(drug_name).eq(cfg["target"]), "standard_version"].eq("").any():
            raise IntegrityError("Unversioned target labels: use reviewed breakpoints or explicit exploratory configuration.")
    for col in ["country", "collection_date", "patient_id", "duplicate_group", "host", "specimen",
                "ndm", "oxa48", "mechanism_evidence", "source_row", "region", "hospital_id", "lab_id", "platform", "panel_id",
                "tested_concentrations", "qc_reference"]:
        if col not in raw:
            raw[col] = ""
    for c in ["ndm", "oxa48"]:
        raw[c] = raw[c].replace("", "unknown")
        if not set(raw[c]) <= {"positive", "negative", "unknown"}:
            raise IntegrityError(f"Invalid {c} state; use positive, negative, unknown.")
    annotated = raw[["ndm", "oxa48"]].ne("unknown").any(axis=1)
    if (annotated & raw.mechanism_evidence.isin(["", "not_curated"])).any():
        raise IntegrityError("Mechanism annotations need an evidence reference.")
    raw["drug"] = raw.drug.map(drug_name)
    raw["sir"] = raw.reported_sir.str.strip().str.lower().map(SIR).fillna("unknown")
    raw["standard"] = raw.standard.str.strip().str.upper()
    raw["standard_version"] = raw.standard_version.str.strip()
    raw["method"] = raw.method.str.strip()
    from .harmonization import comparability_audit, provenance_issue
    comparability = comparability_audit(raw, cfg)
    exclusions = []
    cleaned = []
    metadata_fields = ["source_id", "species", "country", "collection_date", "patient_id",
                       "duplicate_group", "host", "ndm", "oxa48", "mechanism_evidence", "region", "hospital_id", "lab_id"]
    for isolate, block in raw.groupby("isolate_id", sort=True):
        for column in metadata_fields:
            if block[column].nunique() > 1:
                raise IntegrityError(f"Conflicting {column} for isolate {isolate}; curate before training.")
        meta = block.iloc[0]
        if cfg.get("require_known_source", False) and meta.source_id in {"", "NCBI_SOURCE_UNKNOWN"}:
            exclusions.append({"isolate_id": isolate, "reason": "source_unknown"}); continue
        if meta.species not in cfg["species"]:
            exclusions.append({"isolate_id": isolate, "reason": "unsupported_species"}); continue
        if cfg.get("human_only", True) and meta.host.strip().lower() not in HUMANS:
            exclusions.append({"isolate_id": isolate, "reason": "human_host_not_confirmed"}); continue
        if cfg.get("mechanism_cohort") == "NDM_OR_OXA48" and not (meta.ndm == "positive" or meta.oxa48 == "positive"):
            exclusions.append({"isolate_id": isolate, "reason": "mechanism_not_confirmed"}); continue
        by_drug = {}
        for drug, values in block.groupby("drug"):
            # Identical repeated observations collapse; conflicting measurements are never averaged.
            cols = ["measurement", "operator", "units", "method", "standard", "standard_version", "sir", "lab_id", "platform", "panel_id", "tested_concentrations", "qc_reference"]
            unique = values.drop_duplicates(cols)
            if len(unique) != 1:
                exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "conflicting_replicates"})
                continue
            by_drug[drug] = unique.iloc[0]
        target = by_drug.get(cfg["target"])
        if target is None:
            exclusions.append({"isolate_id": isolate, "reason": "target_missing_or_conflicting"}); continue
        categorical = cfg.get("representation", "mic") == "categorical_ast"
        if target.method.lower() not in (AST_METHODS if categorical else MIC_METHODS):
            exclusions.append({"isolate_id": isolate, "reason": "target_method_unsupported"}); continue
        if not categorical:
            try:
                parse_mic(target.measurement, target.operator, target.units)
            except IntegrityError:
                exclusions.append({"isolate_id": isolate, "reason": "target_MIC_invalid"}); continue
        if target.standard != cfg["standard"] and cfg["label_mode"] == "reported":
            exclusions.append({"isolate_id": isolate, "reason": "target_standard_mismatch"}); continue
        if cfg.get("label_mode") == "reported" and cfg.get("standard_version") and target.standard_version.strip() != str(cfg["standard_version"]).strip():
            exclusions.append({"isolate_id": isolate, "reason": "target_version_mismatch"}); continue
        issue = provenance_issue(target, cfg, categorical)
        if issue and (cfg.get("comparability_policy") == "strict" or issue == "dilution_panel_invalid"):
            exclusions.append({"isolate_id": isolate, "reason": "target_" + issue}); continue
        sir = target.sir
        if rules:
            matches = [r for r in rules["rules"] if r["species"] == meta.species and r["drug"] == cfg["target"]]
            if len(matches) != 1:
                exclusions.append({"isolate_id": isolate, "reason": "no_unique_breakpoint_rule"}); continue
            try:
                mic = parse_mic(target.measurement, target.operator, target.units)
                sir = interpret_mic(mic, matches[0]["s_max"], matches[0]["r_min"])
            except IntegrityError:
                sir = None
        y = binary_label(sir, cfg["endpoint"])
        if y is None:
            exclusions.append({"isolate_id": isolate, "reason": "target_unresolved_or_I_excluded"}); continue
        result = {c: meta[c] for c in metadata_fields}
        result.update(isolate_id=isolate, y=y, target_sir=sir,
                      label_standard=cfg["standard"], label_version=rules["version"] if rules else target.standard_version)
        observed = 0
        for drug in cfg["features"]:
            r = by_drug.get(drug)
            if categorical:
                try:
                    if r is not None and r.method.lower() not in AST_METHODS:
                        raise IntegrityError("Predictor is not a documented measured AST method.")
                    if r is not None:
                        expected_version = str(cfg.get("standard_version", target.standard_version)).strip()
                        if r.standard != cfg["standard"] or r.standard_version.strip() != expected_version:
                            exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "feature_interpretation_mismatch"})
                            r = None
                        elif cfg.get("comparability_policy") == "strict" and provenance_issue(r, cfg, True):
                            exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "feature_" + provenance_issue(r, cfg, True)})
                            r = None
                    encoded, present = encode_ast(drug, r.reported_sir if r is not None else "")
                except IntegrityError:
                    exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "feature_AST_invalid"})
                    encoded, present = encode_ast(drug, "")
                result.update(encoded)
                observed += int(present)
                continue
            mic = None
            if r is not None and r.method.lower() in MIC_METHODS:
                try:
                    issue = provenance_issue(r, cfg, False)
                    if issue and (cfg.get("comparability_policy") == "strict" or issue == "dilution_panel_invalid"):
                        raise IntegrityError(issue)
                    mic = parse_mic(r.measurement, r.operator, r.units)
                except IntegrityError:
                    exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "feature_MIC_invalid"})
            result[f"{drug}__log2_bound"] = mic.log2 if mic else np.nan
            result[f"{drug}__left_censored"] = float(mic.operator in {"<", "<="}) if mic else 0.
            result[f"{drug}__right_censored"] = float(mic.operator in {">", ">="}) if mic else 0.
            result[f"{drug}__strict_bound"] = float(mic.operator in {"<", ">"}) if mic else 0.
            result[f"{drug}__missing"] = float(mic is None)
            observed += mic is not None
        result["observed_features"] = observed
        if observed < cfg["min_observed_features"]:
            exclusions.append({"isolate_id": isolate, "reason": "insufficient_feature_panel"}); continue
        result["mechanism"] = ("co_producer" if meta.ndm == meta.oxa48 == "positive" else
                               "NDM_positive_other_unknown" if meta.ndm == "positive" and meta.oxa48 == "unknown" else
                               "OXA48_positive_other_unknown" if meta.oxa48 == "positive" and meta.ndm == "unknown" else
                               "NDM_only_assayed" if meta.ndm == "positive" else
                               "OXA48_only_assayed" if meta.oxa48 == "positive" else
                               "both_assayed_negative" if meta.ndm == meta.oxa48 == "negative" else "unknown")
        cleaned.append(result)
    cohort = pd.DataFrame(cleaned)
    if len(cohort):
        cohort["group_id"] = construct_groups(cohort)
    suffixes = AST_CATEGORIES if cfg.get("representation") == "categorical_ast" else ["log2_bound", "left_censored", "right_censored", "strict_bound", "missing"]
    feature_cols = [f"{d}__{suffix}" for d in cfg["features"] for suffix in suffixes]
    if cohort.empty:
        cohort = pd.DataFrame(columns=metadata_fields + ['isolate_id', 'y', 'target_sir',
            'label_standard', 'label_version', 'observed_features', 'mechanism', 'group_id'] + feature_cols)
    audit = {"input_sha256": sha256(path), "raw_rows": len(raw), "raw_isolates": raw.isolate_id.nunique(),
             "eligible_isolates": len(cohort), "synthetic": synthetic,
             "evidence_status": "SOFTWARE_DEMONSTRATION" if synthetic else "EXPLORATORY_MEASURED_DATA",
             "label_mode": cfg["label_mode"], "endpoint": cfg["endpoint"],
             "representation": cfg.get("representation", "mic"),
             "comparability": comparability,
             "excluded_event_counts": dict(Counter(x["reason"] for x in exclusions)),
             "input_target_SIR_counts": raw.loc[raw.drug.eq(cfg["target"]), "sir"].value_counts().to_dict(),
             "class_counts": cohort.y.value_counts().to_dict() if len(cohort) else {},
             "patient_ids_available": int(cohort.patient_id.ne("").sum()) if len(cohort) else 0,
             "mechanism_counts": cohort.mechanism.value_counts().to_dict() if len(cohort) else {},
             "feature_columns": feature_cols,
             "limitations": ["Not a representative sample unless acquisition design establishes it.",
                             "No clinical or causal validation.", "Missing patient IDs limit independence claims."]}
    if not synthetic and cfg["label_mode"] == "reported" and cfg.get("allow_unversioned_reported"):
        audit["limitations"].append("Reported labels may be unversioned; not breakpoint-harmonized.")
    if cfg.get("representation") == "categorical_ast":
        audit["limitations"].append("Categorical model: S, I, R, SDD and missing encoded separately; no numeric MICs inferred.")
    return cohort, audit, pd.DataFrame(exclusions), feature_cols
