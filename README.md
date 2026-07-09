# Knowledge Hubs

Knowledge Hubs is a local-first product for turning team knowledge into reusable operational memory. Paste meeting notes, project writeups, retrospectives, process docs, or decision logs, and the app extracts structured knowledge — decisions, risks, checklists, lessons, how-to patterns, and best practices — and stores it in a searchable, relationship-aware graph.

The product includes a FastAPI backend, a Neo4j-backed knowledge graph, and an Angular workspace for ingesting, browsing, editing, and querying extracted knowledge.

## Product Positioning

Teams lose valuable context in scattered notes, chat threads, and long documents. Knowledge Hubs gives that context a durable home by converting raw text artifacts into searchable knowledge items and lightweight relationship graphs.

Use it for:

- capturing decisions and lessons from meetings or retrospectives
- turning project notes into checklists and how-to guidance
- identifying risks, success factors, and best practices from team documents
- building a persistent knowledge graph with rich relationship traversal
- asking natural-language questions over your entire knowledge base

## Core Capabilities

- **Artifact ingestion**: submit text, upload files (PDF, TXT, MD), fetch URLs, or extract decisions from meeting transcripts, emails, and Slack threads using a local LLM.
- **Knowledge extraction**: identify decisions, risks, best practices, lessons, checklists, and how-to items automatically.
- **Full CRUD**: create, read, update, and delete both artifacts and individual knowledge items from the UI and API.
- **Graph persistence**: store artifacts, extracted items, relationships, and playbooks in Neo4j with full relationship traversal.
- **Interactive graph visualization**: pan, zoom (mouse wheel + buttons), and drag nodes in the knowledge graph view.
- **Knowledge browser**: filter and search extracted knowledge by type, tag, and free text.
- **Knowledge item details**: inspect extracted metadata, source artifacts, tags, relationships, and cross-source links.
- **Review workflow**: accept or reject pending knowledge items before they enter the active knowledge base.
- **Cross-source linking**: automatically detect and surface related items across different artifacts using keyword similarity.
- **Playbook support**: create curated playbooks from structured steps.
- **OKF import/export**: ingest and export knowledge using an Open Knowledge Format payload.
- **GraphRAG queries**: ask natural-language questions over the workspace and receive grounded answers with citations and context nodes.
- **Workspace provider policy**: configure workspace defaults for LLM and embedding providers, enforce local-only mode with an admin kill-switch, and store provider provenance for auditability.

## Product Architecture

```text
Knowledge Hubs
+-- backend/                  FastAPI service and extraction pipeline
|   +-- app/
|   |   +-- main.py            API routes, CRUD endpoints, ingestion orchestration
|   |   +-- store.py           Neo4j persistence layer
|   |   +-- db.py              SQLite models (SQLAlchemy async)
|   |   +-- auth.py            JWT authentication
|   |   +-- services/
|   |       +-- embeddings.py          Local-first embedding provider
|   |       +-- llm_client.py          Local-first LLM provider (Ollama / OpenAI)
|   |       +-- llm_extraction.py      LLM-backed transcript extraction
|   |       +-- graphrag.py            GraphRAG pipeline (retrieval + generation)
|   |       +-- knowledge_extraction.py  Rule-based extraction
|   |       +-- cross_source_linker.py   Cross-artifact similarity linking
|   |       +-- graph_builder.py         Graph visualization builder
|   |       +-- curation_layer.py        Playbook curation
|   |       +-- neo4j_graph.py           Neo4j graph + vector store
|   |       +-- ingestion_normalization.py
|   |       +-- item_schema.py
|   |       +-- okf.py
|   +-- data/                 SQLite fallback store
+-- frontend/                 Angular 17 product UI
|   +-- src/app/
|       +-- pages/
|       |   +-- knowledge/         Hub — ingest, browse, graph, artifact CRUD
|       |   +-- knowledge-detail/  Item detail — edit, delete, relationships
|       |   +-- search/            Full-text + filter search
|       |   +-- review/            Pending item review queue
|       |   +-- graphrag/          GraphRAG chat interface
|       |   +-- workspace-settings/ Workspace + provider policy settings
|       |   +-- login/             Authentication
|       +-- services/
|           +-- auth.service.ts    JWT auth + API base
|           +-- auth.guard.ts      Route guard
+-- docker-compose.yml        Full product runtime
+-- .env.example              Environment configuration
```

