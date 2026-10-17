import csv
import json
from pathlib import Path

import pytest

from ai_core_backend import neo4j_client
from ai_core_backend.migrate import migrate_numeric_properties
from ai_core_backend.schemas import (
    GraphEdge,
    GraphNode,
    GraphNodeData,
    NodeProperty,
    Position,
    SaveGraphRequest,
)
pytestmark = pytest.mark.anyio

GRAPH_PREFIX = "itest-"

SAMPLE = [
    ("ja-1", "Trail Shell", "Jackets", 89),
    ("ja-2", "Storm Rider", "Jackets", 119.99),
    ("ja-3", "Coast Mac", "Jackets", 120),
    ("ja-4", "Alpine Rain", "Jackets", 121),
    ("ja-5", "Peak Hardshell", "Jackets", 139),
    ("ja-6", "Urban Bomber", "Jackets", 45.5),
    ("ts-1", "Everyday Tee", "T-shirts", 19),
    ("ts-2", "Merino Tee", "T-shirts", 49),
    ("je-1", "Straight Jeans", "Jeans", 59),
]


def _node(node_id, name, kind, properties=None, x=0):
    return GraphNode(
        id=node_id,
        type="graph",
        position=Position(x=x, y=0),
        data=GraphNodeData(name=name, type=kind, properties=properties or []),
    )


def _clothes_graph(name, products):
    categories = sorted({category for _, _, category, _ in products})
    nodes = [_node(f"cat-{c}", c, "Category") for c in categories]
    edges = []
    for product_id, product_name, category, price in products:
        properties = [] if price is None else [NodeProperty(name="price", type="float", value=price)]
        nodes.append(_node(product_id, product_name, "Product", properties))
        edges.append(
            GraphEdge(
                id=f"edge-{product_id}",
                source=product_id,
                target=f"cat-{category}",
                relationship="belongs to",
                key="BELONGS_TO",
            )
        )
    return SaveGraphRequest(name=f"{GRAPH_PREFIX}{name}", nodes=nodes, edges=edges)


async def test_jackets_under_120_uses_a_numeric_comparison(neo4j):
    summary = await neo4j.save_graph(_clothes_graph("sample", SAMPLE))

    results = await neo4j.find_products(summary.id, category="jackets", max_price=120)

    assert [r["name"] for r in results] == ["Urban Bomber", "Trail Shell", "Storm Rider"]
    assert all(isinstance(r["price"], float) for r in results)
    assert all(r["price"] < 120 for r in results)
    assert {r["category"] for r in results} == {"Jackets"}


async def test_boundary_price_is_excluded_and_other_categories_are_not_returned(neo4j):
    summary = await neo4j.save_graph(_clothes_graph("boundary", SAMPLE))

    names = {r["name"] for r in await neo4j.find_products(summary.id, category="Jackets", max_price=120)}

    assert "Coast Mac" not in names
    assert "Alpine Rain" not in names
    assert "Everyday Tee" not in names


async def test_numbers_compare_as_numbers_not_as_text(neo4j):
    summary = await neo4j.save_graph(
        _clothes_graph("ordering", [("a", "Nine", "Jackets", 9), ("b", "Hundred", "Jackets", 100)])
    )

    results = await neo4j.find_products(summary.id, category="Jackets", max_price=50)

    assert [r["name"] for r in results] == ["Nine"]


async def test_sort_by_price_ascending_and_descending(neo4j):
    summary = await neo4j.save_graph(_clothes_graph("sorting", SAMPLE))

    ascending = await neo4j.find_products(summary.id, category="Jackets", sort="price_asc")
    descending = await neo4j.find_products(summary.id, category="Jackets", sort="price_desc")

    prices = [r["price"] for r in ascending]
    assert prices == sorted(prices)
    assert prices == [45.5, 89, 119.99, 120, 121, 139]
    assert [r["price"] for r in descending] == sorted(prices, reverse=True)


