import json

import pytest

from ai_core_backend.numeric_properties import (
    convert_legacy_properties,
    numeric_key,
    numeric_values,
    parse_text_number,
)
from ai_core_backend.schemas import NodeProperty


def test_numeric_key_is_prefixed_and_normalized():
    assert numeric_key("price") == "prop_price"
    assert numeric_key("Stock M") == "prop_stock_m"


def test_only_numeric_typed_properties_get_native_values():
    values = numeric_values(
        [
            NodeProperty(name="price", type="float", value="19"),
            NodeProperty(name="stock", type="integer", value=3),
            NodeProperty(name="colour", value="white"),
            NodeProperty(name="sku", value="19"),
        ]
    )
    assert values == {"prop_price": 19.0, "prop_stock": 3}
    assert isinstance(values["prop_price"], float)


def test_text_price_from_a_client_is_stored_as_a_number():
    prop = NodeProperty(name="price", type="float", value="24.50")
    assert prop.value == 24.5
    assert isinstance(prop.value, float)
    assert json.loads(json.dumps(prop.model_dump()))["value"] == 24.5


@pytest.mark.parametrize(
    "text, expected",
    [("19", 19.0), ("$24.50", 24.5), (" 30 ", 30.0), ("1e2", 100.0)],
)
def test_parse_text_number_accepts_common_price_text(text, expected):
    assert parse_text_number(text, "float") == expected


@pytest.mark.parametrize("text", ["N/A", "", "cheap", "nan", "inf", "1,299.50", "12abc"])
def test_parse_text_number_rejects_bad_values(text):
    with pytest.raises(ValueError):
        parse_text_number(text, "float")


def test_parse_text_number_integer_rejects_fractions():
    assert parse_text_number("12", "integer") == 12
    with pytest.raises(ValueError):
        parse_text_number("12.5", "integer")


def test_convert_legacy_properties_converts_good_and_reports_bad():
    legacy = json.dumps(
        [
            {"name": "price", "value": "$19.99"},
            {"name": "colour", "value": "white"},
        ]
    )
    new_json, numeric, bad, converted = convert_legacy_properties(legacy, {"price": "float"})
    assert converted == 1
    assert bad == []
    assert numeric == {"prop_price": 19.99}
    assert json.loads(new_json) == [
        {"name": "price", "type": "float", "value": 19.99},
        {"name": "colour", "type": "string", "value": "white"},
    ]


def test_convert_legacy_properties_leaves_a_bad_value_untouched():
    legacy = json.dumps([{"name": "price", "value": "N/A"}])
    new_json, numeric, bad, converted = convert_legacy_properties(legacy, {"price": "float"})
    assert converted == 0
    assert numeric == {}
    assert [(b.property, b.value) for b in bad] == [("price", "N/A")]
    assert json.loads(new_json) == [{"name": "price", "type": "string", "value": "N/A"}]


def test_convert_legacy_properties_is_idempotent():
    legacy = json.dumps([{"name": "price", "value": "19"}])
    first_json, _, _, first_count = convert_legacy_properties(legacy, {"price": "float"})
    second_json, numeric, bad, second_count = convert_legacy_properties(first_json, {"price": "float"})
    assert (first_count, second_count) == (1, 0)
    assert second_json == first_json
    assert numeric == {"prop_price": 19.0}
    assert bad == []
