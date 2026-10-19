"""Request/response shapes for the graph API, mirroring the frontend's React
Flow graph shape (see admin-panel/src/graph.ts)."""

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Generous but finite bounds on free-text input: large enough that no
# legitimate graph/query hits them, small enough that one request can't
# stuff megabytes of text into Neo4j or an OpenRouter call.
_SHORT_TEXT = 200
_MEDIUM_TEXT = 2_000
_LONG_TEXT = 1_000_000


class Position(BaseModel):
    x: float
    y: float


PropertyType = Literal["string", "integer", "float"]


def _parse_integer(value: str | int | float) -> int:
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("integer property must be a whole number")
        return int(value)
    if isinstance(value, str):
        return int(value.strip())
    return value


def _parse_float(value: str | int | float) -> float:
    number = float(value.strip() if isinstance(value, str) else value)
    if not math.isfinite(number):
        raise ValueError("float property must be a finite number")
    return number


class NodeProperty(BaseModel):
    name: str = Field(max_length=_SHORT_TEXT)
    type: PropertyType = "string"
    value: str | int | float

    @model_validator(mode="after")
    def _match_value_to_type(self):
        if self.type == "integer":
            self.value = _parse_integer(self.value)
        elif self.type == "float":
            self.value = _parse_float(self.value)
        else:
            self.value = str(self.value)
            if len(self.value) > _MEDIUM_TEXT:
                raise ValueError(f"string property is longer than {_MEDIUM_TEXT} characters")
        return self


class GraphNodeData(BaseModel):
    name: str = Field(max_length=_SHORT_TEXT)
    type: str = Field(max_length=_SHORT_TEXT)
    description: str | None = Field(default=None, max_length=_MEDIUM_TEXT)
    properties: list[NodeProperty] = Field(default=[], max_length=200)


class GraphNode(BaseModel):
    id: str = Field(max_length=_SHORT_TEXT)
    type: str = Field(max_length=_SHORT_TEXT)
    position: Position
    data: GraphNodeData
    # Length of the stored embedding vector, not the vector itself. Response-only.
    embeddingDimensions: int | None = None
    catalogId: str | None = None


class GraphEdge(BaseModel):
    id: str = Field(max_length=_SHORT_TEXT)
    source: str = Field(max_length=_SHORT_TEXT)
    target: str = Field(max_length=_SHORT_TEXT)
    relationship: str = Field(default="", max_length=_SHORT_TEXT)
    key: str | None = Field(default=None, max_length=_SHORT_TEXT)
    properties: list[NodeProperty] = Field(default=[], max_length=50)
    bend: Position | None = None
    # Which node handle the edge is attached to (e.g. "+" vs the "↑" reverse-link).
    sourceHandle: str | None = Field(default=None, max_length=_SHORT_TEXT)
    targetHandle: str | None = Field(default=None, max_length=_SHORT_TEXT)


class GraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(max_length=5_000)
    edges: list[GraphEdge] = Field(max_length=20_000)


class SaveGraphRequest(GraphPayload):
    name: str = Field(max_length=_SHORT_TEXT)


class NamedGraphPayload(GraphPayload):
    id: str
    name: str
    # Humanized whole-graph description for viewing (separate from per-node
    # embedding text). None until "Generate text" has been used.
    text: str | None = None


class SaveGraphResponse(BaseModel):
    message: str
    status: str
    id: str
    name: str
    nodes: int
    edges: int


class SavedGraphSummary(BaseModel):
    id: str
    name: str
    updatedAt: str
    nodes: int
    edges: int


class SaveTextRequest(BaseModel):
    text: str = Field(max_length=_LONG_TEXT)


class SaveTextResponse(BaseModel):
    status: str
    message: str


class NodeText(BaseModel):
    """One node's embedding input: its id and its humanized text."""

    id: str = Field(max_length=_SHORT_TEXT)
    # The embedding model's own input limit is ~512 tokens (see
    # openrouter_client.EMBEDDING_MODEL) — this is a generous superset of that.
    text: str = Field(max_length=_MEDIUM_TEXT)


class GenerateEmbeddingsRequest(BaseModel):
    nodes: list[NodeText] = Field(max_length=5_000)


class GenerateEmbeddingsResponse(BaseModel):
    status: str
    message: str
    count: int
    dimensions: int


class SearchRequest(BaseModel):
    query: str = Field(max_length=_MEDIUM_TEXT)
    # Bounded so a client can't force an extremely expensive Neo4j vector
    # overfetch (search_graph_nodes multiplies this by 10) or a negative
    # Cypher LIMIT, which Neo4j rejects with an unhandled error.
    limit: int = Field(default=5, ge=1, le=50)
    # Restricts matches to one node type, e.g. "Product" for a storefront.
    nodeType: str | None = Field(default=None, max_length=_SHORT_TEXT)


class RelationshipFact(BaseModel):
    """One edge touching a matched node, read live from Neo4j at search time."""

    relationship: str
    direction: Literal["outgoing", "incoming"]
    otherId: str
    otherName: str
    properties: list[NodeProperty] = []


class SearchResultNode(BaseModel):
    id: str
    catalogId: str | None = None
    name: str
    type: str
    description: str | None = None
    properties: list[NodeProperty] = []
    # Cosine similarity between the query and this node, 1.0 = identical.
    score: float
    # The text actually embedded for this node (attributes only).
    embeddingText: str | None = None
    # This node's edges, fetched fresh from Neo4j for this search.
    relationships: list[RelationshipFact] = []


class ProductAttribute(BaseModel):
    """One outgoing edge of a product, e.g. BELONGS_TO -> Jackets."""

    key: str | None = None
    relationship: str
    name: str
    properties: list[NodeProperty] = []


class ProductSummary(BaseModel):
    id: str
    catalogId: str | None = None
    name: str
    description: str | None = None
    properties: list[NodeProperty] = []
    attributes: list[ProductAttribute] = []


class ShopSearchRequest(BaseModel):
    query: str = Field(max_length=_MEDIUM_TEXT)


class ShopConstraint(BaseModel):
    """One thing the shopper asked for, as the parser understood it."""

    label: str
    kind: Literal["required", "safety", "near", "soft"]


class ShopMatch(BaseModel):
    productId: str
    match: Literal["exact", "near", "alternative", "related", "ruled-out"]
    reasons: list[str] = []
    score: float = 0.0


class ShopSearchResponse(BaseModel):
    query: str
    constraints: list[ShopConstraint] = []
    message: str
    results: list[ShopMatch] = []
    ruledOut: list[ShopMatch] = []


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultNode]
    # None if there were no results, or the LLM call failed.
    answer: str | None = None
