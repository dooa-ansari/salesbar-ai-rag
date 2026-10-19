import logging
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)

from ai_core_backend import neo4j_client, openrouter_client, shop_search
from ai_core_backend.schemas import (
    GenerateEmbeddingsRequest,
    GenerateEmbeddingsResponse,
    NamedGraphPayload,
    ProductSummary,
    RelationshipFact,
    SaveGraphRequest,
    SaveGraphResponse,
    SavedGraphSummary,
    SaveTextRequest,
    SaveTextResponse,
    SearchRequest,
    SearchResponse,
    SearchResultNode,
    ShopSearchRequest,
    ShopSearchResponse,
)
from ai_core_backend.seed_data import SEED_CATALOG, SEED_GRAPHS


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort: don't crash startup if Neo4j isn't reachable yet.
    try:
        await neo4j_client.ensure_vector_index()
    except Exception:
        logger.warning("Could not ensure the vector index on startup", exc_info=True)

    try:
        if not await neo4j_client.has_any_saved_graph():
            for graph in SEED_GRAPHS:
                await neo4j_client.save_graph(graph)
            logger.info("Seeded %d sample graph(s)", len(SEED_GRAPHS))
    except Exception:
        logger.warning("Could not seed sample data", exc_info=True)

    yield
    await neo4j_client.close_driver()


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/health")
async def health_check():
    try:
        await neo4j_client.verify_connectivity()
    except Exception as error:
        raise HTTPException(
            status_code=503, detail=f"Neo4j unavailable: {error}"
        ) from error
    return {"status": "ok", "neo4j": "connected"}


@app.post("/graphs", response_model=SaveGraphResponse)
async def save_graph(payload: SaveGraphRequest):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Graph name is required")
    summary = await neo4j_client.save_graph(payload)
    return SaveGraphResponse(
        message="Graph saved successfully",
        status="success",
        id=summary.id,
        name=summary.name,
        nodes=summary.nodes,
        edges=summary.edges,
    )


@app.get("/graphs", response_model=list[SavedGraphSummary])
async def list_graphs():
    return await neo4j_client.list_graphs()


@app.get("/graphs/{graph_id}", response_model=NamedGraphPayload)
async def get_graph(graph_id: str):
    graph = await neo4j_client.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph


@app.get("/graphs/{graph_id}/products", response_model=list[ProductSummary])
async def list_products(graph_id: str):
    products = await neo4j_client.list_products(graph_id)
    if products is None:
        raise HTTPException(status_code=404, detail="Graph not found")
    return products


def _shop_config(graph_name: str | None) -> shop_search.ShopConfig:
    if SEED_CATALOG and SEED_CATALOG.get("name") == graph_name:
        return shop_search.config_from_catalog(SEED_CATALOG)
    return shop_search.ShopConfig()


@app.post("/graphs/{graph_id}/shop-search", response_model=ShopSearchResponse)
async def shop_search_graph(graph_id: str, payload: ShopSearchRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query is required")

    graphs = await neo4j_client.list_graphs()
    name = next((graph.name for graph in graphs if graph.id == graph_id), None)
    if name is None:
        raise HTTPException(status_code=404, detail="Graph not found")

    try:
        result = await shop_search.search(graph_id, query, _shop_config(name))
    except shop_search.ShopSearchError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return ShopSearchResponse(
        query=query,
        constraints=result.constraints,
        message=result.message,
        results=result.results,
        ruledOut=result.ruled_out,
    )


@app.put("/graphs/{graph_id}/text", response_model=SaveTextResponse)
async def save_graph_text(graph_id: str, payload: SaveTextRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Text is required")
    found = await neo4j_client.save_graph_text(graph_id, payload.text)
    if not found:
        raise HTTPException(status_code=404, detail="Graph not found")
    return SaveTextResponse(status="success", message="Text saved")


@app.post("/graphs/{graph_id}/embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(graph_id: str, payload: GenerateEmbeddingsRequest):
    if not payload.nodes:
        raise HTTPException(status_code=422, detail="No nodes to embed")

    # One batched request for every node's text, not one request per node.
    texts = [node.text for node in payload.nodes]
    try:
        embeddings = await openrouter_client.generate_embeddings(texts)
    except openrouter_client.OpenRouterError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    node_ids = [node.id for node in payload.nodes]
    found = await neo4j_client.save_node_embeddings(
        graph_id, node_ids, texts, embeddings
    )
    if not found:
        raise HTTPException(status_code=404, detail="Graph not found")

    return GenerateEmbeddingsResponse(
        status="success",
        message=f"Generated embeddings for {len(embeddings)} node(s)",
        count=len(embeddings),
        dimensions=len(embeddings[0]),
    )


async def _attach_relationships(
    graph_id: str, results: list[SearchResultNode]
) -> None:
    """Hybrid retrieval: fills in each matched node's relationships with a
    live Neo4j traversal, not from the embedding."""
    rows = await neo4j_client.get_node_relationships(
        graph_id, [result.id for result in results]
    )
    by_node: dict[str, list[RelationshipFact]] = defaultdict(list)
    for row in rows:
        by_node[row["fromId"]].append(
            RelationshipFact(
                relationship=row["relationship"],
                direction="outgoing",
                otherId=row["toId"],
                otherName=row["toName"],
                properties=row.get("properties", []),
            )
        )
        by_node[row["toId"]].append(
            RelationshipFact(
                relationship=row["relationship"],
                direction="incoming",
                otherId=row["fromId"],
                otherName=row["fromName"],
                properties=row.get("properties", []),
            )
        )
    for result in results:
        result.relationships = by_node.get(result.id, [])


def _format_context(results: list[SearchResultNode]) -> str:
    lines = []
    for result in results:
        if result.embeddingText:
            lines.append(f"- {result.embeddingText}")
        else:
            line = f"- {result.name} ({result.type})"
            if result.description:
                line += f": {result.description}"
            if result.properties:
                props = ", ".join(f"{p.name}={p.value}" for p in result.properties)
                line += f" [{props}]"
            lines.append(line)
        for rel in result.relationships:
            detail = ", ".join(f"{p.name}={p.value}" for p in rel.properties)
            suffix = f" ({detail})" if detail else ""
            if rel.direction == "outgoing":
                lines.append(f"  {result.name} {rel.relationship} {rel.otherName}{suffix}.")
            else:
                lines.append(f"  {rel.otherName} {rel.relationship} {result.name}{suffix}.")
    return "\n".join(lines)


@app.post("/graphs/{graph_id}/search", response_model=SearchResponse)
async def search_graph(graph_id: str, payload: SearchRequest):
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="Query is required")

    try:
        (query_embedding,) = await openrouter_client.generate_embeddings(
            [payload.query]
        )
    except openrouter_client.OpenRouterError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    results = await neo4j_client.search_graph_nodes(
        graph_id, query_embedding, payload.limit, payload.nodeType
    )
    if results is None:
        raise HTTPException(status_code=404, detail="Graph not found")

    if results:
        await _attach_relationships(graph_id, results)

    # Synthesis is best-effort — results still come back even if it fails.
    answer = None
    if results:
        try:
            answer = await openrouter_client.generate_answer(
                payload.query, _format_context(results)
            )
        except openrouter_client.OpenRouterError as error:
            logger.warning("Answer synthesis failed: %s", error)

    return SearchResponse(query=payload.query, results=results, answer=answer)
