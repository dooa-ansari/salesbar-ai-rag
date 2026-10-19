"""AI search for a storefront.

1. The chat model turns the shopper's words into requested and excluded
   values, choosing from the catalog's own node names.
2. Each value is linked to a graph node: by name, or through the vector index
   when the model's wording doesn't match a node exactly.
3. Neo4j returns, for every product, which of those nodes it is connected to.
   The catalog's constraint config decides what counts as exact, near,
   alternative or ruled out.
"""

import json
import re
from dataclasses import dataclass, field

from ai_core_backend import neo4j_client, openrouter_client
from ai_core_backend.schemas import ShopConstraint, ShopMatch

MIN_RESULTS = 4
MAX_RESULTS = 8
RELATED_RESULTS = 12
PRODUCT_POOL = 50


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", str(text).lower())).strip()


@dataclass
class ShopConfig:
    product_type: str = "Product"
    keys: dict[str, str] = field(default_factory=dict)
    restriction_types: set[str] = field(default_factory=set)
    claim_types: set[str] = field(default_factory=set)
    safety: set[str] = field(default_factory=set)
    near: set[str] = field(default_factory=set)
    soft: set[str] = field(default_factory=set)
    price_property: str | None = None
    price_is_near: bool = False
    price_tolerance: float = 0.0
    size_type: str | None = None
    stock_property: str | None = None
    hints: list[str] = field(default_factory=list)

    def kind(self, node_type: str) -> str:
        if node_type in self.safety:
            return "safety"
        if node_type in self.near:
            return "near"
        if node_type in self.soft:
            return "soft"
        return "required"


def _hint(entry: dict) -> str:
    target = entry.get("require") or entry.get("exclude")
    action = "require" if entry.get("require") else "exclude"
    phrases = ", ".join(f'"{phrase}"' for phrase in entry["phrases"])
    return f"{phrases} -> {action} {target['node_type']} {target['value']}"


def config_from_catalog(catalog: dict | None) -> ShopConfig:
    if not catalog:
        return ShopConfig()
    product_type = catalog["product"]["node_type"]
    node_types = catalog["node_types"]
    columns = catalog["columns"].values()
    constraints = catalog.get("constraints") or {}
    safety = set((constraints.get("safety") or {}).get("node_types", []))
    near = constraints.get("near") or {}
    soft = constraints.get("soft") or {}
    counts = next((spec for spec in columns if spec.get("counts") and spec.get("edge_property")), None)
    price_property = next(iter(near.get("properties", []) + soft.get("properties", [])), None)
    return ShopConfig(
        product_type=product_type,
        keys={
            relationship["to"]: key
            for key, relationship in catalog["relationships"].items()
            if relationship["from"] == product_type
        },
        restriction_types={name for name, spec in node_types.items() if spec["role"] == "restriction"},
        claim_types={
            spec["node_type"]
            for spec in columns
            if spec.get("separator") and not spec.get("counts") and spec["node_type"] not in safety
        },
        safety=safety,
        near=set(near.get("node_types", [])),
        soft=set(soft.get("node_types", [])),
        price_property=price_property,
        price_is_near=price_property in near.get("properties", []),
        price_tolerance=float(near.get("price_tolerance", 0)),
        size_type=counts["node_type"] if counts else None,
        stock_property=counts["edge_property"] if counts else None,
        hints=[_hint(entry) for entry in catalog.get("synonyms") or []],
    )


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    type: str


@dataclass(frozen=True)
class Constraint:
    kind: str
    node: Node | None = None
    amount: float | None = None


@dataclass
class Intent:
    require: list[tuple[str, str]] = field(default_factory=list)
    exclude: list[tuple[str, str]] = field(default_factory=list)
    max_price: float | None = None
    min_price: float | None = None


def build_prompt(vocabulary: list[Node], config: ShopConfig) -> str:
    by_type: dict[str, list[str]] = {}
    for node in vocabulary:
        by_type.setdefault(node.type, []).append(node.name)
    lines = [f"{node_type}: {', '.join(names)}" for node_type, names in by_type.items()]
    restrictions = ", ".join(sorted(config.restriction_types & set(by_type)))
    rules = [
        "Use only types and values from the lists, spelled exactly as listed.",
        'Map everyday words to the closest value, e.g. "small" means the smallest size.',
        "Only include what the shopper actually asked for. Never add values they did not mention.",
        '"no X", "without X" and "X free" go in exclude.',
    ]
    if restrictions:
        rules.append(f'Values of {restrictions} mean "free from". "nickel free" means require that value.')
    if config.hints:
        rules.append("Catalog phrase hints:\n" + "\n".join(f"  {hint}" for hint in config.hints))
    return (
        "You turn a shopper's search into JSON filters for a product catalog.\n"
        "Catalog values by type:\n"
        + "\n".join(lines)
        + "\n\nReply with JSON only:\n"
        '{"require": [{"type": "<type>", "value": "<value>"}], '
        '"exclude": [{"type": "<type>", "value": "<value>"}], '
        '"maxPrice": <number or null>, "minPrice": <number or null>}\n'
        "Rules:\n" + "\n".join(f"- {rule}" for rule in rules)
    )


def parse_intent(text: str) -> Intent:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in model reply: {text[:200]}")
    data = json.loads(text[start : end + 1])

    def pairs(items) -> list[tuple[str, str]]:
        result = []
        for item in items or []:
            if isinstance(item, dict) and item.get("value") is not None:
                result.append((str(item.get("type") or ""), str(item["value"])))
            elif isinstance(item, str):
                result.append(("", item))
        return result

    def number(value) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return Intent(
        require=pairs(data.get("require")),
        exclude=pairs(data.get("exclude")),
        max_price=number(data.get("maxPrice")),
        min_price=number(data.get("minPrice")),
    )


def resolve(
    intent: Intent, vocabulary: list[Node], config: ShopConfig
) -> tuple[list[Constraint], list[tuple[str, str, str]]]:
    """Links the model's values to graph nodes by name. Returns the
    constraints plus (kind, type, value) items still needing a vector link."""
    by_name: dict[str, list[Node]] = {}
    for node in vocabulary:
        by_name.setdefault(normalize(node.name), []).append(node)
    types = {node.type for node in vocabulary}

    def lookup(name: str, preferred: str) -> Node | None:
        key = normalize(name)
        candidates = by_name.get(key) or (by_name.get(key[:-1]) if key.endswith("s") else None) or []
        return next((n for n in candidates if n.type == preferred), candidates[0] if candidates else None)

    constraints: list[Constraint] = []
    unresolved: list[tuple[str, str, str]] = []
    for kind, items in (("require", intent.require), ("exclude", intent.exclude)):
        for node_type, value in items:
            found = [node for node in (lookup(value, node_type), lookup(node_type, "")) if node]
            if not found and node_type in types:
                unresolved.append((kind, node_type, value))
            constraints += [Constraint(kind, node) for node in found]

    constraints = [
        Constraint("require", c.node) if c.kind == "exclude" and c.node.type in config.restriction_types else c
        for c in constraints
    ]
    if intent.max_price is not None:
        constraints.append(Constraint("max_price", amount=intent.max_price))
    if intent.min_price is not None:
        constraints.append(Constraint("min_price", amount=intent.min_price))
    return constraints, unresolved


def unique(constraints: list[Constraint]) -> list[Constraint]:
    kept: list[Constraint] = []
    for constraint in constraints:
        duplicate = any(c.node == constraint.node for c in kept) if constraint.node else constraint in kept
        if not duplicate:
            kept.append(constraint)
    return kept


def _money(amount: float, currency: str = "USD") -> str:
    number = f"{amount:.0f}" if float(amount).is_integer() else f"{amount:.2f}"
    return f"${number}" if currency in ("USD", "") else f"{number} {currency}"


def constraint_label(constraint: Constraint, config: ShopConfig) -> str:
    if constraint.kind == "max_price":
        return f"Under {_money(constraint.amount)}"
    if constraint.kind == "min_price":
        return f"Over {_money(constraint.amount)}"
    node = constraint.node
    if constraint.kind == "exclude":
        return f"No {node.name.lower()}"
    if node.type == config.size_type:
        return f"Size {node.name}"
    if node.type in config.restriction_types:
        return f"{node.name} free"
    return node.name


