import csv
import os
import re
from pathlib import Path

from ai_core_backend.schemas import (
    GraphEdge,
    GraphNode,
    GraphNodeData,
    NodeProperty,
    Position,
    SaveGraphRequest,
)

CATALOG_NAME = "Clothes Catalog"
DEFAULT_PRODUCTS_CSV = Path(__file__).resolve().parents[3] / "products.csv"
PRODUCTS_CSV = Path(os.environ.get("SEED_PRODUCTS_CSV", DEFAULT_PRODUCTS_CSV))

COLUMN_SPACING = 300
ROW_SPACING = 220
PRODUCTS_PER_ROW = 8

ATTRIBUTE_KINDS = [
    ("category", "Category", "in category"),
    ("brand", "Brand", "made by"),
    ("materials", "Material", "made of"),
    ("flags", "Feature", "has feature"),
    ("free_from", "Safety Claim", "is"),
]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _label(value: str) -> str:
    return value.replace("_", " ")


def _split(value: str) -> list[str]:
    return [item for item in value.split("|") if item]


def _stock_by_size(value: str) -> list[tuple[str, int]]:
    pairs = [item.split(":", 1) for item in _split(value)]
    return [(size, int(count)) for size, count in pairs]


def _node(node_id: str, name: str, kind: str, x: float, y: float, description=None, properties=None):
    return GraphNode(
        id=node_id,
        type="graph",
        position=Position(x=x, y=y),
        data=GraphNodeData(
            name=name,
            type=kind,
            description=description,
            properties=properties or [],
        ),
    )


def _product_properties(row: dict) -> list[NodeProperty]:
    properties = [
        NodeProperty(name="sku", value=row["id"]),
        NodeProperty(name="price", type="float", value=row["price"]),
        NodeProperty(name="currency", value=row["currency"]),
    ]
    if row["colour"]:
        properties.append(NodeProperty(name="colour", value=row["colour"]))
    for column in ("materials", "flags", "free_from"):
        values = [_label(item) for item in _split(row[column])]
        if values:
            properties.append(NodeProperty(name=column.replace("_", " "), value=", ".join(values)))
    for size, count in _stock_by_size(row["sizes_in_stock"]):
        properties.append(NodeProperty(name=f"stock {size}", type="integer", value=count))
    for column in ("image_url", "product_url"):
        if row[column]:
            properties.append(NodeProperty(name=column.replace("_", " "), value=row[column]))
    return properties


def build_product_graph(rows: list[dict], name: str = CATALOG_NAME) -> SaveGraphRequest:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    attribute_ids: dict[tuple[str, str], str] = {}

    for index, row in enumerate(rows):
        column = index % PRODUCTS_PER_ROW
        line = index // PRODUCTS_PER_ROW
        nodes.append(
            _node(
                f"product-{_slug(row['id'])}",
                row["name"],
                "Product",
                column * COLUMN_SPACING,
                (line + 1) * ROW_SPACING,
                description=row["description"] or None,
                properties=_product_properties(row),
            )
        )

    for kind_index, (column_name, kind, _) in enumerate(ATTRIBUTE_KINDS):
        values = sorted({value for row in rows for value in _split(row[column_name])})
        for position, value in enumerate(values):
            node_id = f"{_slug(column_name)}-{_slug(value)}"
            attribute_ids[(column_name, value)] = node_id
            nodes.append(
                _node(
                    node_id,
                    _label(value).title(),
                    kind,
                    position * COLUMN_SPACING,
                    -(len(ATTRIBUTE_KINDS) - kind_index) * ROW_SPACING,
                )
            )

    for row in rows:
        product_id = f"product-{_slug(row['id'])}"
        for column_name, _, relationship in ATTRIBUTE_KINDS:
            for value in _split(row[column_name]):
                target = attribute_ids[(column_name, value)]
                edges.append(
                    GraphEdge(
                        id=f"edge-{len(edges) + 1}",
                        source=product_id,
                        target=target,
                        relationship=relationship,
                    )
                )

    return SaveGraphRequest(name=name, nodes=nodes, edges=edges)


def load_products_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_seed_graphs() -> list[SaveGraphRequest]:
    if not PRODUCTS_CSV.is_file():
        return []
    return [build_product_graph(load_products_csv(PRODUCTS_CSV))]


SEED_GRAPHS: list[SaveGraphRequest] = _load_seed_graphs()
