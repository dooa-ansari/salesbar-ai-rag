"""API-level tests: request validation, 404s for a missing graph id, and the
search endpoint's resilience (results still come back even if answer
synthesis fails). neo4j_client/openrouter_client are monkeypatched — no real
Neo4j or OpenRouter call happens here."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from ai_core_backend import neo4j_client, openrouter_client

# Not `from ai_core_backend import main` — ai_core_backend/__init__.py's own `main()` CLI
# stub would shadow the `ai_core_backend.main` submodule in that form.
from ai_core_backend.main import app
from ai_core_backend.openrouter_client import OpenRouterError
from ai_core_backend.schemas import SavedGraphSummary


@pytest.fixture
def client(monkeypatch):
    # Startup touches real infra otherwise — not what these tests are about.
    monkeypatch.setattr(neo4j_client, "ensure_vector_index", AsyncMock())
    monkeypatch.setattr(neo4j_client, "has_any_saved_graph", AsyncMock(return_value=True))
    monkeypatch.setattr(neo4j_client, "close_driver", AsyncMock())
    with TestClient(app) as test_client:
        yield test_client


def test_save_graph_blank_name_is_rejected(client, monkeypatch):
    save_graph = AsyncMock()
    monkeypatch.setattr(neo4j_client, "save_graph", save_graph)

    response = client.post("/graphs", json={"name": "   ", "nodes": [], "edges": []})

    assert response.status_code == 422
    save_graph.assert_not_called()


def test_save_graph_happy_path(client, monkeypatch):
    monkeypatch.setattr(
        neo4j_client,
        "save_graph",
        AsyncMock(
            return_value=SavedGraphSummary(
                id="g1", name="My Graph", updatedAt="2026-01-01T00:00:00Z", nodes=0, edges=0
            )
        ),
    )

    response = client.post("/graphs", json={"name": "My Graph", "nodes": [], "edges": []})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "g1"
    assert body["status"] == "success"


def test_get_graph_not_found_is_404(client, monkeypatch):
    monkeypatch.setattr(neo4j_client, "get_graph", AsyncMock(return_value=None))

    response = client.get("/graphs/does-not-exist")

    assert response.status_code == 404


def test_save_text_blank_is_rejected(client):
    response = client.put("/graphs/g1/text", json={"text": "   "})
    assert response.status_code == 422


def test_save_text_missing_graph_is_404(client, monkeypatch):
    monkeypatch.setattr(neo4j_client, "save_graph_text", AsyncMock(return_value=False))

    response = client.put("/graphs/missing/text", json={"text": "hello"})

    assert response.status_code == 404


def test_generate_embeddings_rejects_empty_node_list(client):
    response = client.post("/graphs/g1/embeddings", json={"nodes": []})
    assert response.status_code == 422


def test_generate_embeddings_missing_graph_is_404(client, monkeypatch):
    monkeypatch.setattr(
        openrouter_client, "generate_embeddings", AsyncMock(return_value=[[0.1, 0.2]])
    )
    monkeypatch.setattr(neo4j_client, "save_node_embeddings", AsyncMock(return_value=False))

    response = client.post(
        "/graphs/missing/embeddings", json={"nodes": [{"id": "n1", "text": "Alice is a person."}]}
    )

    assert response.status_code == 404


def test_search_rejects_blank_query(client):
    response = client.post("/graphs/g1/search", json={"query": "  "})
    assert response.status_code == 422


@pytest.mark.parametrize("limit", [0, -1, 51, 2_000_000_000])
def test_search_rejects_limit_outside_1_to_50(client, limit):
    # A client-supplied `limit` feeds directly into Neo4j's vector overfetch
    # (limit * 10) and a Cypher LIMIT clause, which rejects negative values
    # with an unhandled error rather than a clean 4xx — so this is bounded
    # at the schema level instead.
    response = client.post("/graphs/g1/search", json={"query": "hello", "limit": limit})
    assert response.status_code == 422


def test_save_graph_rejects_a_node_name_over_the_length_limit(client):
    response = client.post(
        "/graphs",
        json={
            "name": "My Graph",
            "nodes": [
                {
                    "id": "n1",
                    "type": "graph",
                    "position": {"x": 0, "y": 0},
                    "data": {"name": "x" * 201, "type": "Person", "properties": []},
                }
            ],
            "edges": [],
        },
    )
    assert response.status_code == 422


def test_search_missing_graph_is_404(client, monkeypatch):
    monkeypatch.setattr(
        openrouter_client, "generate_embeddings", AsyncMock(return_value=[[0.1]])
    )
    monkeypatch.setattr(neo4j_client, "search_graph_nodes", AsyncMock(return_value=None))

    response = client.post("/graphs/missing/search", json={"query": "who is the father?"})

    assert response.status_code == 404


def test_search_still_returns_results_when_answer_synthesis_fails(client, monkeypatch):
    # The whole point of making answer synthesis "best-effort": a flaky LLM
    # call must not take the matched nodes down with it.
    from ai_core_backend.schemas import SearchResultNode

    monkeypatch.setattr(
        openrouter_client, "generate_embeddings", AsyncMock(return_value=[[0.1]])
    )
    monkeypatch.setattr(
        neo4j_client,
        "search_graph_nodes",
        AsyncMock(
            return_value=[
                SearchResultNode(id="n1", name="Robert", type="Person", score=0.9)
            ]
        ),
    )
    monkeypatch.setattr(neo4j_client, "get_node_relationships", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        openrouter_client, "generate_answer", AsyncMock(side_effect=OpenRouterError("down"))
    )

    response = client.post("/graphs/g1/search", json={"query": "who is the father?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] is None
    assert len(body["results"]) == 1
    assert body["results"][0]["name"] == "Robert"


def test_health_reports_503_when_neo4j_unreachable(client, monkeypatch):
    monkeypatch.setattr(
        neo4j_client, "verify_connectivity", AsyncMock(side_effect=RuntimeError("down"))
    )

    response = client.get("/health")

    assert response.status_code == 503


def test_health_reports_ok_when_neo4j_reachable(client, monkeypatch):
    monkeypatch.setattr(neo4j_client, "verify_connectivity", AsyncMock())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
