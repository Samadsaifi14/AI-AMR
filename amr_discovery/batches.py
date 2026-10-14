"""Append-only, content-addressed observation updates shared by browser and CLI."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import pandas as pd
from .data import IntegrityError, REQUIRED, drug_name


def merge_observations(batch_csv: str, base_csv: str = ""):
    frames = []
    inputs = []
    for role, content in [("base", base_csv), ("batch", batch_csv)]:
        if not content.strip():
            if role == "batch":
                raise IntegrityError("Choose a non-empty new observations CSV.")
            continue
        try:
            frame = pd.read_csv(io.StringIO(content), dtype=str, keep_default_na=False)
        except (ValueError, pd.errors.ParserError) as e:
            raise IntegrityError(f"Cannot read {role} CSV: {e}") from e
        if frame.empty:
            raise IntegrityError(f"The {role} CSV has headers but no observation rows.")
        if len(frame.columns) != len(set(frame.columns)) or any('.' in c and c.rsplit('.',1)[-1].isdigit() for c in frame.columns):
            raise IntegrityError("Duplicate or ambiguous CSV column names; use the supplied template.")
        missing = REQUIRED - set(frame.columns)
        if missing:
            raise IntegrityError(f"The {role} CSV is missing columns: {', '.join(sorted(missing))}.")
        for key in ["isolate_id", "source_id", "species", "drug"]:
            if frame[key].str.strip().eq("").any():
                raise IntegrityError(f"The {role} CSV has missing {key}; obtain the original metadata.")
        for key in ["isolate_id", "source_id", "lab_id"]:
            if key in frame and (frame[key] != frame[key].str.strip()).any():
                raise IntegrityError(f"Remove leading or trailing whitespace from {key} before merging.")
        frame["drug"] = frame.drug.map(drug_name)
        frames.append(frame)
        inputs.append({"role":role,"sha256":hashlib.sha256(content.encode()).hexdigest(),"rows":len(frame)})
    merged = pd.concat(frames, ignore_index=True).fillna("")
    before = len(merged)
    merged = merged.drop_duplicates().reset_index(drop=True)
    keys = ["source_id", "isolate_id", "drug"]
    # An isolate identity cannot become two observations just by changing lab ID.
    conflict = merged.duplicated(keys, keep=False)
    if conflict.any():
        raise IntegrityError(f"{int(conflict.sum())} conflicting rows for the same source/isolate/drug. Review retests and metadata; no earlier result was overwritten.")
    # Reject cross-batch laboratory identity changes that could defeat lab holdouts.
    if "lab_id" in merged:
        labs=merged.groupby(["source_id","isolate_id"])["lab_id"].nunique()
        if (labs>1).any():
            raise IntegrityError("An isolate has conflicting lab IDs. Review provenance before combining batches.")
    content = merged.to_csv(index=False, lineterminator="\n")
    manifest={"schema_version":1,"status":"PREPARED_NOT_AUDITED","inputs":inputs,
              "rows":len(merged),"exact_duplicate_rows_removed":before-len(merged),
              "isolate_source_pairs":len(merged[keys[:2]].drop_duplicates()),
              "output_sha256":hashlib.sha256(content.encode()).hexdigest(),
              "next_step":"Audit under a reviewed configuration, then train a new run. Preparation does not establish measurement validity or accuracy. Reserve fresh independent evaluation data."}
    return content,manifest


def prepare_batch(batch_path, output, base_path=None):
    batch=Path(batch_path).read_text(encoding="utf-8-sig")
    base=Path(base_path).read_text(encoding="utf-8-sig") if base_path else ""
    content,manifest=merge_observations(batch,base)
    out=Path(output)
    out.mkdir(parents=True,exist_ok=False)
    (out/"observations.csv").write_text(content,encoding="utf-8",newline="")
    (out/"batch_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest
