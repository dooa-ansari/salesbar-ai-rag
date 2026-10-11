"""openrouter_client's own logic: short-circuits, response-shape validation,
and the index-sort that protects against a provider returning embeddings
out of request order. The actual HTTP call is faked out."""

import pytest

from ai_core_backend import openrouter_client
from ai_core_backend.openrouter_client import OpenRouterError, generate_answer, generate_embeddings


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text or str(json_body)

    def json(self):
        return self._json_body


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient, used as `async with ... as client`."""

    def __init__(self, response: FakeResponse | Exception, **_kwargs):
        self._response = response
        self.last_request: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, *, headers=None, json=None):
        self.last_request = {"url": url, "headers": headers, "json": json}
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch_client(monkeypatch, response: FakeResponse | Exception):
    monkeypatch.setattr(
        openrouter_client.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response, **kwargs)
    )


def _with_api_key(monkeypatch, key: str = "test-key"):
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", key)


@pytest.mark.anyio
async def test_generate_embeddings_empty_input_short_circuits_without_a_call(monkeypatch):
    # No API key set either — if this reached the HTTP layer it would raise.
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "")
    assert await generate_embeddings([]) == []


@pytest.mark.anyio
async def test_generate_embeddings_without_api_key_raises(monkeypatch):
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "")
    with pytest.raises(OpenRouterError, match="OPENROUTER_API_KEY"):
        await generate_embeddings(["hello"])


@pytest.mark.anyio
async def test_generate_embeddings_sorts_by_index_not_response_order(monkeypatch):
    _with_api_key(monkeypatch)
    # Provider returns them out of order; caller must still get [a, b] back
    # for input ["a", "b"].
    body = {
        "data": [
            {"index": 1, "embedding": [2.0]},
            {"index": 0, "embedding": [1.0]},
        ]
    }
    _patch_client(monkeypatch, FakeResponse(200, body))

    result = await generate_embeddings(["a", "b"])
    assert result == [[1.0], [2.0]]


@pytest.mark.anyio
async def test_generate_embeddings_non_200_raises(monkeypatch):
    _with_api_key(monkeypatch)
    _patch_client(monkeypatch, FakeResponse(401, text="unauthorized"))

    with pytest.raises(OpenRouterError, match="401"):
        await generate_embeddings(["hello"])


@pytest.mark.anyio
async def test_generate_embeddings_malformed_body_raises(monkeypatch):
    _with_api_key(monkeypatch)
    _patch_client(monkeypatch, FakeResponse(200, {"unexpected": "shape"}))

    with pytest.raises(OpenRouterError, match="Unexpected response shape"):
        await generate_embeddings(["hello"])


@pytest.mark.anyio
async def test_generate_embeddings_count_mismatch_raises(monkeypatch):
    _with_api_key(monkeypatch)
    body = {"data": [{"index": 0, "embedding": [1.0]}]}
    _patch_client(monkeypatch, FakeResponse(200, body))

    with pytest.raises(OpenRouterError, match="Expected 2"):
        await generate_embeddings(["a", "b"])


@pytest.mark.anyio
async def test_generate_embeddings_network_error_raises(monkeypatch):
    import httpx

    _with_api_key(monkeypatch)
    _patch_client(monkeypatch, httpx.ConnectError("boom"))

    with pytest.raises(OpenRouterError, match="Failed to reach OpenRouter"):
        await generate_embeddings(["hello"])


@pytest.mark.anyio
async def test_generate_answer_without_api_key_raises(monkeypatch):
    monkeypatch.setattr(openrouter_client, "OPENROUTER_API_KEY", "")
    with pytest.raises(OpenRouterError, match="OPENROUTER_API_KEY"):
        await generate_answer("who is the father?", "context")


@pytest.mark.anyio
async def test_generate_answer_strips_and_returns_content(monkeypatch):
    _with_api_key(monkeypatch)
    body = {"choices": [{"message": {"content": "  Robert is the father.  "}}]}
    _patch_client(monkeypatch, FakeResponse(200, body))

    answer = await generate_answer("who is the father?", "context")
    assert answer == "Robert is the father."


@pytest.mark.anyio
async def test_generate_answer_malformed_body_raises(monkeypatch):
    _with_api_key(monkeypatch)
    _patch_client(monkeypatch, FakeResponse(200, {"unexpected": "shape"}))

    with pytest.raises(OpenRouterError, match="Unexpected response shape"):
        await generate_answer("who is the father?", "context")
