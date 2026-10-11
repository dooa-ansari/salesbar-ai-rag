"""Neo4j connection and the Cypher that persists/reads named, saved graphs.

Each saved graph is a `:SavedGraph` node with its own `:GraphNode`s hanging
off it via `:HAS_NODE`. Saving under an existing name replaces that graph's
content but keeps its id; a new name adds a separate entry.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from neo4j import AsyncDriver, AsyncGraphDatabase

from ai_core_backend.openrouter_client import EMBEDDING_DIMENSIONS
from ai_core_backend.schemas import (
    GraphEdge,
    GraphNode,
    GraphNodeData,
    NamedGraphPayload,
    NodeProperty,
    Position,
    SaveGraphRequest,
    SavedGraphSummary,
    SearchResultNode,
)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def verify_connectivity() -> None:
    await get_driver().verify_connectivity()


NODE_EMBEDDING_INDEX = "node_embedding_index"


async def ensure_vector_index() -> None:
    """Idempotent: creates the vector index on :GraphNode(embedding) if it
    doesn't exist yet. Requires Neo4j 5.13+ (works on Community Edition)."""
    async with get_driver().session() as session:
        await session.run(
            f"""
            CREATE VECTOR INDEX {NODE_EMBEDDING_INDEX} IF NOT EXISTS
            FOR (n:GraphNode) ON (n.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }}}}
            """,
            dimensions=EMBEDDING_DIMENSIONS,
        )


def _node_params(node: GraphNode) -> dict:
    return {
        "id": node.id,
        "reactFlowType": node.type,
        "positionX": node.position.x,
        "positionY": node.position.y,
        "name": node.data.name,
        "entityType": node.data.type,
        "description": node.data.description,
        # Neo4j properties can't hold a list of maps, so the name/value pairs
        # are stored as a JSON string and decoded again on the way out.
        "propertiesJson": json.dumps([p.model_dump() for p in node.data.properties]),
    }


def _edge_params(edge: GraphEdge) -> dict:
    return {
        "id": edge.id,
        "source": edge.source,
        "target": edge.target,
        "relationship": edge.relationship,
        "bendX": edge.bend.x if edge.bend else None,
        "bendY": edge.bend.y if edge.bend else None,
        "sourceHandle": edge.sourceHandle,
        "targetHandle": edge.targetHandle,
    }


async def _save_graph_tx(
    tx, name: str, new_id: str, now: str, nodes: list[dict], edges: list[dict]
) -> str:
    result = await tx.run(
        """
        MERGE (g:SavedGraph {name: $name})
        ON CREATE SET g.id = $newId, g.createdAt = $now
        SET g.updatedAt = $now, g.nodeCount = $nodeCount, g.edgeCount = $edgeCount
        RETURN g.id AS id
        """,
        name=name,
        newId=new_id,
        now=now,
        nodeCount=len(nodes),
        edgeCount=len(edges),
    )
    graph_id = (await result.single())["id"]

    # Drop nodes no longer in the graph; keep the rest upserted via MERGE (not
    # recreated), so properties this doesn't set — like a stored embedding —
    # survive a re-save.
    await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})-[:HAS_NODE]->(old:GraphNode)
        WHERE NOT old.id IN $keepIds
        DETACH DELETE old
        """,
        graphId=graph_id,
        keepIds=[node["id"] for node in nodes],
    )
    await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})
        UNWIND $nodes AS node
        MERGE (n:GraphNode {id: node.id})
        SET n.reactFlowType = node.reactFlowType,
            n.positionX = node.positionX,
            n.positionY = node.positionY,
            n.name = node.name,
            n.entityType = node.entityType,
            n.description = node.description,
            n.propertiesJson = node.propertiesJson
        MERGE (g)-[:HAS_NODE]->(n)
        """,
        graphId=graph_id,
        nodes=nodes,
    )

    # Edges carry nothing worth preserving, so just replace them outright.
    await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})-[:HAS_NODE]->(:GraphNode)
              -[r:RELATES_TO]->(:GraphNode)<-[:HAS_NODE]-(g)
        DELETE r
        """,
        graphId=graph_id,
    )
    await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})
        UNWIND $edges AS edge
        MATCH (g)-[:HAS_NODE]->(source:GraphNode {id: edge.source})
        MATCH (g)-[:HAS_NODE]->(target:GraphNode {id: edge.target})
        CREATE (source)-[r:RELATES_TO {id: edge.id}]->(target)
        SET r.relationship = edge.relationship,
            r.bendX = edge.bendX,
            r.bendY = edge.bendY,
            r.sourceHandle = edge.sourceHandle,
            r.targetHandle = edge.targetHandle
        """,
        graphId=graph_id,
        edges=edges,
    )

    return graph_id


