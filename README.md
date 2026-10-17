# Salesbar AI RAG

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5-008CC1?logo=neo4j&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)

A drop-in replacement for the regular search bar. Instead of a dead-end
"no results found", Salesbar always has something useful to say:

- **Results exist** — it shows them.
- **Close matches or popular items exist** — it shows similar or popular
  items instead.
- **Nothing fits** — it acts like a salesman: understands what the shopper
  is after and guides them toward the best alternative in plain language.

Under the hood, the catalog is modeled as a knowledge graph (entities,
attributes and labeled relationships) stored in Neo4j. Each question is
answered with **vector search** (finds the nodes that match the meaning of
the query) combined with a **live Neo4j traversal** (reads those nodes'
actual, current relationships at search time — not baked into the
embedding), and an LLM turns the grounded result into the answer.

This repository contains the **AI core backend** (FastAPI + Neo4j + OpenRouter)
and the **admin panel**, a visual editor for building and testing the graph
that powers the search.

## Features

- **Visual graph editor** — [React Flow](https://reactflow.dev) canvas: add nodes with a name, type, description and arbitrary properties; connect them with labeled, directional relationships; drag edges to reshape them.
- **Auto-arrange** — one click (dagre) re-lays out a congested graph with zero overlap.
- **Save/load named graphs** — persisted in Neo4j; saving an existing name updates it in place.
- **Generate text** — turns the graph into a plain-English description.
- **Generate embeddings** — one vector per node (attributes only), via a free OpenRouter model, stored directly on each `:GraphNode`.
- **Hybrid search** — a chat panel where each question does a Neo4j vector search for semantically matching nodes, then a live Cypher traversal for their actual relationships, then an LLM synthesizes an answer grounded in both. The canvas highlights exactly what was matched vs. traversed.
- **Autosave** — a 15s debounced countdown saves in-progress edits so you don't lose work.
- **Seed data** — graphs listed in `SEED_GRAPHS` are loaded automatically into an empty database on first run (currently none; see below).

## Seed data

On first run, if the database has no saved graphs, every graph in
`SEED_GRAPHS` (`ai-core-backend/src/ai_core_backend/seed_data.py`) is saved
automatically. The list is currently empty; add `SaveGraphRequest` entries
there to ship example graphs.

## Tech stack

- **Admin panel**: React 19, TypeScript, Vite, React Flow, Tailwind CSS v4, React Router
- **AI core backend**: FastAPI, async Neo4j driver, Pydantic
- **Database**: Neo4j 5 (Community Edition) — graph storage + native vector index
- **LLM**: [OpenRouter](https://openrouter.ai) — free-tier models for embeddings and chat completions
- **Infra**: Docker Compose (prod-style build + a dev override with hot reload on both services)

## Quick start

Requires Docker and Docker Compose.

```bash
git clone https://github.com/dooa-ansari/salesbar-ai-rag.git
cd salesbar-ai-rag

# Create a .env file next to docker-compose.yml with at least:
#   NEO4J_PASSWORD=<a real password>   (required — see Security below)
#   OPENROUTER_API_KEY=<your key>      (optional: https://openrouter.ai/keys;
#                                       needed for "Generate embeddings"/search)

docker compose up --build
```

Then open:

- **Admin panel**: http://localhost:3000
- **AI core backend API**: http://localhost:8000 (docs at `/docs`)
- **Neo4j Browser**: http://localhost:7474

`docker compose up` (no extra flags) automatically layers
`docker-compose.override.yml` on top, which bind-mounts the admin panel's
and backend's source and runs them in hot-reload mode — edit a file locally and it shows
up without rebuilding. To run the plain, production-built images instead:
`docker compose -f docker-compose.yml up`.

## Development (without Docker)

**Backend** (needs [uv](https://docs.astral.sh/uv/) and a running Neo4j):

```bash
cd ai-core-backend
uv sync
uv run uvicorn ai_core_backend.main:app --reload
```

**Admin panel**:

```bash
cd admin-panel
npm install
npm run dev
```

## Testing

```bash
# Backend — pytest, fully mocked (no real Neo4j/OpenRouter needed)
cd ai-core-backend && uv run pytest

# Backend integration tests — run Cypher against a throwaway Neo4j
docker run -d --name salesbar-test-neo4j -p 17687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5-community
cd ai-core-backend && TEST_NEO4J_URI=bolt://localhost:17687 uv run pytest tests/integration

# Admin panel — Vitest unit tests (pure logic, no DOM needed)
cd admin-panel && npm run test

# Admin panel — Playwright E2E (spins up its own dev server, mocks the API)
cd admin-panel && npm run test:e2e
```


## Project structure

```
ai-core-backend/
  src/ai_core_backend/
    main.py            FastAPI app and all endpoints
    neo4j_client.py     Neo4j connection + Cypher
    openrouter_client.py  Embeddings/chat completions via OpenRouter
    schemas.py          Pydantic request/response models
    seed_data.py         Graphs loaded on first run (currently empty)
  tests/                 pytest suite

admin-panel/
  src/
    pages/              Graphs list + graph editor pages
    components/         GraphNode, RelationshipEdge, SearchPanel, Button
    graph.ts             Node/edge helpers, layout, humanize/embed text
    api.ts               Backend API client
    *.test.ts            Vitest unit tests
  e2e/                   Playwright E2E tests

docker-compose.yml           Base stack (neo4j, ai-core-backend, frontend)
docker-compose.override.yml  Dev hot-reload (auto-applied by `docker compose up`)
```

## Security

**This stack has no authentication** — not the backend API, not the
admin panel — and by default every port (Neo4j's 7474/7687, the backend's
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

Set in `.env` (gitignored):

| Variable | Default | Notes |
|---|---|---|
| `NEO4J_PASSWORD` | *(weak placeholder)* | **Set this.** See Security above. |
| `OPENROUTER_API_KEY` | *(empty)* | Needed for "Generate embeddings" and search; rest of the app works without it. |
| `OPENROUTER_EMBEDDING_MODEL` | `liquid/lfm-2.5-embedding-350m:free` | Embedding model used for node vectors. |
| `OPENROUTER_CHAT_MODEL` | `liquid/lfm-2.5-2.6b:free` | Chat model that synthesizes answers. |
| `EMBEDDING_DIMENSIONS` | `1024` | Output size of the embedding model; sets the Neo4j vector index size. If you change it on an existing database, drop the vector index and regenerate embeddings. |
| `BACKEND_PORT` | `8000` | Host port for the AI core backend API. |
| `FRONTEND_PORT` | `3000` | Host port for the admin panel. |
| `NEO4J_HTTP_PORT` | `7474` | Host port for the Neo4j Browser. |
| `NEO4J_BOLT_PORT` | `7687` | Host port for the Bolt protocol. |

## License

MIT — see [LICENSE](LICENSE).
