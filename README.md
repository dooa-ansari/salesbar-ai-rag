# GraphRAG Chat System

[![Tests](https://github.com/dooa-ansari/GraphRag-Chats/actions/workflows/test.yml/badge.svg)](https://github.com/dooa-ansari/GraphRag-Chats/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)

Build a knowledge graph visually, then ask it questions in plain English.

A full-stack app for building a graph of entities and relationships by hand
(name, type, description, key/value properties, labeled relationships),
embedding each node for semantic search, and querying it through a chat
panel that combines **vector search** (finds the nodes that match the
meaning of your question) with a **live Neo4j traversal** (reads that
node's actual current relationships, fresh, at search time — not baked
into the embedding) to answer questions grounded in the graph.

![Demo: building a small graph, generating embeddings, and asking it a question](docs/demo.gif)

*Building a 6-node "Startup team" graph, then asking "Who should I ask about a payments bug?". The canvas highlights the nodes and relationships the answer came from. (Recorded with sample data, sped up 1.5x.)*

## Features

- **Visual graph editor** — [React Flow](https://reactflow.dev) canvas: add nodes with a name, type, description and arbitrary properties; connect them with labeled, directional relationships; drag edges to reshape them.
- **Auto-arrange** — one click (dagre) re-lays out a congested graph with zero overlap.
- **Save/load named graphs** — persisted in Neo4j; saving an existing name updates it in place.
- **Generate text** — turns the graph into a plain-English description.
- **Generate embeddings** — one vector per node (attributes only), via a free OpenRouter model, stored directly on each `:GraphNode`.
- **Hybrid search** — a chat panel where each question does a Neo4j vector search for semantically matching nodes, then a live Cypher traversal for their actual relationships, then an LLM synthesizes an answer grounded in both. The canvas highlights exactly what was matched vs. traversed.
- **Autosave** — a 15s debounced countdown saves in-progress edits so you don't lose work.
- **Seed data** — a fresh, empty database is automatically populated with 6 example graphs on first run (see below), so there's something to open and search immediately.
- **Use-case demo** — [`use-case-ecommerce`](use-case-ecommerce) is a standalone storefront with a single search bar, built against the "Grocery Store Catalog" seed graph, showing hybrid search applied to a real use case.

## Example seed graphs

Loaded automatically once, only if the database is completely empty (see
`ai-core-backend/src/ai_core_backend/seed_data.py`):

| Graph | Size | Try asking |
|---|---|---|
| Smith Family Tree | 10 nodes / 30 edges | "who is the grandfather of Emily?" |
| Grocery Store Catalog | 73 / 90 | "gmo free, seed oil free, chocolate flavour protein bar without any sugar" |
| Nimbus Cloud Storage FAQs | 52 / 79 | "I'm on the free plan and ran out of storage, can I still share links that don't expire?" |
| Alex Rivera — Resume | 48 / 98 | "find an engineer with Python and AWS experience who built a RAG system" |
| City Library Catalog | 45 / 68 | "a fantasy novel under 450 pages that's available right now, by an award-winning author" |
| Movie Recommendation Catalog | 53 / 116 | "a mind-bending sci-fi movie under two hours on StreamVault" |

## Tech stack

- **Frontend**: React 19, TypeScript, Vite, React Flow, Tailwind CSS v4, React Router
- **Backend**: FastAPI, async Neo4j driver, Pydantic
- **Database**: Neo4j 5 (Community Edition) — graph storage + native vector index
- **LLM**: [OpenRouter](https://openrouter.ai) — free-tier models for embeddings and chat completions
- **Infra**: Docker Compose (prod-style build + a dev override with hot reload on both services)

## Quick start

Requires Docker and Docker Compose.

```bash
git clone https://github.com/dooa-ansari/GraphRag-Chats.git
cd GraphRag-Chats
cp .env.example .env
# Open .env and set a real NEO4J_PASSWORD (required — see Security below).
# OPENROUTER_API_KEY is optional: get a free key at https://openrouter.ai/keys
# if you want "Generate embeddings"/search to work; the rest of the app
# works fine without one.

docker compose up --build
```

Then open:

- **App**: http://localhost:3000
- **E-commerce search demo**: http://localhost:3001
- **Backend API**: http://localhost:8000 (docs at `/docs`)
- **Neo4j Browser**: http://localhost:7474

`docker compose up` (no extra flags) automatically layers
`docker-compose.override.yml` on top, which bind-mounts both frontends'
source and runs them in hot-reload mode — edit a file locally and it shows
up without rebuilding. To run the plain, production-built images instead:
`docker compose -f docker-compose.yml up`.

## Development (without Docker)

**Backend** (needs [uv](https://docs.astral.sh/uv/) and a running Neo4j):

```bash
cd ai-core-backend
uv sync
uv run uvicorn ai_core_backend.main:app --reload
```

**Frontend**:

```bash
cd admin-panel
npm install
npm run dev
```

## Testing

```bash
# Backend — pytest, fully mocked (no real Neo4j/OpenRouter needed)
cd ai-core-backend && uv run pytest

# Frontend — Vitest unit tests (pure logic, no DOM needed)
cd admin-panel && npm run test

# Frontend — Playwright E2E (spins up its own dev server, mocks the API)
cd admin-panel && npm run test:e2e
```

Both the backend and frontend unit-test suites run on every push via
[`.github/workflows/test.yml`](.github/workflows/test.yml).

## Project structure

```
ai-core-backend/
  src/ai_core_backend/
    main.py            FastAPI app and all endpoints
    neo4j_client.py     Neo4j connection + Cypher
    openrouter_client.py  Embeddings/chat completions via OpenRouter
    schemas.py          Pydantic request/response models
    seed_data.py         The 6 example graphs loaded on first run
  tests/                 pytest suite

admin-panel/
  src/
    pages/              Graphs list + graph editor pages
    components/         GraphNode, RelationshipEdge, SearchPanel, Button
    graph.ts             Node/edge helpers, layout, humanize/embed text
    api.ts               Backend API client
    *.test.ts            Vitest unit tests
  e2e/                   Playwright E2E tests

use-case-ecommerce/         Standalone storefront search demo against the
                               "Grocery Store Catalog" seed graph
  src/
    api.ts                   Backend API client (resolves the catalog by name)
    App.tsx                  Search bar + results
    components/              SearchBar, ProductCard

docker-compose.yml           Base stack (neo4j, backend, frontend, ecommerce)
docker-compose.override.yml  Dev hot-reload (auto-applied by `docker compose up`)
```

## Security

**This stack has no authentication** — not the backend API, not the
frontend — and by default every port (Neo4j's 7474/7687, the backend's
8000) is published to the host's `0.0.0.0`, not just `localhost`. That's
fine for local development, but **do not** run it on a host whose ports are
reachable from an untrusted network (a cloud VM with open inbound rules, a
shared LAN) without putting it behind your own auth, VPN, or reverse proxy.
Anyone who can reach those ports can read, edit or delete every saved
graph, browse the Neo4j database directly, and run up your OpenRouter bill.

Always set a real `NEO4J_PASSWORD` in `.env` — the fallback used when it's
unset is a public placeholder, not a safe default. See the warning comment
at the top of `docker-compose.yml` for details.

## Environment variables

Set in `.env` (copy from `.env.example`; gitignored):

| Variable | Default | Notes |
|---|---|---|
| `NEO4J_PASSWORD` | *(weak placeholder)* | **Set this.** See Security above. |
| `OPENROUTER_API_KEY` | *(empty)* | Needed for "Generate embeddings" and search; rest of the app works without it. |
| `BACKEND_PORT` | `8000` | Host port for the API. |
| `FRONTEND_PORT` | `3000` | Host port for the app. |
| `ECOMMERCE_PORT` | `3001` | Host port for the e-commerce search demo. |
| `NEO4J_HTTP_PORT` | `7474` | Host port for the Neo4j Browser. |
| `NEO4J_BOLT_PORT` | `7687` | Host port for the Bolt protocol. |

## License

MIT — see [LICENSE](LICENSE).
