import os
from pathlib import Path

from ai_core_backend.catalog import build_graph, load_catalog, load_rows, source_exists
from ai_core_backend.schemas import SaveGraphRequest

DEFAULT_CATALOG = Path(__file__).resolve().parents[3] / "data" / "clothes" / "catalog.yaml"
CATALOG_PATH = Path(os.environ.get("SEED_CATALOG", DEFAULT_CATALOG))


def _load_seed_catalog() -> dict | None:
    if not CATALOG_PATH.is_file():
        return None
    return load_catalog(CATALOG_PATH)


def _load_seed_graphs(catalog: dict | None) -> list[SaveGraphRequest]:
    if catalog is None or not source_exists(catalog):
        return []
    return [build_graph(catalog, load_rows(catalog))]


SEED_CATALOG: dict | None = _load_seed_catalog()
SEED_GRAPHS: list[SaveGraphRequest] = _load_seed_graphs(SEED_CATALOG)
