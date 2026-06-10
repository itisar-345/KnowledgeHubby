# Knowledge Hubs

Knowledge Hubs is a local-first product for turning team knowledge into reusable operational memory. Paste meeting notes, project writeups, retrospectives, process docs, or decision logs, and the app extracts structured knowledge such as decisions, risks, checklists, lessons, how-to patterns, and best practices.

The product includes a FastAPI backend, a JSON-backed local knowledge store, and a Next.js workspace for ingesting and browsing extracted knowledge.

## Product Positioning

Teams lose valuable context in scattered notes, chat threads, and long documents. Knowledge Hubs gives that context a durable home by converting raw text artifacts into searchable knowledge items and lightweight relationship graphs.

Use it for:

- capturing decisions and lessons from meetings or retrospectives
- turning project notes into checklists and how-to guidance
- identifying risks, success factors, and best practices from team documents
- building a local knowledge base without requiring an external database

## Core Capabilities

- **Artifact ingestion**: submit manual notes, documents, summaries, or process text.
- **Knowledge extraction**: identify decisions, risks, best practices, lessons, checklists, and how-to items.
- **Local persistence**: store artifacts, extracted items, relationships, and playbooks in JSON.
- **Knowledge browser**: search and filter extracted knowledge in the Next.js UI.
- **Knowledge item details**: inspect extracted metadata, source artifacts, tags, and relationships.
- **Graph-ready API**: expose relationship data for knowledge graph visualizations.
- **Frontend graph visualization**: browse artifact-to-knowledge relationships from the hub.
- **Playbook support**: create curated playbooks from structured steps.

## Product Architecture

```text
Knowledge Hubs
+-- backend/                 FastAPI service and extraction pipeline
|   +-- app/
|   |   +-- main.py           API routes and ingestion orchestration
|   |   +-- store.py          JSON persistence layer
|   |   +-- services/         Extraction, normalization, graph, and curation services
|   +-- data/                 Local knowledge store
+-- frontend/                Next.js product UI
|   +-- src/
|       +-- app/              App routes and global shell
|       +-- components/       Shared UI components
+-- docker-compose.yml        Full product runtime
+-- .env.example              Frontend API configuration
```

## Tech Stack

- **Frontend**: Next.js, React, TypeScript, lucide-react
- **Backend**: FastAPI, Pydantic, Uvicorn
- **Storage**: local JSON file at `backend/data/knowledge_store.json`
- **Runtime**: Docker Compose or local Node/Python processes

## Run Locally

### 1. Configure Environment

Copy the example environment file if you want to customize the frontend API URL:

```bash
cp .env.example .env
```

Default API target:

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

### 2. Start the Backend

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

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the product at:

```text
http://localhost:3000
```

## Run With Docker

```bash
docker compose up --build
```

The frontend runs on `http://localhost:3000` and the backend runs on `http://localhost:8000`.

## API Surface

### `GET /health`

Returns backend health status.

### `GET /knowledge`

Returns the full local knowledge store:

- `artifacts`
- `knowledge_items`
- `relationships`
- `playbooks`

### `POST /knowledge/artifacts`

Ingests a source artifact and extracts knowledge items.

Example request:

```json
{
  "title": "Q2 Launch Retro",
  "content": "We decided to freeze scope two weeks before launch...",
  "source": "manual",
  "author": "Product Team",
  "tags": ["launch", "retro"]
}
```

### `POST /knowledge/playbooks`

Creates a curated playbook from structured steps.

### `GET /knowledge/graph`

Returns graph visualization data built from artifacts, knowledge items, and relationships.

## Data Model

Knowledge Hubs stores four primary collections:

- **Artifacts**: raw source documents and metadata.
- **Knowledge items**: extracted decisions, risks, lessons, practices, checklists, and how-to items.
- **Relationships**: links between artifacts and extracted knowledge items.
- **Playbooks**: curated reusable workflows.

The default persistence layer is intentionally simple so the product can run locally without setup. For production use, the store can be replaced with a database-backed implementation behind the same persistence boundary.

## Development Notes

- Backend CORS is configured for the local frontend on ports `3000` and `8000`.
- Extracted IDs are deterministic hashes based on artifact content and extracted item titles.
- The current extraction services are lightweight and deterministic; they are designed to be replaced or extended with richer NLP or LLM-backed extraction.
- Docker mounts `backend/data` so local knowledge persists across container rebuilds.

## Roadmap

- import support for files and external sources
- database-backed persistence option
- authentication and workspace separation
- human review workflow for accepting or editing extracted knowledge