async def save_graph(request: SaveGraphRequest) -> SavedGraphSummary:
    node_params = [_node_params(node) for node in request.nodes]
    edge_params = [_edge_params(edge) for edge in request.edges]
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with get_driver().session() as session:
        graph_id = await session.execute_write(
            _save_graph_tx, request.name, new_id, now, node_params, edge_params
        )

    return SavedGraphSummary(
        id=graph_id,
        name=request.name,
        updatedAt=now,
        nodes=len(request.nodes),
        edges=len(request.edges),
    )


async def _list_graphs_tx(tx) -> list[SavedGraphSummary]:
    records = await tx.run(
        """
        MATCH (g:SavedGraph)
        RETURN g.id AS id, g.name AS name, g.updatedAt AS updatedAt,
               g.nodeCount AS nodeCount, g.edgeCount AS edgeCount
        ORDER BY g.updatedAt DESC
        """
    )
    return [
        SavedGraphSummary(
            id=record["id"],
            name=record["name"],
            updatedAt=record["updatedAt"],
            nodes=record["nodeCount"] or 0,
            edges=record["edgeCount"] or 0,
        )
        async for record in records
    ]


async def list_graphs() -> list[SavedGraphSummary]:
    async with get_driver().session() as session:
        return await session.execute_read(_list_graphs_tx)


async def _has_any_saved_graph_tx(tx) -> bool:
    result = await tx.run("MATCH (g:SavedGraph) RETURN g.id AS id LIMIT 1")
    return await result.single() is not None


async def has_any_saved_graph() -> bool:
    async with get_driver().session() as session:
        return await session.execute_read(_has_any_saved_graph_tx)


async def _get_graph_tx(tx, graph_id: str) -> NamedGraphPayload | None:
    header = await (
        await tx.run(
            "MATCH (g:SavedGraph {id: $graphId}) RETURN g.name AS name, g.text AS text",
            graphId=graph_id,
        )
    ).single()
    if header is None:
        return None

    node_records = await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})-[:HAS_NODE]->(n:GraphNode)
        RETURN n.id AS id,
               n.reactFlowType AS reactFlowType,
               n.positionX AS positionX,
               n.positionY AS positionY,
               n.name AS name,
               n.entityType AS entityType,
               n.description AS description,
               n.propertiesJson AS propertiesJson,
               size(n.embedding) AS embeddingDimensions
        """,
        graphId=graph_id,
    )
    nodes = [
        GraphNode(
            id=record["id"],
            type=record["reactFlowType"],
            position=Position(x=record["positionX"], y=record["positionY"]),
            data=GraphNodeData(
                name=record["name"],
                type=record["entityType"],
                description=record["description"],
                properties=[
                    NodeProperty(**item)
                    for item in json.loads(record["propertiesJson"] or "[]")
                ],
            ),
            embeddingDimensions=record["embeddingDimensions"],
        )
        async for record in node_records
    ]

    edge_records = await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})-[:HAS_NODE]->(source:GraphNode)
        MATCH (source)-[r:RELATES_TO]->(target:GraphNode)<-[:HAS_NODE]-(g)
        RETURN r.id AS id,
               source.id AS source,
               target.id AS target,
               r.relationship AS relationship,
               r.bendX AS bendX,
               r.bendY AS bendY,
               r.sourceHandle AS sourceHandle,
               r.targetHandle AS targetHandle
        """,
        graphId=graph_id,
    )
    edges = [
        GraphEdge(
            id=record["id"],
            source=record["source"],
            target=record["target"],
            relationship=record["relationship"] or "",
            bend=(
                Position(x=record["bendX"], y=record["bendY"])
                if record["bendX"] is not None and record["bendY"] is not None
                else None
            ),
            sourceHandle=record["sourceHandle"],
            targetHandle=record["targetHandle"],
        )
        async for record in edge_records
    ]

    return NamedGraphPayload(
        id=graph_id, name=header["name"], text=header["text"], nodes=nodes, edges=edges
    )


async def get_graph(graph_id: str) -> NamedGraphPayload | None:
    async with get_driver().session() as session:
        return await session.execute_read(_get_graph_tx, graph_id)


async def _save_graph_text_tx(tx, graph_id: str, text: str) -> bool:
    result = await tx.run(
        "MATCH (g:SavedGraph {id: $graphId}) SET g.text = $text RETURN g.id AS id",
        graphId=graph_id,
        text=text,
    )
    return await result.single() is not None


