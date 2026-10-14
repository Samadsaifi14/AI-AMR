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

ANTIBIOTICS = {"meropenem", "imipenem", "ertapenem", "doripenem", "cefepime", "ceftazidime",
               "cefotaxime", "ceftriaxone", "cefoxitin", "cefazolin", "aztreonam", "amikacin",
               "gentamicin", "tobramycin", "ciprofloxacin", "levofloxacin", "colistin",
               "polymyxin-b", "tigecycline", "trimethoprim-sulfamethoxazole", "ampicillin",
               "piperacillin", "fosfomycin", "nitrofurantoin", "chloramphenicol", "tetracycline"}
COMBINATIONS = {"ceftazidime-avibactam", "meropenem-vaborbactam", "imipenem-relebactam",
                "piperacillin-tazobactam", "ampicillin-sulbactam", "amoxicillin-clavulanate"}
MECHANISMS = ("ndm", "oxa48", "kpc", "vim", "imp")

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
    cfg = dict(cfg)
    from .harmonization import known
    if cfg.get('selection_objective', 'log_loss') not in {'log_loss', 'specificity_at_sensitivity'}:
        raise IntegrityError('Unknown development selection objective.')
    if cfg.get("representation", "mic") not in {"mic", "categorical_ast"}:
        raise IntegrityError("Representation must be mic or categorical_ast.")
    if cfg.get("representation") == "categorical_ast" and cfg.get("label_mode") != "reported":
        raise IntegrityError("Categorical AST requires measured reported labels; no MIC breakpoint conversion.")
    if cfg.get("comparability_policy", "exploratory") not in {"exploratory", "strict"}:
        raise IntegrityError("Comparability policy must be exploratory or strict.")
    if cfg.get("comparability_policy") == "strict":
        if cfg.get("standard") not in {"EUCAST", "CLSI"} or not known(cfg.get("standard_version", "")):
            raise IntegrityError("Strict comparability requires EUCAST/CLSI and a pinned standard_version.")
        if cfg.get("label_mode") != "reported":
            raise IntegrityError("Strict comparability currently accepts documented reported AST only.")
    if cfg.get('threshold_policy', 'calibration') not in {'calibration', 'source_robust'}:
        raise IntegrityError('Unknown threshold policy.')
    if cfg.get('decision_policy', 'validated_band') not in {'validated_band', 'research_binary'}:
        raise IntegrityError('Unknown research decision policy.')
    framework = cfg.get("task") == "antibiotic_resistance"
    if cfg.get("task") not in {None, "antibiotic_resistance"}:
        raise IntegrityError("This framework predicts antibiotic resistance; mechanisms are annotations only.")
    cfg["target"] = drug_name(cfg.get("target", ""))
    if cfg["target"] not in (ANTIBIOTICS | COMBINATIONS if framework else {"meropenem", "imipenem"}):
        raise IntegrityError("Choose an explicitly supported antibiotic target.")
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
    selection = cfg.get("feature_selection", {})
    if not isinstance(selection, dict) or set(selection) - {"min_coverage", "correlation_threshold", "max_drugs"}:
        raise IntegrityError("Unknown feature_selection setting.")
    for key in ["min_coverage", "correlation_threshold"]:
        value = selection.get(key, 0.2 if key == "min_coverage" else 0.95)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 1:
            raise IntegrityError(f"Invalid feature_selection {key}.")
    maximum = selection.get("max_drugs")
    if maximum is not None and (isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1):
        raise IntegrityError("max_drugs must be a positive integer or null.")
    families = cfg.get("model_families")
    if families is not None and (not isinstance(families, list) or not families or
                                 not set(families) <= {"random_forest", "xgboost", "logistic", "hist_gradient_boosting"}):
        raise IntegrityError("Unsupported model_families.")
    for name in drugs:
        if framework:
            if name not in ANTIBIOTICS | COMBINATIONS:
                raise IntegrityError(f"Unsupported antibiotic predictor: {name}")
            # Target and products containing it are direct susceptibility proxies.
            if name == cfg["target"] or name.startswith(cfg["target"] + "-") or cfg["target"].startswith(name + "-"):
                raise IntegrityError(f"Target antibiotic leakage: {name}")
            continue
        if any(c in name for c in CARBAPENEMS) or name in {"ndm", "oxa48", "species", "country"}:
            raise IntegrityError(f"Forbidden primary feature: {name}")
        if "/" in name or "-" in name:
            raise IntegrityError("v0.1 accepts single-drug MIC features only; combination ratios require review.")
    if cfg.get("include_species", False) and not framework:
        raise IntegrityError("Core models are phenotype-only; species is implemented as a separate baseline.")
    for name in set(drugs + [cfg["target"]]) & COMBINATIONS:
        review = cfg.get("combination_reviews", {}).get(name, {})
        concentration = review.get("fixed_inhibitor_mg_l")
        if not review.get("citation") or review.get("reviewed") is not True or isinstance(concentration, bool) or not isinstance(concentration, (int, float)) or not math.isfinite(concentration) or concentration <= 0:
            raise IntegrityError(f"Combination {name} requires reviewed citation and fixed_inhibitor_mg_l; ratio MICs are not collapsed.")
    if not 1 <= cfg.get("min_observed_features", 1) <= len(drugs):
        raise IntegrityError("Invalid minimum feature count.")
    if not isinstance(cfg.get("species"), list) or not cfg["species"] or any(not known(s) for s in cfg["species"]):
        raise IntegrityError("Provide a nonempty species allowlist.")
    for field, default, lower, upper, inclusive in [
        ("sensitivity_target", .95, 0, 1, False),
        ("specificity_target", .5, 0, 1, True),
        ("deferral_halfwidth", .1, 0, .5, True),
    ]:
        value = cfg.get(field, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not (lower <= value <= upper) or (not inclusive and value == lower) or (field == "deferral_halfwidth" and value == upper):
            raise IntegrityError(f"Invalid {field}.")
    repeats = cfg.get("bootstrap_repeats", 200)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise IntegrityError("bootstrap_repeats must be a positive integer.")
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
    if cfg.get("standard_version") and str(rules["version"]) != str(cfg["standard_version"]):
        raise IntegrityError("Breakpoint version differs from study configuration.")
    return rules


def identity_tokens(row):
    """Recorded identity links only; hospital IDs must be consistently curated across sources."""
    from .harmonization import known
    tokens = {'isolate:' + row['isolate_id']}
    if known(row.get('patient_id', '')):
        if known(row.get('source_id', '')):
            tokens.add('patient:' + row['source_id'] + ':' + row['patient_id'])
        if known(row.get('hospital_id', '')):
            tokens.add('hospital_patient:' + row['hospital_id'] + ':' + row['patient_id'])
    if known(row.get('duplicate_group', '')):
        tokens.add('duplicate:' + row['duplicate_group'])
    return tokens


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
        for token in sorted(identity_tokens(row)):
            if token in seen:
                parent[root(i)] = root(seen[token])
            else:
                seen[token] = i
    return ["G" + str(root(i)) for i in range(len(cohort))]


def build_cohort(path, config, breakpoint_file=None, progress=None):
    cfg = validate_config(config)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    # Formatting whitespace must not create different patient or isolate identities.
    for column in raw.columns:
        raw[column] = raw[column].str.strip()
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
                "tested_concentrations", "qc_reference", "curation_status", "fixed_inhibitor_mg_l"]:
        if col not in raw:
            raw[col] = ""
    for c in MECHANISMS:
        if c not in raw:
            raw[c] = "unknown"
        raw[c] = raw[c].replace("", "unknown")
        if not set(raw[c]) <= {"positive", "negative", "unknown"}:
            raise IntegrityError(f"Invalid {c} state; use positive, negative, unknown.")
    annotated = raw[list(MECHANISMS)].ne("unknown").any(axis=1)
    from .harmonization import known
    for c in ['patient_id', 'duplicate_group', 'hospital_id']:
        raw[c] = raw[c].map(lambda value: value if known(value) else '')
    if (annotated & ~raw.mechanism_evidence.map(known)).any():
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
                       "duplicate_group", "host", *MECHANISMS, "mechanism_evidence", "region", "hospital_id", "lab_id"]
    groups = raw.groupby("isolate_id", sort=True)
    if progress:
        progress(f"Auditing {len(raw)} observation rows across {len(groups)} isolate groups")
    for group_index, (isolate, block) in enumerate(groups):
        if progress and group_index % 100 == 0:
            progress(f"Auditing isolate group {group_index + 1} of {len(groups)}")
        if block.curation_status.str.upper().str.contains('QUARANTIN|REVIEW_REQUIRED|PROPOSED', regex=True).any():
            exclusions.append({"isolate_id": isolate, "reason": "curation_quarantined"}); continue
        for column in metadata_fields:
            if block[column].nunique() > 1:
                raise IntegrityError(f"Conflicting {column} for isolate {isolate}; curate before training.")
        meta = block.iloc[0]
        from .harmonization import known
        if cfg.get("require_known_source", False) and not known(meta.source_id):
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
            cols = ["measurement", "operator", "units", "method", "standard", "standard_version", "sir", "lab_id", "platform", "panel_id", "tested_concentrations", "qc_reference", "fixed_inhibitor_mg_l"]
            unique = values.drop_duplicates(cols)
            if len(unique) != 1:
                exclusions.append({"isolate_id": isolate, "drug": drug, "reason": "conflicting_replicates"})
                continue
            record = unique.iloc[0]
            if drug in COMBINATIONS and drug in cfg.get('combination_reviews', {}):
                expected = cfg['combination_reviews'][drug]['fixed_inhibitor_mg_l']
                try:
                    valid = math.isclose(float(record.fixed_inhibitor_mg_l), expected, rel_tol=1e-9)
                except ValueError:
                    valid = False
                if not valid:
                    exclusions.append({'isolate_id': isolate, 'drug': drug, 'reason': 'combination_inhibitor_unverified'})
                    continue
            by_drug[drug] = record
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
        if issue and (cfg.get("comparability_policy") == "strict" or issue in {"dilution_panel_invalid", "drug_method_incompatible"}):
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
                        elif provenance_issue(r, cfg, True) and (cfg.get("comparability_policy") == "strict" or provenance_issue(r, cfg, True) == 'drug_method_incompatible'):
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
                    if issue and (cfg.get("comparability_policy") == "strict" or issue in {"dilution_panel_invalid", "drug_method_incompatible"}):
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
        if any(meta[m] != "unknown" for m in ("kpc", "vim", "imp")):
            positives = [m.upper() for m in MECHANISMS if meta[m] == "positive"]
            unknown = [m.upper() for m in MECHANISMS if meta[m] == "unknown"]
            result["mechanism"] = ("+".join(positives) or "assayed_negative") + (";unassayed=" + "+".join(unknown) if unknown else "")
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
             "breakpoints_sha256": sha256(breakpoint_file) if rules else None,
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
             "task": cfg.get("task", "legacy_carbapenem_resistance"), "target": cfg["target"],
             "panel_coverage": [{"drug": d, "source_id": source, "isolates": len(part),
                                 "observed": int(part[f"{d}__missing"].eq(0).sum()),
                                 "coverage": float(part[f"{d}__missing"].eq(0).mean()),
                                 "purpose": "descriptive audit only; selection uses training folds"}
                                for source, part in cohort.groupby("source_id") for d in cfg["features"]],
             "limitations": ["Not a representative sample unless acquisition design establishes it.",
                             "No clinical or causal validation.", "Missing patient IDs limit independence claims."]}
    if not synthetic and cfg["label_mode"] == "reported" and cfg.get("allow_unversioned_reported"):
        audit["limitations"].append("Reported labels may be unversioned; not breakpoint-harmonized.")
    if cfg.get("representation") == "categorical_ast":
        audit["limitations"].append("Categorical model: S, I, R, SDD and missing encoded separately; no numeric MICs inferred.")
    return cohort, audit, pd.DataFrame(exclusions), feature_cols
