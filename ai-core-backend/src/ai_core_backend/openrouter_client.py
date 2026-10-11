"""Client for OpenRouter's OpenAI-compatible embeddings and chat completions APIs.

https://openrouter.ai/docs/api_reference/embeddings
"""

import os

import httpx

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free-tier text embedding model, up to 512 tokens of input.
EMBEDDING_MODEL = "liquid/lfm-2.5-embedding-350m:free"
EMBEDDING_DIMENSIONS = 1024

# Free-tier chat model, used to synthesize an answer from retrieved nodes.
CHAT_MODEL = "liquid/lfm-2.5-2.6b:free"


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter can't be reached, rejects the key, or returns an
    unexpected response shape."""


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """One batched call for all of `texts`, returned in the same order."""
    if not texts:
        return []
    if not OPENROUTER_API_KEY:
        raise OpenRouterError("OPENROUTER_API_KEY is not set on the backend")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/embeddings",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model": EMBEDDING_MODEL, "input": texts},
            )
        except httpx.HTTPError as error:
            raise OpenRouterError(f"Failed to reach OpenRouter: {error}") from error

    if response.status_code != 200:
        raise OpenRouterError(
            f"OpenRouter returned {response.status_code}: {response.text}"
        )

    body = response.json()
    try:
        # Sorted by index rather than trusted to already be in request order.
        items = sorted(body["data"], key=lambda item: item["index"])
        embeddings = [item["embedding"] for item in items]
    except (KeyError, TypeError) as error:
        raise OpenRouterError(
            f"Unexpected response shape from OpenRouter: {body}"
        ) from error

    if len(embeddings) != len(texts):
        raise OpenRouterError(
            f"Expected {len(texts)} embeddings back, got {len(embeddings)}"
        )
    return embeddings


async def generate_answer(query: str, context: str) -> str:
    """Synthesizes a natural-language answer to `query`, grounded only in
    `context` (the retrieved nodes, formatted as text by the caller)."""
    if not OPENROUTER_API_KEY:
        raise OpenRouterError("OPENROUTER_API_KEY is not set on the backend")

    messages = [
        {
            "role": "system",
            "content": (
                "You answer questions about a knowledge graph using only the "
                "entities given to you as context. Be concise — a few sentences "
                "at most. If the context doesn't contain the answer, say so "
                "rather than guessing."
            ),
        },
        {
            "role": "user",
            "content": f"Context (matching graph entities):\n{context}\n\nQuestion: {query}",
        },
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model": CHAT_MODEL, "messages": messages},
            )
        except httpx.HTTPError as error:
            raise OpenRouterError(f"Failed to reach OpenRouter: {error}") from error

    if response.status_code != 200:
        raise OpenRouterError(
            f"OpenRouter returned {response.status_code}: {response.text}"
        )

    body = response.json()
    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise OpenRouterError(
            f"Unexpected response shape from OpenRouter: {body}"
        ) from error
