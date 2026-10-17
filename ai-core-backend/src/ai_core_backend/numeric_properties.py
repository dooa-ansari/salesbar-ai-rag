import json
import math
import re
from dataclasses import dataclass

from ai_core_backend.schemas import NodeProperty

NUMERIC_PREFIX = "prop_"
NUMERIC_TYPES = ("integer", "float")


@dataclass(frozen=True)
class BadValue:
    property: str
    value: str


def numeric_key(name: str) -> str:
    return NUMERIC_PREFIX + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def numeric_values(properties: list[NodeProperty]) -> dict[str, int | float]:
    return {
        numeric_key(p.name): p.value
        for p in properties
        if p.type in NUMERIC_TYPES
    }


def parse_text_number(value: str, type_: str) -> int | float:
    text = value.strip().removeprefix("$").strip()
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"not a finite number: {value!r}")
    if type_ == "integer":
        if not number.is_integer():
            raise ValueError(f"not a whole number: {value!r}")
        return int(number)
    return number


def convert_legacy_properties(
    properties_json: str, types_by_name: dict[str, str]
) -> tuple[str, dict[str, int | float], list[BadValue], int]:
    entries = json.loads(properties_json or "[]")
    bad_values: list[BadValue] = []
    converted = 0
    for entry in entries:
        type_ = types_by_name.get(entry["name"])
        if type_ is None or entry.get("type") in NUMERIC_TYPES:
            continue
        try:
            entry["value"] = parse_text_number(str(entry["value"]), type_)
        except ValueError:
            bad_values.append(BadValue(entry["name"], str(entry["value"])))
            continue
        entry["type"] = type_
        converted += 1
    properties = [NodeProperty(**entry) for entry in entries]
    return json.dumps([p.model_dump() for p in properties]), numeric_values(properties), bad_values, converted
