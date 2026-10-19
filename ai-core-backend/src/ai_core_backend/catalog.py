import csv
import re
from pathlib import Path

import yaml

from ai_core_backend.schemas import (
    GraphEdge,
    GraphNode,
    GraphNodeData,
    NodeProperty,
    Position,
    SaveGraphRequest,
)

ROLES = {"product", "brand", "category", "attribute", "restriction"}
COLUMN_SPACING = 300
ROW_SPACING = 220
PRODUCTS_PER_ROW = 8


def load_catalog(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        catalog = yaml.safe_load(handle)
    _validate(catalog)
    catalog["_directory"] = path.resolve().parent
    return catalog


def _validate(catalog: dict) -> None:
    node_types = catalog.get("node_types") or {}
    unknown_roles = {t: n["role"] for t, n in node_types.items() if n.get("role") not in ROLES}
    if unknown_roles:
        raise ValueError(f"node_types with an invalid role: {unknown_roles}")
    products = [t for t, n in node_types.items() if n["role"] == "product"]
    if len(products) != 1:
        raise ValueError(f"exactly one product node type is required, found {products}")
    if catalog["product"]["node_type"] != products[0]:
        raise ValueError("product.node_type must be the node type with the product role")

    relationships = catalog.get("relationships") or {}
    for key, relationship in relationships.items():
        for end in ("from", "to"):
            if relationship[end] not in node_types:
                raise ValueError(f"relationship {key} references unknown node type {relationship[end]}")
        if "label" not in relationship:
            raise ValueError(f"relationship {key} has no label")

    for column, spec in (catalog.get("columns") or {}).items():
        if spec["node_type"] not in node_types:
            raise ValueError(f"column {column} references unknown node type {spec['node_type']}")
        if spec["relationship"] not in relationships:
            raise ValueError(f"column {column} references unknown relationship {spec['relationship']}")

    constraints = catalog.get("constraints") or {}
    for kind in ("safety", "near", "soft"):
        for node_type in (constraints.get(kind) or {}).get("node_types", []):
            if node_type not in node_types:
                raise ValueError(f"{kind} constraint references unknown node type {node_type}")

    for entry in catalog.get("synonyms") or []:
        target = entry.get("require") or entry.get("exclude")
        if not entry.get("phrases") or not target:
            raise ValueError(f"synonym entry needs phrases and a require/exclude target: {entry}")
        if target["node_type"] not in node_types:
            raise ValueError(f"synonym references unknown node type {target['node_type']}")


def load_rows(catalog: dict) -> list[dict]:
    source = (catalog["_directory"] / catalog["source"]["file"]).resolve()
    with source.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def source_exists(catalog: dict) -> bool:
    return (catalog["_directory"] / catalog["source"]["file"]).is_file()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _display(value: str) -> str:
    label = value.replace("_", " ")
    return label.title() if label == label.lower() else label


def _split(value: str, separator: str | None) -> list[str]:
    if not value:
        return []
    if separator is None:
        return [value]
    return [item for item in value.split(separator) if item]


def _counts(value: str, separator: str | None) -> list[tuple[str, int]]:
    pairs = [item.split(":", 1) for item in _split(value, separator)]
    return [(label, int(count)) for label, count in pairs]


def _entities(row: dict, column: str, spec: dict) -> list[str]:
    value = row[column]
    separator = spec.get("separator")
    if spec.get("counts"):
        return [label for label, _ in _counts(value, separator)]
    suffix = spec.get("strip_suffix")
    names = _split(value, separator)
    if suffix:
        return [name.removesuffix(suffix) for name in names]
    return names


def _product_properties(catalog: dict, row: dict) -> list[NodeProperty]:
    properties = []
    for spec in catalog["product"]["properties"]:
        value = row[spec["column"]]
        if value != "":
            properties.append(
                NodeProperty(name=spec["name"], type=spec.get("type", "string"), value=value)
            )
    for column, spec in catalog["columns"].items():
        if spec.get("as_property") and not spec.get("counts"):
            values = [_display(entity) for entity in _entities(row, column, spec)]
            if values:
                properties.append(
                    NodeProperty(name=spec["as_property"], value=", ".join(values))
                )
    return properties


def _edge_properties(row: dict, column: str, spec: dict, entity: str) -> list[NodeProperty]:
    if not spec.get("counts") or not spec.get("edge_property"):
        return []
    counts = dict(_counts(row[column], spec.get("separator")))
    return [NodeProperty(name=spec["edge_property"], type="integer", value=counts[entity])]


def _node(node_id, name, node_type, x, y, description=None, properties=None) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="graph",
        position=Position(x=x, y=y),
        data=GraphNodeData(
            name=name,
            type=node_type,
            description=description,
            properties=properties or [],
        ),
    )


def build_graph(catalog: dict, rows: list[dict]) -> SaveGraphRequest:
    product_spec = catalog["product"]
    product_type = product_spec["node_type"]
    columns = catalog["columns"]
    relationships = catalog["relationships"]

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    entity_ids: dict[tuple[str, str], str] = {}

    for index, row in enumerate(rows):
        nodes.append(
            _node(
                f"{_slug(product_type)}-{_slug(row[product_spec['id_column']])}",
                row[product_spec["name_column"]],
                product_type,
                (index % PRODUCTS_PER_ROW) * COLUMN_SPACING,
                (index // PRODUCTS_PER_ROW + 1) * ROW_SPACING,
                description=row[product_spec["description_column"]] or None,
                properties=_product_properties(catalog, row),
            )
        )

    for column_index, (column, spec) in enumerate(columns.items()):
        names = sorted({name for row in rows for name in _entities(row, column, spec)})
        for position, name in enumerate(names):
            node_id = f"{_slug(spec['node_type'])}-{_slug(name)}"
            if (spec["node_type"], name) in entity_ids:
                continue
            entity_ids[(spec["node_type"], name)] = node_id
            nodes.append(
                _node(
                    node_id,
                    _display(name),
                    spec["node_type"],
                    position * COLUMN_SPACING,
                    -(len(columns) - column_index) * ROW_SPACING,
                )
            )

    for row in rows:
        product_id = f"{_slug(product_type)}-{_slug(row[product_spec['id_column']])}"
        for column, spec in columns.items():
            relationship = relationships[spec["relationship"]]
            for name in _entities(row, column, spec):
                edges.append(
                    GraphEdge(
                        id=f"edge-{len(edges) + 1}",
                        source=product_id,
                        target=entity_ids[(spec["node_type"], name)],
                        relationship=relationship["label"],
                        key=spec["relationship"],
                        properties=_edge_properties(row, column, spec, name),
                    )
                )

    return SaveGraphRequest(name=catalog["name"], nodes=nodes, edges=edges)
