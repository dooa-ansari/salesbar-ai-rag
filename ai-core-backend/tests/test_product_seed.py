import csv
import io
from pathlib import Path

import pytest
import yaml

from ai_core_backend.catalog import build_graph, load_catalog

HEADER = (
    "id,name,category,image_type,brand,price,currency,colour,materials,flags,"
    "free_from,sizes_in_stock,description,image_url,product_url"
)

ROWS = [
    "TS01,Everyday Tee,T-shirts,tshirt,Kindred,19,USD,white,cotton,,,S:6|M:0,"
    "Soft everyday tee.,images/TS01.svg,/products/TS01",
    "JA01,Trail Shell,Jackets,jacket,Northpeak,89.5,USD,green,nylon|polyester,"
    'waterproof|recycled,nickel_free,M:2,"Shell, with a hood.",images/JA01.svg,/products/JA01',
    "TS14,Mystery Tee,T-shirts,tshirt,Kindred,18,USD,orange,,,,S:3,No fabric info.,"
    "images/TS14.svg,/products/TS14",
]

CATALOG = {
    "name": "Test Catalog",
    "source": {"file": "products.csv", "format": "csv"},
    "product": {
        "node_type": "Product",
        "name_column": "name",
        "id_column": "id",
        "description_column": "description",
        "properties": [
            {"column": "id", "name": "sku", "type": "string"},
            {"column": "price", "name": "price", "type": "float"},
        ],
    },
    "node_types": {
        "Product": {"role": "product"},
        "Brand": {"role": "brand"},
        "Category": {"role": "category"},
        "Material": {"role": "attribute"},
        "Size": {"role": "attribute"},
        "Restriction": {"role": "restriction"},
    },
    "relationships": {
        "BELONGS_TO": {"label": "belongs to", "from": "Product", "to": "Category"},
        "IS_MADE_BY": {"label": "is made by", "from": "Product", "to": "Brand"},
        "MADE_OF": {"label": "is made of", "from": "Product", "to": "Material"},
        "AVAILABLE_IN": {
            "label": "is available in",
            "from": "Product",
            "to": "Size",
        },
        "IS_FREE_FROM": {"label": "is free from", "from": "Product", "to": "Restriction"},
    },
    "columns": {
        "category": {"node_type": "Category", "relationship": "BELONGS_TO"},
        "brand": {"node_type": "Brand", "relationship": "IS_MADE_BY"},
        "materials": {
            "node_type": "Material",
            "relationship": "MADE_OF",
            "separator": "|",
            "as_property": "materials",
        },
        "free_from": {
            "node_type": "Restriction",
            "relationship": "IS_FREE_FROM",
            "separator": "|",
            "strip_suffix": "_free",
        },
        "sizes_in_stock": {
            "node_type": "Size",
            "relationship": "AVAILABLE_IN",
            "separator": "|",
            "counts": True,
            "edge_property": "stock",
        },
    },
}


def _rows():
    return list(csv.DictReader(io.StringIO("\n".join([HEADER, *ROWS]))))


def _graph():
    return build_graph(CATALOG, _rows())


def _node(graph, node_id):
    return next(node for node in graph.nodes if node.id == node_id)


def _properties(graph, node_id):
    return {p.name: p for p in _node(graph, node_id).data.properties}


def test_builds_a_product_node_per_row():
    products = [n for n in _graph().nodes if n.data.type == "Product"]
    assert [n.data.name for n in products] == ["Everyday Tee", "Trail Shell", "Mystery Tee"]


def test_price_is_a_float_property():
    properties = _properties(_graph(), "product-ja01")
    assert properties["price"].type == "float"
    assert properties["price"].value == 89.5


def test_stock_lives_on_the_available_in_edge_as_an_integer():
    graph = _graph()
    edge = next(e for e in graph.edges if e.source == "product-ja01" and e.target == "size-m")
    assert edge.key == "AVAILABLE_IN"
    assert [(p.name, p.type, p.value) for p in edge.properties] == [("stock", "integer", 2)]


def test_sold_out_size_keeps_an_edge_with_zero_stock():
    graph = _graph()
    edges = {
        e.target: e.properties[0].value
        for e in graph.edges
        if e.source == "product-ts01" and e.key == "AVAILABLE_IN"
    }
    assert edges == {"size-s": 6, "size-m": 0}


def test_stock_is_not_duplicated_on_the_product():
    properties = _properties(_graph(), "product-ts01")
    assert not any(name.startswith("stock") for name in properties)


def test_edges_carry_stable_key_and_display_label():
    graph = _graph()
    made_by = [e for e in graph.edges if e.key == "IS_MADE_BY"]
    assert made_by
    assert {e.relationship for e in made_by} == {"is made by"}


def test_shared_attributes_become_one_node_with_many_edges():
    graph = _graph()
    brands = [n for n in graph.nodes if n.data.type == "Brand"]
    assert sorted(n.data.name for n in brands) == ["Kindred", "Northpeak"]
    kindred = [e for e in graph.edges if e.target == "brand-kindred"]
    assert {e.source for e in kindred} == {"product-ts01", "product-ts14"}


def test_missing_materials_produce_no_material_edges():
    graph = _graph()
    keys = {e.key for e in graph.edges if e.source == "product-ts14"}
    assert "MADE_OF" not in keys
    assert "materials" not in _properties(graph, "product-ts14")


def test_multi_value_columns_produce_one_edge_each():
    graph = _graph()
    made_of = [e for e in graph.edges if e.source == "product-ja01" and e.key == "MADE_OF"]
    assert {e.target for e in made_of} == {"material-nylon", "material-polyester"}


def test_suffix_is_stripped_from_restriction_names():
    graph = _graph()
    restrictions = [n for n in graph.nodes if n.data.type == "Restriction"]
    assert [n.data.name for n in restrictions] == ["Nickel"]


def test_size_names_keep_their_case():
    graph = _graph()
    sizes = {n.data.name for n in graph.nodes if n.data.type == "Size"}
    assert sizes == {"S", "M"}


def test_quoted_description_is_preserved():
    assert _node(_graph(), "product-ja01").data.description == "Shell, with a hood."


def _write_catalog(tmp_path: Path, catalog: dict) -> Path:
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    return path


def test_load_catalog_accepts_a_valid_definition(tmp_path):
    loaded = load_catalog(_write_catalog(tmp_path, CATALOG))
    assert loaded["name"] == "Test Catalog"


def test_load_catalog_rejects_unknown_relationship(tmp_path):
    broken = {**CATALOG, "columns": {"brand": {"node_type": "Brand", "relationship": "NOPE"}}}
    with pytest.raises(ValueError, match="unknown relationship"):
        load_catalog(_write_catalog(tmp_path, broken))


def test_load_catalog_requires_exactly_one_product_type(tmp_path):
    node_types = {**CATALOG["node_types"], "Bundle": {"role": "product"}}
    with pytest.raises(ValueError, match="exactly one product"):
        load_catalog(_write_catalog(tmp_path, {**CATALOG, "node_types": node_types}))
