import asyncio
import sys
from dataclasses import dataclass, field

from ai_core_backend import neo4j_client
from ai_core_backend.numeric_properties import BadValue, convert_legacy_properties


@dataclass
class MigrationReport:
    nodes_scanned: int = 0
    values_migrated: int = 0
    bad_values: list[tuple[str, str, BadValue]] = field(default_factory=list)


async def migrate_numeric_properties(
    types_by_name: dict[str, str], catalog_id: str | None = None
) -> MigrationReport:
    report = MigrationReport()
    async with neo4j_client.get_driver().session() as session:
        result = await session.run(
            """
            MATCH (n:GraphNode)
            WHERE n.propertiesJson IS NOT NULL
              AND ($catalogId IS NULL OR n.catalogId = $catalogId)
            RETURN n.catalogId AS catalogId, n.id AS id, n.propertiesJson AS propertiesJson
            """,
            catalogId=catalog_id,
        )
        records = [record async for record in result]

        for record in records:
            report.nodes_scanned += 1
            properties_json, numeric, bad_values, converted = convert_legacy_properties(
                record["propertiesJson"], types_by_name
            )
            report.values_migrated += converted
            report.bad_values.extend(
                (record["catalogId"], record["id"], bad) for bad in bad_values
            )
            if converted:
                await session.run(
                    """
                    MATCH (n:GraphNode {catalogId: $catalogId, id: $id})
                    SET n.propertiesJson = $propertiesJson
                    SET n += $numeric
                    """,
                    catalogId=record["catalogId"],
                    id=record["id"],
                    propertiesJson=properties_json,
                    numeric=numeric,
                )
    return report


def _parse_arguments(arguments: list[str]) -> dict[str, str]:
    types_by_name = {}
    for argument in arguments:
        name, _, type_ = argument.partition(":")
        if type_ not in ("integer", "float"):
            raise SystemExit(f"expected name:integer or name:float, got {argument!r}")
        types_by_name[name] = type_
    return types_by_name


async def _main(arguments: list[str]) -> None:
    types_by_name = _parse_arguments(arguments)
    if not types_by_name:
        raise SystemExit("usage: python -m ai_core_backend.migrate price:float stock:integer")
    try:
        report = await migrate_numeric_properties(types_by_name)
    finally:
        await neo4j_client.close_driver()
    print(f"scanned {report.nodes_scanned} node(s), migrated {report.values_migrated} value(s)")
    for catalog_id, node_id, bad in report.bad_values:
        print(f"skipped {bad.property}={bad.value!r} on node {node_id} (catalog {catalog_id})")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
