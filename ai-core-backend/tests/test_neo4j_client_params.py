"""`_node_params`/`_edge_params` flatten the Pydantic request shapes into the
flat dicts Cypher's UNWIND expects — pure functions, worth pinning down since
a mistake here silently corrupts what gets saved rather than raising."""

import json

from ai_core_backend.neo4j_client import _edge_params, _node_params
from ai_core_backend.schemas import GraphEdge, GraphNode, GraphNodeData, NodeProperty, Position


def _node(**overrides) -> GraphNode:
    defaults = dict(
        id="n1",
        type="graph",
        position=Position(x=1.5, y=2.5),
        data=GraphNodeData(name="Alice", type="Person", description="A person.", properties=[]),
    )
    defaults.update(overrides)
    return GraphNode(**defaults)


def test_node_params_flattens_position_and_fields():
    params = _node_params(_node())
    assert params["id"] == "n1"
    assert params["reactFlowType"] == "graph"
    assert params["positionX"] == 1.5
    assert params["positionY"] == 2.5
    assert params["name"] == "Alice"
    assert params["entityType"] == "Person"
    assert params["description"] == "A person."


def test_node_params_encodes_properties_as_json():
    node = _node(
        data=GraphNodeData(
            name="Alice",
            type="Person",
            properties=[NodeProperty(name="age", value="30")],
        )
    )
    params = _node_params(node)
    assert json.loads(params["propertiesJson"]) == [{"name": "age", "value": "30"}]


def test_node_params_empty_properties_round_trips_to_empty_list():
    params = _node_params(_node())
    assert json.loads(params["propertiesJson"]) == []


def _edge(**overrides) -> GraphEdge:
    defaults = dict(id="e1", source="a", target="b", relationship="Father")
    defaults.update(overrides)
    return GraphEdge(**defaults)


def test_edge_params_without_bend_sends_null_coordinates():
    params = _edge_params(_edge())
    assert params["bendX"] is None
    assert params["bendY"] is None


def test_edge_params_with_bend_flattens_coordinates():
    params = _edge_params(_edge(bend=Position(x=10, y=-20)))
    assert params["bendX"] == 10
    assert params["bendY"] == -20


def test_edge_params_passes_through_handles_and_relationship():
    params = _edge_params(_edge(sourceHandle="link", targetHandle="in-bottom"))
    assert params["relationship"] == "Father"
    assert params["sourceHandle"] == "link"
    assert params["targetHandle"] == "in-bottom"