def constraint_kind(constraint: Constraint, config: ShopConfig) -> str:
    if constraint.kind in ("max_price", "min_price"):
        return "near" if config.price_is_near else "soft"
    return config.kind(constraint.node.type)


@dataclass
class _Check:
    kind: str
    ok: bool
    reason: str = ""


def _check(row: dict, constraint: Constraint, config: ShopConfig) -> _Check:
    kind = constraint_kind(constraint, config)

    if constraint.kind in ("max_price", "min_price"):
        price = row["price"]
        if not isinstance(price, (int, float)):
            return _Check(kind, False, "Price not recorded")
        limit = constraint.amount
        if constraint.kind == "max_price":
            gap = price - limit
            reason = f"{_money(gap)} over budget"
        else:
            gap = limit - price
            reason = f"{_money(gap)} under your minimum"
        if gap <= 0:
            return _Check(kind, True)
        within = limit > 0 and gap <= config.price_tolerance * limit
        return _Check(kind if within else "soft", False, reason)

    node = constraint.node
    edge = row["hits"].get(node.id)
    has_type = config.keys.get(node.type) in row["keys"]

    if constraint.kind == "exclude":
        if edge is not None:
            return _Check(kind, False, f"Contains {node.name.lower()}")
        if not has_type and kind == "safety":
            return _Check(kind, False, f"{node.type} not recorded")
        return _Check(kind, True)

    if node.type == config.size_type:
        if edge is None:
            return _Check(kind, False, f"No size {node.name}")
        stock = next((p.value for p in edge if p.name == config.stock_property), None)
        if isinstance(stock, (int, float)) and stock <= 0:
            return _Check(kind, False, f"Size {node.name} sold out")
        return _Check(kind, True)

    if edge is not None:
        return _Check(kind, True)
    if node.type in config.restriction_types or node.type in config.claim_types:
        return _Check(kind, False, f"Not {constraint_label(constraint, config).lower()}")
    if not has_type:
        return _Check(kind, False, f"{node.type} not recorded")
    return _Check(kind, False, f"Not {node.name.lower()}")


def _tier(checks: list[_Check]) -> str | None:
    failed = [check for check in checks if not check.ok]
    if any(check.kind == "required" for check in failed):
        return None
    safety = [check for check in failed if check.kind == "safety"]
    near = [check for check in failed if check.kind == "near"]
    soft = [check for check in failed if check.kind == "soft"]
    if safety:
        return "ruled-out" if not soft and len(near) <= 1 else None
    if not failed:
        return "exact"
    if len(near) == 1 and not soft:
        return "near"
    return "alternative"


def _message(exact: int, near: int, alternatives: int, ruled_out: int, safety_labels: list[str]) -> str:
    joined = " and ".join(f"“{label}”" for label in safety_labels)
    parts = []
    if exact:
        parts.append(f"{exact} {'product matches' if exact == 1 else 'products match'} everything you asked for.")
        if near:
            parts.append(f"{near} more {'comes' if near == 1 else 'come'} close.")
    elif near:
        parts.append(f"Nothing matches every detail, but {near} {'comes' if near == 1 else 'come'} close.")
    if alternatives:
        if exact:
            parts.append("Here are a few similar ones too.")
        else:
            parts.append("Here are the closest alternatives." if near else "No exact match, so here are the closest alternatives.")
    if not (exact or near or alternatives):
        if ruled_out and safety_labels:
            return f"I can't confirm anything here as {joined}, so I'm not recommending any of it."
        return "Nothing in the catalog fits that yet. Try a wider budget or another size."
    if ruled_out and safety_labels:
        parts.append(f"I left out {ruled_out} that I can't confirm as {joined}.")
    return " ".join(parts)


@dataclass
class ShopResult:
    constraints: list[ShopConstraint]
    message: str
    results: list[ShopMatch]
    ruled_out: list[ShopMatch]


