import os

import pytest

from ai_core_backend import neo4j_client

TEST_NEO4J_URI = os.environ.get("TEST_NEO4J_URI")
TEST_NEO4J_USER = os.environ.get("TEST_NEO4J_USER", "neo4j")
TEST_NEO4J_PASSWORD = os.environ.get("TEST_NEO4J_PASSWORD", "testpassword")
GRAPH_PREFIX = "itest-"

DELETE_TEST_GRAPHS = """
MATCH (g:SavedGraph) WHERE g.name STARTS WITH $prefix
OPTIONAL MATCH (g)-[:HAS_NODE]->(n:GraphNode)
DETACH DELETE n, g
"""


async def _delete_test_graphs():
    async with neo4j_client.get_driver().session() as session:
        await session.run(DELETE_TEST_GRAPHS, prefix=GRAPH_PREFIX)


@pytest.fixture
async def neo4j(monkeypatch):
    if not TEST_NEO4J_URI:
        pytest.skip("set TEST_NEO4J_URI to a throwaway Neo4j to run integration tests")
    monkeypatch.setattr(neo4j_client, "NEO4J_URI", TEST_NEO4J_URI)
    monkeypatch.setattr(neo4j_client, "NEO4J_USER", TEST_NEO4J_USER)
    monkeypatch.setattr(neo4j_client, "NEO4J_PASSWORD", TEST_NEO4J_PASSWORD)
    monkeypatch.setattr(neo4j_client, "_driver", None)
    await neo4j_client.ensure_vector_index()
    await _delete_test_graphs()
    yield neo4j_client
    await _delete_test_graphs()
    await neo4j_client.close_driver()
