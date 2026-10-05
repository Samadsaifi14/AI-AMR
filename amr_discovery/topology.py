"""Development-only gene co-occurrence and documented spatial proximity.

Edges describe observations, not interactions, transmission, or ancestry.
Unknown gene calls are excluded from pair denominators, never treated as absent.
"""
from itertools import combinations
import math
import pandas as pd
from .data import IntegrityError


def gene_network(frame, training_ids):
    required = {'isolate_id', 'gene', 'status', 'evidence_reference'}
    if not required <= set(frame):
        raise IntegrityError(f'Gene CSV needs {sorted(required)}')
    f = frame.copy().fillna('')
    if not f.status.isin(['positive', 'negative', 'unknown']).all():
        raise IntegrityError('Gene status must be positive, negative, or unknown.')
    if (f.evidence_reference.str.strip() == '').any():
        raise IntegrityError('Every gene call needs an evidence reference.')
    if (f.gene.str.strip() == '').any() or (f.isolate_id.str.strip() == '').any():
        raise IntegrityError('Blank gene or isolate identifier.')
    if f.duplicated(['isolate_id', 'gene']).any():
        raise IntegrityError('Resolve duplicate isolate/gene calls before analysis.')
    f = f[f.isolate_id.isin(training_ids)]
    if f.empty:
        raise IntegrityError('No gene calls match development training isolates.')
    if f.gene.nunique() > 100 or f.isolate_id.nunique() > 10000:
        raise IntegrityError('Browser network limit: 100 genes and 10,000 isolates.')
    m = f.pivot(index='isolate_id', columns='gene', values='status')
    edges = []
    for a, b in combinations(sorted(m.columns), 2):
        known = m[a].isin(['positive', 'negative']) & m[b].isin(['positive', 'negative'])
        pa, pb = m.loc[known, a].eq('positive'), m.loc[known, b].eq('positive')
        union, both = int((pa | pb).sum()), int((pa & pb).sum())
        edges.append(dict(gene_a=a, gene_b=b, jointly_observed=int(known.sum()),
                          co_positive=both, positive_union=union,
                          jaccard=both / union if union else None))
    return pd.DataFrame(edges, columns=['gene_a','gene_b','jointly_observed','co_positive','positive_union','jaccard'])


def spatial_edges(frame, training_ids, radius_km=25., window_days=30):
    required = {'isolate_id', 'latitude', 'longitude', 'collection_date', 'location_reference'}
    if not required <= set(frame):
        raise IntegrityError(f'Geography CSV needs {sorted(required)}')
    if not 0 < radius_km <= 500 or not 0 <= window_days <= 365:
        raise IntegrityError('Radius must be (0,500] km; time window [0,365] days.')
    f = frame.copy()
    if f.isolate_id.duplicated().any():
        raise IntegrityError('Geography needs one documented location per isolate.')
    if f.location_reference.fillna('').str.strip().eq('').any():
        raise IntegrityError('Every coordinate needs a location reference.')
    for col, bound in [('latitude',90),('longitude',180)]:
        f[col] = pd.to_numeric(f[col], errors='coerce')
        if not f[col].between(-bound,bound).all():
            raise IntegrityError('Invalid or missing coordinates.')
    f.collection_date = pd.to_datetime(f.collection_date, format='%Y-%m-%d', errors='coerce')
    if f.collection_date.isna().any():
        raise IntegrityError('Use complete YYYY-MM-DD dates for spatial analysis.')
    f = f[f.isolate_id.isin(training_ids)]
    if f.empty:
        raise IntegrityError('No geographic rows match development training isolates.')
    if len(f) > 1000:
        raise IntegrityError('Browser spatial limit is 1,000 training locations.')
    rows = []
    for a,b in combinations(f.itertuples(index=False),2):
        days = abs((a.collection_date-b.collection_date).days)
        if days > window_days:
            continue
        la,lb = math.radians(a.latitude),math.radians(b.latitude)
        dl,do = lb-la,math.radians(b.longitude-a.longitude)
        h = math.sin(dl/2)**2 + math.cos(la)*math.cos(lb)*math.sin(do/2)**2
        distance = 6371.0088 * 2 * math.asin(math.sqrt(min(1,max(0,h))))
        if distance <= radius_km:
            rows.append(dict(isolate_a=a.isolate_id,isolate_b=b.isolate_id,distance_km=distance,days_apart=days))
    return pd.DataFrame(rows,columns=['isolate_a','isolate_b','distance_km','days_apart'])
