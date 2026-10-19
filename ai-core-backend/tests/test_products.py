import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ai_core_backend import neo4j_client, openrouter_client
from ai_core_backend.main import app
from ai_core_backend.schemas import ProductAttribute, ProductSummary, SearchRequest


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


class _Tx:
    def __init__(self, exists=True, records=None):
        self.calls = []
        self._exists = exists
        self._records = records or []

    async def run(self, query, **params):
        self.calls.append((query, params))
        if query.startswith("MATCH (g:SavedGraph {id: $graphId}) RETURN g.id AS id"):
            return _Result(single={"id": params["graphId"]} if self._exists else None)
        return _Result(records=self._records)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(neo4j_client, "ensure_vector_index", AsyncMock())
    monkeypatch.setattr(neo4j_client, "has_any_saved_graph", AsyncMock(return_value=True))
    monkeypatch.setattr(neo4j_client, "close_driver", AsyncMock())
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_list_products_unknown_catalog_returns_none():
    assert await neo4j_client._list_products_tx(_Tx(exists=False), "missing") is None


@pytest.mark.anyio
async def test_list_products_parses_properties_and_attributes():
    record = {
        "id": "JA01",
        "catalogId": "c1",
        "name": "Trail Shell",
        "description": "Light rain shell.",
        "propertiesJson": json.dumps([{"name": "price", "type": "float", "value": 89.0}]),
        "attributes": [
            {"key": "BELONGS_TO", "relationship": "belongs to", "name": "Jackets", "propertiesJson": None},
            {
                "key": "AVAILABLE_IN",
                "relationship": "is available in",
                "name": "M",
                "propertiesJson": json.dumps([{"name": "stock", "type": "integer", "value": 2}]),
            },
        ],
    }
    tx = _Tx(records=[record])

    (product,) = await neo4j_client._list_products_tx(tx, "c1")

    query, params = tx.calls[-1]
    assert params["productType"] == "Product"
    assert params["graphId"] == "c1"
    assert product.properties[0].value == 89.0
    assert product.attributes[0] == ProductAttribute(key="BELONGS_TO", relationship="belongs to", name="Jackets")
    assert product.attributes[1].properties[0].value == 2


@pytest.mark.anyio
async def test_search_can_be_limited_to_one_node_type():
    tx = _Tx()
    await neo4j_client._search_graph_nodes_tx(tx, "c1", [0.1], 5, "Product")
    query, params = tx.calls[-1]
    assert "node.entityType = $nodeType" in query
    assert params["nodeType"] == "Product"


@pytest.mark.anyio
async def test_search_without_node_type_matches_every_type():
    tx = _Tx()
    await neo4j_client._search_graph_nodes_tx(tx, "c1", [0.1], 5)
    assert tx.calls[-1][1]["nodeType"] is None


def test_search_request_node_type_defaults_to_none():
    assert SearchRequest(query="jacket").nodeType is None


def test_products_endpoint_missing_graph_is_404(client, monkeypatch):
    monkeypatch.setattr(neo4j_client, "list_products", AsyncMock(return_value=None))
    assert client.get("/graphs/missing/products").status_code == 404


def test_products_endpoint_returns_products(client, monkeypatch):
    product = ProductSummary(id="JA01", name="Trail Shell")
    monkeypatch.setattr(neo4j_client, "list_products", AsyncMock(return_value=[product]))

    response = client.get("/graphs/c1/products")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Trail Shell"


def test_search_endpoint_passes_node_type(client, monkeypatch):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(openrouter_client, "generate_embeddings", AsyncMock(return_value=[[0.1]]))
    monkeypatch.setattr(neo4j_client, "search_graph_nodes", search)

    response = client.post("/graphs/c1/search", json={"query": "jacket", "nodeType": "Product"})

    assert response.status_code == 200
    assert search.call_args.args[3] == "Product"


