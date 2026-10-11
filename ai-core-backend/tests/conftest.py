import pytest


@pytest.fixture
def anyio_backend():
    # Only asyncio is installed (no trio) — anyio's plugin would otherwise
    # try to run every async test under both.
    return "asyncio"
