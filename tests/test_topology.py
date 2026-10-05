import pandas as pd
import pytest
from amr_discovery.data import IntegrityError
from amr_discovery.topology import gene_network, spatial_edges


def test_unknown_and_test_isolates_do_not_contribute_to_gene_edges():
    f = pd.DataFrame([
        ['train','a','positive','assay'],['train','b','unknown','assay'],
        ['test','a','positive','assay'],['test','b','positive','assay'],
    ], columns=['isolate_id','gene','status','evidence_reference'])
    edge = gene_network(f, {'train'}).iloc[0]
    assert edge.jointly_observed == 0
    assert edge.co_positive == 0
    assert pd.isna(edge.jaccard)


def test_duplicate_gene_calls_are_blocked():
    f = pd.DataFrame([['x','a','positive','assay']]*2,
                     columns=['isolate_id','gene','status','evidence_reference'])
    with pytest.raises(IntegrityError, match='duplicate'):
        gene_network(f, {'x'})


def test_spatial_edges_require_time_and_development_membership():
    f = pd.DataFrame([
        ['a','12','77','2024-01-01','hospital'],
        ['b','12','77','2024-01-02','hospital'],
        ['late','12','77','2025-01-01','hospital'],
        ['test','12','77','2024-01-01','hospital'],
    ],columns=['isolate_id','latitude','longitude','collection_date','location_reference'])
    edges = spatial_edges(f, {'a','b','late'})
    assert len(edges) == 1
    assert edges.iloc[0].distance_km == 0
    assert edges.iloc[0].days_apart == 1


def test_invalid_coordinates_are_blocked():
    f = pd.DataFrame([['a','91','77','2024-01-01','hospital']],
                     columns=['isolate_id','latitude','longitude','collection_date','location_reference'])
    with pytest.raises(IntegrityError, match='coordinates'):
        spatial_edges(f, {'a'})