def _clothes_catalog(monkeypatch):
    from shop_fixtures import Clothes

    from ai_core_backend.schemas import SavedGraphSummary, SearchResultNode

    clothes = Clothes()
    monkeypatch.setattr(
        neo4j_client,
        "list_graphs",
        AsyncMock(return_value=[SavedGraphSummary(id="c1", name="Clothes Catalog", updatedAt="", nodes=0, edges=0)]),
    )
    monkeypatch.setattr(
        neo4j_client,
        "catalog_vocabulary",
        AsyncMock(return_value=[{"id": n.id, "name": n.name, "type": n.type} for n in clothes.vocabulary]),
    )
    small = clothes.node("Size", "S")
    monkeypatch.setattr(
        neo4j_client,
        "search_graph_nodes",
        AsyncMock(
            side_effect=lambda graph_id, embedding, limit, node_type: [
                SearchResultNode(id=small.id, name=small.name, type=small.type, score=0.8)
            ]
            if node_type == "Size"
            else []
        ),
    )
    monkeypatch.setattr(
        neo4j_client, "product_matches", AsyncMock(side_effect=lambda graph_id, ids, *args: clothes.rows(ids))
    )
    monkeypatch.setattr(openrouter_client, "generate_embeddings", AsyncMock(side_effect=lambda texts: [[0.1]] * len(texts)))
    return clothes


def test_shop_search_links_model_values_to_graph_nodes(client, monkeypatch):
    clothes = _clothes_catalog(monkeypatch)
    reply = '{"require": [{"type": "Colour", "value": "Blue"}, {"type": "Category", "value": "T-shirts"}, {"type": "Size", "value": "small"}]}'
    monkeypatch.setattr(openrouter_client, "chat", AsyncMock(return_value=reply))

    response = client.post("/graphs/c1/shop-search", json={"query": "blue shirt in size small"})

    assert response.status_code == 200
    body = response.json()
    assert [c["label"] for c in body["constraints"]] == ["Blue", "T-shirts", "Size S"]
    assert clothes.name(body["results"][0]["productId"]) == "Recycled Run Tee"
    assert body["results"][0]["match"] == "exact"


def test_shop_search_fails_when_the_model_fails(client, monkeypatch):
    from ai_core_backend.openrouter_client import OpenRouterError

    _clothes_catalog(monkeypatch)
    monkeypatch.setattr(openrouter_client, "chat", AsyncMock(side_effect=OpenRouterError("down")))

    response = client.post("/graphs/c1/shop-search", json={"query": "jacket"})

    assert response.status_code == 502
    assert "down" in response.json()["detail"]


def test_shop_search_fails_when_the_model_reply_is_not_json(client, monkeypatch):
    _clothes_catalog(monkeypatch)
    monkeypatch.setattr(openrouter_client, "chat", AsyncMock(return_value="Sure! Here are some jackets."))

    response = client.post("/graphs/c1/shop-search", json={"query": "jacket"})

    assert response.status_code == 502


def test_shop_search_fails_when_embeddings_fail(client, monkeypatch):
    from ai_core_backend.openrouter_client import OpenRouterError

    _clothes_catalog(monkeypatch)
    monkeypatch.setattr(openrouter_client, "chat", AsyncMock(return_value='{"require": [{"type": "Category", "value": "Jeans"}]}'))
    monkeypatch.setattr(openrouter_client, "generate_embeddings", AsyncMock(side_effect=OpenRouterError("down")))

    response = client.post("/graphs/c1/shop-search", json={"query": "jeans"})

    assert response.status_code == 502
    assert "Could not embed the query" in response.json()["detail"]


def test_shop_search_missing_graph_is_404(client, monkeypatch):
    monkeypatch.setattr(neo4j_client, "list_graphs", AsyncMock(return_value=[]))
    assert client.post("/graphs/missing/shop-search", json={"query": "jacket"}).status_code == 404


def test_shop_search_blank_query_is_422(client):
    assert client.post("/graphs/c1/shop-search", json={"query": "  "}).status_code == 422
