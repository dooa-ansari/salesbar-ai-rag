import csv
import io

from ai_core_backend.seed_data import build_product_graph

HEADER = (
    "id,name,category,image_type,brand,price,currency,colour,materials,flags,"
    "free_from,sizes_in_stock,description,image_url,product_url"
)

ROWS = [
    "TS01,Everyday Tee,T-shirts,tshirt,Kindred,19,USD,white,cotton,,,S:6|M:0,"
    "Soft everyday tee.,images/TS01.svg,/products/TS01",
    "JA01,Trail Shell,Jackets,jacket,Northpeak,89.5,USD,green,nylon|polyester,"
    "waterproof|recycled,,M:2,\"Shell, with a hood.\",images/JA01.svg,/products/JA01",
    "TS14,Mystery Tee,T-shirts,tshirt,Kindred,18,USD,orange,,,,S:3,No fabric info.,"
    "images/TS14.svg,/products/TS14",
]


def _rows():
    return list(csv.DictReader(io.StringIO("\n".join([HEADER, *ROWS]))))


def _node(graph, node_id):
    return next(node for node in graph.nodes if node.id == node_id)


def test_builds_a_product_node_per_row():
    graph = build_product_graph(_rows())
    products = [node for node in graph.nodes if node.data.type == "Product"]
    assert [node.data.name for node in products] == ["Everyday Tee", "Trail Shell", "Mystery Tee"]


def test_price_is_float_and_stock_is_integer():
    graph = build_product_graph(_rows())
    properties = {p.name: p for p in _node(graph, "product-ja01").data.properties}
    assert properties["price"].type == "float"
    assert properties["price"].value == 89.5
    assert properties["stock M"].type == "integer"
    assert properties["stock M"].value == 2


def test_sold_out_size_is_kept_as_zero():
    graph = build_product_graph(_rows())
    properties = {p.name: p.value for p in _node(graph, "product-ts01").data.properties}
    assert properties["stock M"] == 0


def test_shared_attributes_become_one_node_with_many_edges():
    graph = build_product_graph(_rows())
    brand_nodes = [n for n in graph.nodes if n.data.type == "Brand"]
    assert sorted(n.data.name for n in brand_nodes) == ["Kindred", "Northpeak"]
    kindred_edges = [e for e in graph.edges if e.target == "brand-kindred"]
    assert {e.source for e in kindred_edges} == {"product-ts01", "product-ts14"}


def test_missing_materials_produce_no_material_edges():
    graph = build_product_graph(_rows())
    mystery_relationships = {e.relationship for e in graph.edges if e.source == "product-ts14"}
    assert "made of" not in mystery_relationships


def test_multi_value_columns_produce_one_edge_each():
    graph = build_product_graph(_rows())
    made_of = [e for e in graph.edges if e.source == "product-ja01" and e.relationship == "made of"]
    assert {e.target for e in made_of} == {"materials-nylon", "materials-polyester"}


def test_quoted_description_is_preserved():
    graph = build_product_graph(_rows())
    assert _node(graph, "product-ja01").data.description == "Shell, with a hood."
