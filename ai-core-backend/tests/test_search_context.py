from ai_core_backend.main import _format_context
from ai_core_backend.schemas import NodeProperty, RelationshipFact, SearchResultNode


def _result(relationships):
    return SearchResultNode(
        id="p1",
        name="Trail Shell",
        type="Product",
        score=0.9,
        relationships=relationships,
    )


def test_context_includes_edge_properties_such_as_stock():
    result = _result(
        [
            RelationshipFact(
                relationship="is available in",
                direction="outgoing",
                otherId="size-m",
                otherName="M",
                properties=[NodeProperty(name="stock", type="integer", value=2)],
            )
        ]
    )
    assert "Trail Shell is available in M (stock=2)." in _format_context([result])


def test_context_without_edge_properties_is_unchanged():
    result = _result(
        [
            RelationshipFact(
                relationship="is made by",
                direction="outgoing",
                otherId="brand-northpeak",
                otherName="Northpeak",
            )
        ]
    )
    assert "Trail Shell is made by Northpeak." in _format_context([result])
