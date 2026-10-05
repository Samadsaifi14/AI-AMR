"""Chunked wide-table import with explicit reviewed mappings; no guessed clinical units."""
import json
from pathlib import Path
import pandas as pd
from .data import IntegrityError, REQUIRED, sha256


def import_wide(source, mapping_path, destination, chunksize=10000):
    mapping = json.loads(Path(mapping_path).read_text())
    metadata = mapping.get('metadata', {})
    constants = mapping.get('constants', {})
    drugs = mapping.get('drugs', {})
    if not drugs or not {'isolate_id','source_id','species'} <= set(metadata) | set(constants):
        raise IntegrityError('Map isolate_id, source_id, species and at least one drug explicitly.')
    if set(metadata) & set(constants):
        raise IntegrityError('Metadata columns and constants must not overlap.')
    for drug, fields in drugs.items():
        if not fields.get('measurement'):
            raise IntegrityError(f'Map a MIC measurement column for {drug}; categorical AST is not converted to MIC.')
    out = Path(destination)
    if out.exists():
        raise IntegrityError('Output exists; select a new output path.')
    out.parent.mkdir(parents=True,exist_ok=True)
    input_rows = output_rows = 0
    first = True
    try:
        with out.open('x',encoding='utf-8',newline='') as handle:
            for chunk in pd.read_csv(source,dtype=str,keep_default_na=False,chunksize=chunksize):
                needed = set(metadata.values()) | {v for fields in drugs.values() for v in fields.values()}
                if not needed <= set(chunk.columns):
                    raise IntegrityError(f'Mapped source columns missing: {sorted(needed-set(chunk.columns))}')
                input_rows += len(chunk)
                base = pd.DataFrame({k:chunk[v] for k,v in metadata.items()})
                for k,v in constants.items():
                    base[k] = str(v)
                for drug, fields in drugs.items():
                    frame = base.copy()
                    frame['drug'] = drug
                    for name,column in fields.items():
                        frame[name] = chunk[column]
                    for name in REQUIRED - set(frame.columns):
                        frame[name] = ''
                    # Preserve all source rows, including missing measurements, for downstream audit.
                    frame = frame.reindex(columns=sorted(set(metadata) | set(constants) | REQUIRED | {k for f in drugs.values() for k in f}))
                    frame.to_csv(handle,index=False,header=first)
                    first = False
                    output_rows += len(frame)
    except Exception:
        out.unlink(missing_ok=True)
        raise
    manifest = {'input_sha256':sha256(source),'mapping_sha256':sha256(mapping_path),
                'output_sha256':sha256(out),'input_rows':input_rows,'output_rows':output_rows,
                'row_subsampling':False,'mapping':mapping}
    out.with_suffix(out.suffix+'.provenance.json').write_text(json.dumps(manifest,indent=2))
    return manifest