async def test_sort_applies_across_all_categories_when_no_category_given(neo4j):
    summary = await neo4j.save_graph(_clothes_graph("all-sorted", SAMPLE))

    prices = [r["price"] for r in await neo4j.find_products(summary.id)]

    assert prices == sorted(prices)
    assert len(prices) == len(SAMPLE)


async def test_products_without_a_price_never_match_a_price_limit(neo4j):
    products = [("x", "No Price Jacket", "Jackets", None), ("y", "Cheap Jacket", "Jackets", 10)]
    summary = await neo4j.save_graph(_clothes_graph("no-price", products))

    results = await neo4j.find_products(summary.id, category="Jackets", max_price=120)

    assert [r["name"] for r in results] == ["Cheap Jacket"]


async def test_unknown_sort_is_rejected(neo4j):
    with pytest.raises(ValueError):
        await neo4j.find_products("any", sort="name_asc")


async def test_search_is_scoped_to_its_own_catalog(neo4j):
    first = await neo4j.save_graph(_clothes_graph("scope-a", SAMPLE))
    second = await neo4j.save_graph(_clothes_graph("scope-b", [("ja-1", "Other Jacket", "Jackets", 10)]))

    a = await neo4j.find_products(first.id, category="Jackets", max_price=120)
    b = await neo4j.find_products(second.id, category="Jackets", max_price=120)

    assert "Other Jacket" not in {r["name"] for r in a}
    assert [r["name"] for r in b] == ["Other Jacket"]


async def test_resaving_without_a_price_clears_the_numeric_value(neo4j):
    with_price = _clothes_graph("resave", [("p", "Jacket", "Jackets", 50)])
    summary = await neo4j.save_graph(with_price)
    assert [r["name"] for r in await neo4j.find_products(summary.id, max_price=120)] == ["Jacket"]

    await neo4j.save_graph(_clothes_graph("resave", [("p", "Jacket", "Jackets", None)]))

    assert await neo4j.find_products(summary.id, max_price=120) == []


async def _create_legacy_graph(neo4j, name, products):
    async with neo4j.get_driver().session() as session:
        await session.run(
            "CREATE (g:SavedGraph {id: $id, name: $name, updatedAt: 'x', nodeCount: 0, edgeCount: 0})",
            id=name,
            name=f"{GRAPH_PREFIX}{name}",
        )
        await session.run(
            """
            MATCH (g:SavedGraph {id: $id})
            CREATE (c:GraphNode {catalogId: $id, id: 'cat-jackets', name: 'Jackets', entityType: 'Category',
                                 propertiesJson: '[]'})
            CREATE (g)-[:HAS_NODE]->(c)
            """,
            id=name,
        )
        for node_id, product_name, raw_price in products:
            await session.run(
                """
                MATCH (g:SavedGraph {id: $id})
                MATCH (c:GraphNode {catalogId: $id, id: 'cat-jackets'})
                CREATE (p:GraphNode {catalogId: $id, id: $nodeId, name: $name, entityType: 'Product',
                                     propertiesJson: $json})
                CREATE (g)-[:HAS_NODE]->(p)
                CREATE (p)-[:RELATES_TO {id: $nodeId, relationship: 'belongs to', key: 'BELONGS_TO'}]->(c)
                """,
                id=name,
                nodeId=node_id,
                name=product_name,
                json=json.dumps([{"name": "price", "value": raw_price}]),
            )
    return name


