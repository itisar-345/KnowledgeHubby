# Knowledge Hubs

Focused repo extracted from the larger Future of Work platform.

This version keeps only the Knowledge Hubs slice:

- ingest manual notes, docs, meeting summaries, and process text
- extract decisions, risks, best practices, lessons, checklists, and how-to items
- store artifacts and extracted knowledge locally in JSON
- expose a small FastAPI backend
- provide a Next.js UI for ingesting and browsing knowledge

## Run Locally

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Docker

```bash
docker compose up --build
```

## Source

The initial extraction, graph, ingestion, and curation services were copied from:

- `intelligence_plane/path5_knowledge_hubs`
- `experience_layer/src/app/knowledge`

This repo intentionally leaves out the broken multi-service platform wiring.