## Tech Stack

- **Frontend**: Angular 17, TypeScript
- **Backend**: FastAPI, Pydantic, Uvicorn, SQLAlchemy (async SQLite)
- **Graph store**: Neo4j (primary) — SQLite cosine search fallback when Neo4j is unavailable
- **Embeddings (default)**: sentence-transformers `all-MiniLM-L6-v2` — runs fully offline, no API key required, dim=384
- **LLM (default)**: Ollama (`llama3.1:8b` or any local model) — extraction, summarisation, GraphRAG generation and reranking
- **Cloud upgrade (optional)**: set `EMBEDDING_PROVIDER=openai` and/or `LLM_PROVIDER=openai` with an `OPENAI_API_KEY` to swap in OpenAI models independently
- **Cloud provider policy**: `ALLOW_CLOUD_PROVIDERS=false` disables OpenAI for all workspaces and enforces local-only runtime across LLM and embedding layers
- **Runtime**: Docker Compose or local Node/Python processes

## Run Locally

### 1. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

The defaults work fully offline — no API keys needed. To upgrade to OpenAI:

```bash
# .env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
EMBEDDING_DIM=1536   # text-embedding-3-small
```

To use a different local Ollama model:

```bash
OLLAMA_MODEL=mistral
```

### 2. Start Ollama (local LLM)

```bash
# Install from https://ollama.com, then:
ollama pull llama3.1:8b
```

### 3. Start the Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend health check:

```bash
curl http://localhost:8000/health
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm start
```

Open the product at:

```text
http://localhost:4200
```

## Run With Docker

```bash
docker compose up --build
```

The frontend runs on `http://localhost:3000` and the backend runs on `http://localhost:8000`.

## API Surface

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register a new user and workspace |
| `POST` | `/auth/token` | Login and receive a JWT |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Backend and Neo4j status |
| `GET` | `/health/consistency` | SQLite vs Neo4j drift report |

### Artifacts

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/knowledge` | Full workspace snapshot (artifacts, items, relationships, playbooks) |
| `POST` | `/knowledge/artifacts` | Ingest text artifact and extract knowledge |
| `POST` | `/knowledge/artifacts/upload` | Upload a file (PDF, TXT, MD) and extract knowledge |
| `POST` | `/knowledge/artifacts/url` | Fetch a URL and extract knowledge |
| `POST` | `/knowledge/artifacts/transcript` | Extract decisions from a transcript, email, or Slack thread using LLM |
| `PUT` | `/knowledge/artifacts/{id}` | Update artifact title and/or tags (re-extracts if content changes) |
| `DELETE` | `/knowledge/artifacts/{id}` | Delete artifact and all its extracted items and relationships |

### Knowledge Items

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/knowledge/items/{id}` | Update item title, tags, or details |
| `DELETE` | `/knowledge/items/{id}` | Delete a single knowledge item and its relationships |

### Review

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/knowledge/review` | List items pending review |
| `PATCH` | `/knowledge/review/{id}` | Accept or reject a pending item |

### Search & Links

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/knowledge/search` | Full-text search with type, source, and tag filters |
| `POST` | `/knowledge/link` | Run cross-source linking across all workspace items |
| `GET` | `/knowledge/links` | List all cross-source links |

### Graph & Playbooks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/knowledge/graph` | Graph visualization data (nodes + edges) |
| `POST` | `/knowledge/playbooks` | Create a curated playbook |

