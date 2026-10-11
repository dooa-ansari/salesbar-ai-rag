"""Sample data loaded automatically on first run (see main.lifespan).

Currently empty: add `SaveGraphRequest` instances to SEED_GRAPHS and they are
saved when the database has no graphs yet.
"""

from ai_core_backend.schemas import SaveGraphRequest

SEED_GRAPHS: list[SaveGraphRequest] = []