async def save_graph_text(graph_id: str, text: str) -> bool:
    """Returns False if the graph id doesn't exist."""
    async with get_driver().session() as session:
        return await session.execute_write(_save_graph_text_tx, graph_id, text)


async def _save_node_embeddings_tx(
    tx, graph_id: str, pairs: list[dict]
) -> bool:
    exists = await (
        await tx.run(
            "MATCH (g:SavedGraph {id: $graphId}) RETURN g.id AS id", graphId=graph_id
        )
    ).single()
    if exists is None:
        return False

    # Stores both the vector and the text it was computed from.
    await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})
        UNWIND $pairs AS pair
        MATCH (g)-[:HAS_NODE]->(n:GraphNode {id: pair.id})
        SET n.embedding = pair.embedding,
            n.embeddingText = pair.text
        """,
        graphId=graph_id,
        pairs=pairs,
    )
    return True


async def save_node_embeddings(
    graph_id: str,
    node_ids: list[str],
    texts: list[str],
    embeddings: list[list[float]],
) -> bool:
    """Returns False if the graph id doesn't exist. Stale node ids are
    silently skipped rather than treated as an error."""
    pairs = [
        {"id": node_id, "text": text, "embedding": embedding}
        for node_id, text, embedding in zip(node_ids, texts, embeddings)
    ]
    async with get_driver().session() as session:
        return await session.execute_write(
            _save_node_embeddings_tx, graph_id, pairs
        )


async def _search_graph_nodes_tx(
    tx, graph_id: str, query_embedding: list[float], limit: int
) -> list[SearchResultNode] | None:
    exists = await (
        await tx.run(
            "MATCH (g:SavedGraph {id: $graphId}) RETURN g.id AS id", graphId=graph_id
        )
    ).single()
    if exists is None:
        return None

    # The index spans every graph, so over-fetch then filter to this one.
    overfetch = max(limit * 10, 50)
    records = await tx.run(
        """
        CALL db.index.vector.queryNodes($indexName, $overfetch, $queryEmbedding)
        YIELD node, score
        MATCH (g:SavedGraph {id: $graphId})-[:HAS_NODE]->(node)
        RETURN node.id AS id,
               node.name AS name,
               node.entityType AS type,
               node.description AS description,
               node.propertiesJson AS propertiesJson,
               node.embeddingText AS embeddingText,
               score
        ORDER BY score DESC
        LIMIT $limit
        """,
        indexName=NODE_EMBEDDING_INDEX,
        overfetch=overfetch,
        queryEmbedding=query_embedding,
        graphId=graph_id,
        limit=limit,
    )
    return [
        SearchResultNode(
            id=record["id"],
            name=record["name"],
            type=record["type"],
            description=record["description"],
            properties=[
                NodeProperty(**item)
                for item in json.loads(record["propertiesJson"] or "[]")
            ],
            score=record["score"],
            embeddingText=record["embeddingText"],
        )
        async for record in records
    ]


async def search_graph_nodes(
    graph_id: str, query_embedding: list[float], limit: int = 5
) -> list[SearchResultNode] | None:
    """Returns None if the graph id doesn't exist, so the caller can 404."""
    async with get_driver().session() as session:
        return await session.execute_read(
            _search_graph_nodes_tx, graph_id, query_embedding, limit
        )


async def _get_node_relationships_tx(
    tx, graph_id: str, node_ids: list[str]
) -> list[dict]:
    records = await tx.run(
        """
        MATCH (g:SavedGraph {id: $graphId})
        MATCH (g)-[:HAS_NODE]->(a:GraphNode)-[r:RELATES_TO]->(b:GraphNode)<-[:HAS_NODE]-(g)
        WHERE a.id IN $nodeIds OR b.id IN $nodeIds
        RETURN a.id AS fromId, a.name AS fromName,
               r.relationship AS relationship,
               b.id AS toId, b.name AS toName
        """,
        graphId=graph_id,
        nodeIds=node_ids,
    )
    return [
        {
            "fromId": record["fromId"],
            "fromName": record["fromName"],
            "relationship": record["relationship"],
            "toId": record["toId"],
            "toName": record["toName"],
        }
        async for record in records
    ]


async def get_node_relationships(graph_id: str, node_ids: list[str]) -> list[dict]:
    """Every edge touching any of `node_ids`, read fresh from the graph."""
    if not node_ids:
        return []
    async with get_driver().session() as session:
        return await session.execute_read(
            _get_node_relationships_tx, graph_id, node_ids
        )
