import pytest
from pydantic import ValidationError

from ai_core_backend.schemas import NodeProperty


def test_property_defaults_to_string_type():
    prop = NodeProperty(name="color", value="red")
    assert prop.type == "string"
    assert prop.value == "red"


def test_string_property_stringifies_numeric_input():
    assert NodeProperty(name="sku", type="string", value=42).value == "42"


def test_integer_property_accepts_numbers_and_numeric_strings():
    assert NodeProperty(name="stock", type="integer", value=12).value == 12
    assert NodeProperty(name="stock", type="integer", value=" 12 ").value == 12
    assert NodeProperty(name="stock", type="integer", value=12.0).value == 12


def test_integer_property_rejects_fractions_and_text():
    for bad in (12.5, "12.5", "abc"):
        with pytest.raises(ValidationError):
            NodeProperty(name="stock", type="integer", value=bad)


def test_float_property_accepts_numbers_and_numeric_strings():
    assert NodeProperty(name="price", type="float", value="9.99").value == 9.99
    assert NodeProperty(name="price", type="float", value=10).value == 10.0


def test_float_property_rejects_text_and_non_finite():
    for bad in ("abc", "nan", "inf"):
        with pytest.raises(ValidationError):
            NodeProperty(name="price", type="float", value=bad)


def test_numeric_value_keeps_its_python_type():
    assert isinstance(NodeProperty(name="stock", type="integer", value="3").value, int)
    assert isinstance(NodeProperty(name="price", type="float", value="3").value, float)


def test_overlong_string_property_is_rejected():
    with pytest.raises(ValidationError):
        NodeProperty(name="notes", value="x" * 2_001)
