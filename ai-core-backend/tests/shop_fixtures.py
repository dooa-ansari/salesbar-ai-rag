from ai_core_backend.catalog import build_graph, load_catalog, load_rows
from ai_core_backend.seed_data import DEFAULT_CATALOG
from ai_core_backend.shop_search import Node, config_from_catalog


class Clothes:
    """The seed catalog in memory, answering the same questions the Neo4j
    queries answer, so ranking can be tested without a database."""

    def __init__(self):
        catalog = load_catalog(DEFAULT_CATALOG)
        self.graph = build_graph(catalog, load_rows(catalog))
        self.config = config_from_catalog(catalog)
        self.nodes = {node.id: node for node in self.graph.nodes}
        product_type = self.config.product_type
        self.products = [n for n in self.graph.nodes if n.data.type == product_type]
        self.vocabulary = [
            Node(n.id, n.data.name, n.data.type) for n in self.graph.nodes if n.data.type != product_type
        ]

    def node(self, node_type: str, name: str) -> Node:
        return next(n for n in self.vocabulary if n.type == node_type and n.name == name)

    def product_id(self, name: str) -> str:
        return next(p.id for p in self.products if p.data.name == name)

    def name(self, product_id: str) -> str:
        return self.nodes[product_id].data.name

    def rows(self, node_ids: list[str]) -> list[dict]:
        rows = []
        for product in self.products:
            edges = [edge for edge in self.graph.edges if edge.source == product.id]
            price = next((p.value for p in product.data.properties if p.name == self.config.price_property), None)
            rows.append(
                {
                    "id": product.id,
                    "price": price,
                    "hits": {edge.target: edge.properties for edge in edges if edge.target in node_ids},
                    "keys": {edge.key for edge in edges},
                }
            )
        return rows