async def test_migration_converts_text_prices_and_reports_the_bad_one(neo4j):
    catalog_id = await _create_legacy_graph(
        neo4j,
        "legacy",
        [
            ("p1", "Plain Text", "19"),
            ("p2", "Dollar Sign", "$24.50"),
            ("p3", "Padded", " 30 "),
            ("p4", "Bad Price", "N/A"),
        ],
    )
    assert await neo4j.find_products(catalog_id, category="Jackets", max_price=120) == []

    report = await migrate_numeric_properties({"price": "float"}, catalog_id=catalog_id)

    assert report.nodes_scanned == 5
    assert report.values_migrated == 3
    assert [(node_id, bad.property, bad.value) for _, node_id, bad in report.bad_values] == [
        ("p4", "price", "N/A")
    ]
    results = await neo4j.find_products(catalog_id, category="Jackets", max_price=120)
    assert [(r["name"], r["price"]) for r in results] == [
        ("Plain Text", 19.0),
        ("Dollar Sign", 24.5),
        ("Padded", 30.0),
    ]

    async with neo4j.get_driver().session() as session:
        record = await (
            await session.run(
                "MATCH (n:GraphNode {catalogId: $c, id: 'p4'}) RETURN n.propertiesJson AS json, n.prop_price AS price",
                c=catalog_id,
            )
        ).single()
    assert record["price"] is None
    assert json.loads(record["json"]) == [{"name": "price", "value": "N/A"}]


async def test_migration_can_run_twice(neo4j):
    catalog_id = await _create_legacy_graph(neo4j, "twice", [("p1", "One", "10"), ("p2", "Two", "oops")])

    first = await migrate_numeric_properties({"price": "float"}, catalog_id=catalog_id)
    second = await migrate_numeric_properties({"price": "float"}, catalog_id=catalog_id)

    assert first.values_migrated == 1
    assert second.values_migrated == 0
    assert len(second.bad_values) == 1
    results = await neo4j.find_products(catalog_id, category="Jackets", max_price=120)
    assert [(r["name"], r["price"]) for r in results] == [("One", 10.0)]


async def test_text_prices_are_no_longer_needed(neo4j):
    request = SaveGraphRequest(
        name=f"{GRAPH_PREFIX}typed",
        nodes=[
            _node("cat-jackets", "Jackets", "Category"),
            _node("p1", "Typed Jacket", "Product", [NodeProperty(name="price", type="float", value="89")]),
        ],
        edges=[
            GraphEdge(id="e1", source="p1", target="cat-jackets", relationship="belongs to", key="BELONGS_TO")
        ],
    )
    summary = await neo4j.save_graph(request)

    results = await neo4j.find_products(summary.id, category="Jackets", max_price=120)

    assert [(r["name"], r["price"]) for r in results] == [("Typed Jacket", 89.0)]
    assert isinstance(results[0]["price"], float)

    async with neo4j.get_driver().session() as session:
        record = await (
            await session.run(
                "MATCH (n:GraphNode {catalogId: $c, id: 'p1'}) RETURN n.propertiesJson AS json, n.prop_price AS price",
                c=summary.id,
            )
        ).single()
    stored = json.loads(record["json"])
    assert stored == [{"name": "price", "type": "float", "value": 89.0}]
    assert record["price"] == 89.0

    query_source = Path(neo4j_client.__file__).read_text(encoding="utf-8")
    find_products_source = query_source[query_source.index("async def _find_products_tx") :]
    assert "toFloat" not in find_products_source
    assert "toInteger" not in find_products_source


async def test_the_seeded_clothes_catalog_answers_jackets_under_120(neo4j):
    from ai_core_backend.catalog import load_catalog, load_rows
    from ai_core_backend.seed_data import CATALOG_PATH, SEED_GRAPHS

    if not SEED_GRAPHS:
        pytest.skip("no seed catalog available")
    rows = load_rows(load_catalog(CATALOG_PATH))
    expected = sorted(
        (float(r["price"]), r["name"]) for r in rows if r["category"] == "Jackets" and float(r["price"]) < 120
    )
    seed = SEED_GRAPHS[0].model_copy(update={"name": f"{GRAPH_PREFIX}seed"})
    summary = await neo4j.save_graph(seed)

    results = await neo4j.find_products(summary.id, category="jackets", max_price=120)

    assert expected
    assert [(r["price"], r["name"]) for r in results] == expected
    names = {r["name"] for r in results}
    assert "Alpine Rain Jacket" in names
    assert "Harbor Rain Jacket" not in names
    assert "Peak Hardshell" not in names
