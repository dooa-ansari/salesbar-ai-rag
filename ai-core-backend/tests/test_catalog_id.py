import pytest

from ai_core_backend import neo4j_client
from ai_core_backend.schemas import (
    GraphNode,
    GraphNodeData,
    NodeProperty,
    Position,
    SaveGraphRequest,
)


class _Result:
    def __init__(self, records=None, single=None):
        self._records = records or []
        self._single = single

    async def single(self):
        return self._single

    def __aiter__(self):
        self._iterator = iter(self._records)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class _RecordingTx:
    def __init__(self, exists=True):
        self.calls = []
        self._exists = exists

    async def run(self, query, **params):
        self.calls.append((query, params))
        if "RETURN g.id AS id" in query and "LIMIT" not in query:
            return _Result(single={"id": params.get("graphId") or params.get("newId")} if self._exists else None)
        return _Result()


@pytest.mark.anyio
async def test_search_filters_on_catalog_id():
    tx = _RecordingTx()
    results = await neo4j_client._search_graph_nodes_tx(tx, "catalog-1", [0.1, 0.2], 5)
    assert results == []
    query, params = tx.calls[-1]
    assert "node.catalogId = $graphId" in query
    assert params["graphId"] == "catalog-1"


@pytest.mark.anyio
async def test_search_unknown_catalog_returns_none():
    tx = _RecordingTx(exists=False)
    assert await neo4j_client._search_graph_nodes_tx(tx, "missing", [0.1], 5) is None


@pytest.mark.anyio
async def test_save_merges_nodes_within_their_catalog():
    node = GraphNode(
        id="brand-kindred",
        type="graph",
        position=Position(x=0, y=0),
        data=GraphNodeData(name="Kindred", type="Brand", properties=[]),
    )
    request = SaveGraphRequest(name="Catalog A", nodes=[node], edges=[])
    tx = _RecordingTx()
    await neo4j_client._save_graph_tx(
        tx,
        request.name,
        "catalog-a",
        "now",
        [neo4j_client._node_params(node)],
        [],
    )
    merge_calls = [(q, p) for q, p in tx.calls if "MERGE (n:GraphNode" in q]
    assert len(merge_calls) == 1
    query, params = merge_calls[0]
    assert "{catalogId: $graphId, id: node.id}" in query
    assert params["graphId"] == "catalog-a"


def test_client_supplied_catalog_id_is_not_persisted():
    node = GraphNode(
        id="n1",
        type="graph",
        position=Position(x=0, y=0),
        data=GraphNodeData(
            name="X", type="Thing", properties=[NodeProperty(name="a", value="b")]
        ),
        catalogId="someone-elses-catalog",
    )
    assert "catalogId" not in neo4j_client._node_params(node)
