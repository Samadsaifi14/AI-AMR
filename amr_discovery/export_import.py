"""Import an NCBI AST export without guessing laboratory or study provenance."""
import io
import json
import hashlib
import math
import pandas as pd
from .data import IntegrityError, REQUIRED, drug_name, SIR

EXPORT_FIELDS = {'#BioSample', 'Scientific name', 'Antibiotic', 'Resistance phenotype',
                 'Measurement sign', 'MIC (mg/L)', 'Testing standard'}


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def import_ncbi_export(csv, reference_csv=''):
    """The reference is a documented prior acquisition, not a generated mapping.

    Join on accession, species, drug, standard, phenotype, MIC and censoring.
    Unmatched observations retain their input values but are quarantined.
    Submission dates are not specimen collection dates; platform is not method.
    """
    frame = pd.read_csv(io.StringIO(csv), dtype=str, keep_default_na=False)
    if frame.empty or not EXPORT_FIELDS <= set(frame):
        raise IntegrityError('Expected a nonempty NCBI AST export with its original headers.')
    if any(frame[c].str.strip().eq('').any() for c in ['#BioSample','Scientific name','Antibiotic']):
        raise IntegrityError('Export has missing accession, species or antibiotic.')
    refs = {}
    if reference_csv:
        reference = pd.read_csv(io.StringIO(reference_csv), dtype=str, keep_default_na=False)
        if not REQUIRED <= set(reference):
            raise IntegrityError('Provenance reference must be canonical observations.')
        for row in reference.to_dict('records'):
            key = (row['isolate_id'], row['species'], drug_name(row['drug']), row['standard'].upper(),
                   SIR.get(row['reported_sir'].lower()), _number(row['measurement']), row['operator'])
            refs.setdefault(key, []).append(row)
    rows, matched, quarantined = [], 0, 0
    for index, row in enumerate(frame.to_dict('records'), 2):
        drug = drug_name(row['Antibiotic'])
        value, operator = row['MIC (mg/L)'], row['Measurement sign']
        standard = row['Testing standard'].upper().strip()
        sir = SIR.get(row['Resistance phenotype'].strip().lower(), 'unknown')
        key = (row['#BioSample'], row['Scientific name'], drug, standard, sir, _number(value), operator)
        candidates = refs.get(key, [])
        provenance = ['source_id','host','method','standard_version','country','collection_date',
                      'patient_id','duplicate_group','lab_id','hospital_id','region','qc_reference']
        signatures = {tuple(x.get(c, '') for c in provenance) for x in candidates}
        verified = len(signatures) == 1 and bool(candidates) and _number(value) is not None
        original = candidates[0] if verified else {}
        result = {c: original.get(c, '') for c in provenance}
        result.update(isolate_id=row['#BioSample'], species=row['Scientific name'], drug=drug,
                      measurement=value, operator=operator, units='mg/L', standard=standard,
                      reported_sir=sir, evidence_class='measured_public',
                      platform=row.get('Laboratory typing platform', ''),
                      accession=row['#BioSample'], source_row=f'uploaded_ncbi_export:{index}',
                      submission_date=row.get('Create date', ''),
                      ndm='unknown', oxa48='unknown', mechanism_evidence='not_supplied',
                      curation_status='MATCHED_PRIOR_ACQUISITION' if verified else 'QUARANTINED_PROVENANCE_REQUIRED')
        if not verified:
            result['source_id'] = 'unknown'
            result['method'] = 'unknown'
            result['country'] = row.get('Location', '').split(':')[0].strip()
        for c in REQUIRED:
            result.setdefault(c, '')
        rows.append(result)
        matched += int(verified)
        quarantined += int(not verified)
    output = pd.DataFrame(rows).to_csv(index=False, lineterminator='\n')
    manifest = {'schema':1, 'status':'IMPORTED_REVIEW_REQUIRED', 'rows':len(rows),
                'isolates':frame['#BioSample'].nunique(), 'matched_rows':matched,
                'quarantined_rows':quarantined, 'input_sha256':hashlib.sha256(csv.encode()).hexdigest(),
                'reference_sha256':hashlib.sha256(reference_csv.encode()).hexdigest() if reference_csv else None,
                'output_sha256':hashlib.sha256(output.encode()).hexdigest(),
                'drugs':sorted({r['drug'] for r in rows}),
                'clinical_validation':False,
                'note':'No patient IDs, study IDs, human host, methods, standard versions or collection dates were guessed. Imported labels remain exploratory when version is unknown.'}
    return output, manifest
