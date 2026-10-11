"""Structural integrity of the example graphs loaded on first run.

These catch exactly the mistakes that are easy to make when hand-writing (or
table-generating) a graph's nodes/edges: a typo'd id, a duplicate, an edge
left pointing at a node that got renamed or removed.
"""

import pytest

from ai_core_backend.seed_data import SEED_GRAPHS


@pytest.mark.parametrize("graph", SEED_GRAPHS, ids=[g.name for g in SEED_GRAPHS])
def test_edges_reference_existing_nodes(graph):
    node_ids = {node.id for node in graph.nodes}
    dangling = [
        edge.id
        for edge in graph.edges
        if edge.source not in node_ids or edge.target not in node_ids
    ]
    assert dangling == []


@pytest.mark.parametrize("graph", SEED_GRAPHS, ids=[g.name for g in SEED_GRAPHS])
def test_no_duplicate_node_ids(graph):
    node_ids = [node.id for node in graph.nodes]
    assert len(node_ids) == len(set(node_ids))


@pytest.mark.parametrize("graph", SEED_GRAPHS, ids=[g.name for g in SEED_GRAPHS])
def test_no_duplicate_edge_ids(graph):
    edge_ids = [edge.id for edge in graph.edges]
    assert len(edge_ids) == len(set(edge_ids))


@pytest.mark.parametrize("graph", SEED_GRAPHS, ids=[g.name for g in SEED_GRAPHS])
def test_every_node_has_a_name_and_type(graph):
    for node in graph.nodes:
        assert node.data.name.strip()
        assert node.data.type.strip()


@pytest.mark.parametrize("graph", SEED_GRAPHS, ids=[g.name for g in SEED_GRAPHS])
def test_graph_is_non_empty(graph):
    assert graph.nodes
    assert graph.edges


def test_seed_graph_names_are_unique():
    # has_any_saved_graph() gates seeding on the whole DB being empty, but
    # within one seeding pass two graphs sharing a name would silently merge
    # (save_graph upserts by name).
    names = [graph.name for graph in SEED_GRAPHS]
    assert len(names) == len(set(names))