### OKF & GraphRAG

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/knowledge/okf/import` | Import an OKF-style JSON payload |
| `GET` | `/knowledge/okf/export` | Export workspace as OKF payload |
| `POST` | `/knowledge/graphrag/query` | Run GraphRAG query and return grounded answer with citations |

### Workspace & Provider Configuration

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workspace/settings` | Get current workspace provider policy and active provider names |
| `PATCH` | `/workspace/settings` | Update workspace provider policy and cloud access flag |
| `GET` | `/workspace/provider-configs` | List workspace provider configurations |
| `POST` | `/workspace/provider-configs` | Create a new provider configuration for the workspace |
| `PUT` | `/workspace/provider-configs/{config_id}` | Update an existing workspace provider configuration |
| `DELETE` | `/workspace/provider-configs/{config_id}` | Delete a workspace provider configuration |

## Data Model

Knowledge Hubs stores five primary collections:

- **Artifacts**: raw source documents with title, content, author, tags, and metadata.
- **Knowledge items**: extracted decisions, risks, lessons, practices, checklists, and how-to items — each linked to a source artifact.
- **Relationships**: typed edges between artifacts and knowledge items (`CONTAINS`, `RELATED_TO`).
- **Playbooks**: curated reusable workflows built from structured steps.
- **Cross-links**: similarity-scored links between knowledge items from different artifacts.

The default persistence layer is Neo4j, which supports rich relationship traversal, graph queries, and vector indexing for semantic search. SQLite is maintained in parallel as a fallback for cosine vector search and offline use.

## Frontend Pages

| Route | Description |
|-------|-------------|
| `/knowledge` | Main hub — ingest artifacts, browse extracted items, manage artifacts (edit/delete), interactive knowledge graph |
| `/knowledge/:id` | Item detail — view extracted fields, source artifact, relationships, cross-links; edit title or delete item |
| `/search` | Full-text and filtered search across items and artifacts with shareable URLs |
| `/review` | Review queue for pending knowledge items — accept, reject, or edit before promoting |
| `/graphrag` | GraphRAG chat — ask questions over the knowledge base, see context nodes and retrieval mode |
| `/workspace-settings` | Workspace/provider settings — manage default LLM, embedding, and cloud access policies |
| `/login` | Authentication |

## Interactive Graph

The knowledge graph on the hub page supports:

- **Mouse wheel zoom** — zoom toward the cursor position
- **Zoom buttons** — `+` / `−` / `⊙` reset, with a live percentage readout
- **Pan** — click and drag the canvas background
- **Node drag** — reposition individual nodes by dragging them
- **Node selection** — click a node to inspect its relationships in the side panel

## Development Notes

- **Local-first by default**: embeddings use `sentence-transformers` (all-MiniLM-L6-v2, dim=384) and LLM calls go to Ollama. No external API key is required for any feature.
- **Cloud as opt-in**: set `EMBEDDING_PROVIDER=openai` and/or `LLM_PROVIDER=openai` with `OPENAI_API_KEY` to upgrade individual layers independently.
- **Embedding dimension**: the Neo4j vector index is created with `EMBEDDING_DIM` (default 384). If you switch to OpenAI embeddings, set `EMBEDDING_DIM=1536` and recreate the index.
- **CORS**: backend allows `localhost:3000`, `localhost:4200`, and their `127.0.0.1` equivalents.
- **Deterministic IDs**: artifact and item IDs are stable SHA-256 hashes of their content, so re-ingesting the same document is idempotent.
- **Dual-store writes**: every embedding is written to both SQLite (always available) and Neo4j (when connected), so vector search degrades gracefully rather than failing.
- **Docker**: Neo4j runs as the primary store; `backend/data` is mounted for SQLite persistence across container rebuilds.
- **SQLite fallback**: set `STORAGE_BACKEND=sqlite` to bypass Neo4j entirely without code changes.
