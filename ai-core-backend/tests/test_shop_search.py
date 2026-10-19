import pytest
from shop_fixtures import Clothes

from ai_core_backend.shop_search import (
    Constraint,
    Intent,
    build_prompt,
    parse_intent,
    rank,
    resolve,
    unique,
)


@pytest.fixture(scope="module")
def clothes():
    return Clothes()


def _run(clothes, intent, scores=None):
    constraints, unresolved = resolve(intent, clothes.vocabulary, clothes.config)
    assert unresolved == []
    constraints = unique(constraints)
    rows = clothes.rows([c.node.id for c in constraints if c.node])
    return rank(rows, constraints, scores or {}, clothes.config)


def _names(clothes, matches):
    return [clothes.name(match.productId) for match in matches]


RUNNING_QUERY = Intent(
    require=[("Category", "Jackets"), ("Feature", "Waterproof"), ("Size", "M")],
    exclude=[("Material", "Wool")],
    max_price=120,
)


def test_running_query_check_from_products_md(clothes):
    result = _run(clothes, RUNNING_QUERY)

    exact = [m for m in result.results if m.match == "exact"]
    near = {clothes.name(m.productId): m.reasons for m in result.results if m.match == "near"}
    assert set(_names(clothes, exact)) == {"Trail Shell Jacket", "Storm Rider Rain Jacket", "Coast Rain Mac"}
    assert near == {"Alpine Rain Jacket": ["Size M sold out"], "Harbor Rain Jacket": ["$1 over budget"]}
    assert set(_names(clothes, result.ruled_out)) == {
        "Storm Rider Rain Jacket Wool Lined",
        "Fjord Wool Blend Shell",
        "Mystery Rain Jacket",
    }
    assert "Peak Hardshell" not in _names(clothes, result.results)
    assert {(c.label, c.kind) for c in result.constraints} == {
        ("Jackets", "required"),
        ("Waterproof", "soft"),
        ("Size M", "near"),
        ("No wool", "safety"),
        ("Under $120", "near"),
    }


def test_blue_shirt_in_size_small_only_returns_t_shirts(clothes):
    result = _run(clothes, Intent(require=[("Colour", "Blue"), ("Category", "T-shirts"), ("Size", "S")]))

    exact = [m for m in result.results if m.match == "exact"]
    assert _names(clothes, exact) == ["Recycled Run Tee"]
    assert all(clothes.product_id(n).startswith("product-ts") for n in _names(clothes, result.results))
    assert {m.match for m in result.results[1:]} == {"alternative"}


def test_unknown_material_is_ruled_out_not_recommended(clothes):
    result = _run(clothes, Intent(require=[("Category", "Jackets")], exclude=[("Material", "Wool")]))
    assert "Mystery Rain Jacket" not in _names(clothes, result.results)
    reasons = {clothes.name(m.productId): m.reasons for m in result.ruled_out}
    assert reasons["Mystery Rain Jacket"] == ["Material not recorded"]


def test_nickel_free_excluded_by_the_model_still_means_require(clothes):
    constraints, _ = resolve(
        Intent(require=[("Category", "Shoes")], exclude=[("Material", "Nickel")]), clothes.vocabulary, clothes.config
    )
    nickel = next(c for c in constraints if c.node.name == "Nickel")
    assert (nickel.kind, nickel.node.type) == ("require", "Restriction")

    result = _run(clothes, Intent(require=[("Category", "Shoes"), ("Restriction", "Nickel")]))
    assert result.results == []
    assert "can't confirm" in result.message


def test_resolve_survives_type_and_value_swapped(clothes):
    constraints, unresolved = resolve(
        Intent(require=[("Jackets", "waterproof")]), clothes.vocabulary, clothes.config
    )
    assert {(c.node.type, c.node.name) for c in constraints} == {("Category", "Jackets"), ("Feature", "Waterproof")}
    assert unresolved == []


def test_resolve_sends_unknown_wording_to_vector_linking(clothes):
    constraints, unresolved = resolve(Intent(require=[("Size", "small")]), clothes.vocabulary, clothes.config)
    assert constraints == []
    assert unresolved == [("require", "Size", "small")]


def test_resolve_drops_values_with_no_known_type(clothes):
    constraints, unresolved = resolve(Intent(require=[("Fabric", "silk")]), clothes.vocabulary, clothes.config)
    assert constraints == [] and unresolved == []


def test_no_constraints_ranks_products_by_similarity(clothes):
    boot = clothes.product_id("Waterproof Hiking Boot")
    result = rank(clothes.rows([]), [], {boot: 0.9}, clothes.config)
    assert [m.match for m in result.results] == ["related"]
    assert result.results[0].productId == boot


def test_unique_keeps_one_constraint_per_node(clothes):
    blue = clothes.node("Colour", "Blue")
    assert unique([Constraint("require", blue), Constraint("require", blue)]) == [Constraint("require", blue)]


def test_prompt_lists_graph_values_and_catalog_hints(clothes):
    prompt = build_prompt(clothes.vocabulary, clothes.config)
    assert "Size: " in prompt and "EU42" in prompt
    assert '"no wool"' in prompt
    assert "Restriction" in prompt


@pytest.mark.parametrize(
    "reply",
    [
        '{"require": [{"type": "Colour", "value": "Blue"}], "exclude": [], "maxPrice": 50, "minPrice": null}',
        '```json\n{"require": [{"type": "Colour", "value": "Blue"}], "maxPrice": "50"}\n```',
    ],
)
def test_parse_intent_reads_plain_and_fenced_json(reply):
    intent = parse_intent(reply)
    assert intent.require == [("Colour", "Blue")]
    assert intent.max_price == 50


def test_parse_intent_rejects_prose():
    with pytest.raises(ValueError):
        parse_intent("Sure! Here are some blue shirts.")
