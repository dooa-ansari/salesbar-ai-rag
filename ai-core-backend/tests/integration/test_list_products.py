import pytest

from ai_core_backend.catalog import build_graph, load_catalog, load_rows
from ai_core_backend.seed_data import DEFAULT_CATALOG

pytestmark = pytest.mark.anyio

GRAPH_PREFIX = "itest-"


async def test_list_products_returns_every_seeded_product_with_its_edges(neo4j):
    catalog = load_catalog(DEFAULT_CATALOG)
    request = build_graph(catalog, load_rows(catalog))
    request.name = f"{GRAPH_PREFIX}products"
    saved = await neo4j.save_graph(request)

    products = await neo4j.list_products(saved.id)

    assert len(products) == 56
    tee = next(product for product in products if product.id == "product-ts01")
    keys = {attribute.key for attribute in tee.attributes}
    assert {"BELONGS_TO", "IS_MADE_BY", "COMES_IN", "AVAILABLE_IN"} <= keys
    sizes = {a.name: a.properties[0].value for a in tee.attributes if a.key == "AVAILABLE_IN"}
    assert sizes == {"S": 6, "M": 8, "L": 5, "XL": 3}


async def test_list_products_unknown_catalog_returns_none(neo4j):
    assert await neo4j.list_products("does-not-exist") is None


async def test_product_matches_reports_linked_nodes_stock_and_price(neo4j):
    catalog = load_catalog(DEFAULT_CATALOG)
    request = build_graph(catalog, load_rows(catalog))
    request.name = f"{GRAPH_PREFIX}matches"
    saved = await neo4j.save_graph(request)
    vocabulary = {(v["type"], v["name"]): v["id"] for v in await neo4j.catalog_vocabulary(saved.id)}
    blue, small = vocabulary[("Colour", "Blue")], vocabulary[("Size", "S")]

    rows = {row["id"]: row for row in await neo4j.product_matches(saved.id, [blue, small], ["MADE_OF"], "price")}

    tee = rows["product-ts07"]
    assert set(tee["hits"]) == {blue, small}
    assert tee["hits"][small][0].value == 4
    assert tee["price"] == 27.0
    assert tee["keys"] == {"MADE_OF"}
    assert rows["product-ja14"]["keys"] == set()
    assert ("Product", "Recycled Run Tee") not in vocabulary