def rank(rows: list[dict], constraints: list[Constraint], scores: dict[str, float], config: ShopConfig) -> ShopResult:
    labels = [ShopConstraint(label=constraint_label(c, config), kind=constraint_kind(c, config)) for c in constraints]
    prices = {row["id"]: row["price"] if isinstance(row["price"], (int, float)) else float("inf") for row in rows}

    def order(matches: list[ShopMatch]) -> list[ShopMatch]:
        return sorted(matches, key=lambda m: (len(m.reasons), -m.score, prices.get(m.productId, float("inf"))))

    if not constraints:
        related = [row for row in rows if row["id"] in scores] if scores else rows
        related = sorted(related, key=lambda row: (-scores.get(row["id"], 0.0), prices[row["id"]]))
        results = [
            ShopMatch(productId=row["id"], match="related", score=scores.get(row["id"], 0.0))
            for row in related[:RELATED_RESULTS]
        ]
        message = "Here's what I'd show you." if results else "Nothing in the catalog fits that yet."
        return ShopResult(labels, message, results, [])

    tiers: dict[str, list[ShopMatch]] = {"exact": [], "near": [], "alternative": [], "ruled-out": []}
    for row in rows:
        checks = [_check(row, constraint, config) for constraint in constraints]
        tier = _tier(checks)
        if tier is None:
            continue
        failed = [check for check in checks if not check.ok]
        if tier == "ruled-out":
            failed = [check for check in failed if check.kind == "safety"]
        tiers[tier].append(
            ShopMatch(
                productId=row["id"],
                match=tier,
                reasons=[check.reason for check in failed],
                score=scores.get(row["id"], 0.0),
            )
        )

    exact, near = order(tiers["exact"]), order(tiers["near"])
    results = exact + near
    alternatives: list[ShopMatch] = []
    if len(results) < MIN_RESULTS:
        alternatives = order(tiers["alternative"])[: MAX_RESULTS - len(results)]
        results += alternatives
    ruled_out = order(tiers["ruled-out"])
    safety_labels = [label.label for label in labels if label.kind == "safety"]
    message = _message(len(exact), len(near), len(alternatives), len(ruled_out), safety_labels)
    return ShopResult(labels, message, results, ruled_out)


class ShopSearchError(RuntimeError):
    """The chat or embedding model failed, or the chat reply wasn't the JSON asked for."""


async def _understand(query: str, vocabulary: list[Node], config: ShopConfig) -> Intent:
    try:
        reply = await openrouter_client.chat(
            [
                {"role": "system", "content": build_prompt(vocabulary, config)},
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
        return parse_intent(reply)
    except (openrouter_client.OpenRouterError, ValueError) as error:
        raise ShopSearchError(f"Could not read the query with the chat model: {error}") from error


async def _link(graph_id: str, unresolved: list[tuple[str, str, str]]) -> list[Constraint]:
    if not unresolved:
        return []
    embeddings = await openrouter_client.generate_embeddings([value for _, _, value in unresolved])
    linked = []
    for (kind, node_type, _), embedding in zip(unresolved, embeddings):
        nodes = await neo4j_client.search_graph_nodes(graph_id, embedding, 1, node_type)
        if nodes:
            linked.append(Constraint(kind, Node(nodes[0].id, nodes[0].name, nodes[0].type)))
    return linked


async def search(graph_id: str, query: str, config: ShopConfig) -> ShopResult:
    vocabulary = [
        Node(item["id"], item["name"], item["type"])
        for item in await neo4j_client.catalog_vocabulary(graph_id, config.product_type)
    ]
    intent = await _understand(query, vocabulary, config)
    constraints, unresolved = resolve(intent, vocabulary, config)

    try:
        (query_embedding,) = await openrouter_client.generate_embeddings([query])
        products = await neo4j_client.search_graph_nodes(graph_id, query_embedding, PRODUCT_POOL, config.product_type)
        scores = {product.id: product.score for product in products or []}
        constraints += await _link(graph_id, unresolved)
    except openrouter_client.OpenRouterError as error:
        raise ShopSearchError(f"Could not embed the query: {error}") from error

    constraints = unique(constraints)
    rows = await neo4j_client.product_matches(
        graph_id,
        [c.node.id for c in constraints if c.node],
        sorted(set(config.keys.values())),
        config.price_property,
        config.product_type,
    )
    return rank(rows, constraints, scores, config)
