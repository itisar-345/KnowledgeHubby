# App Flow Document
## Knowledge Hubs — End-to-End User Journeys

**Version:** 1.0
**Status:** Draft

---

## 1. First-Run Setup Flow

```
Install Docker Compose stack
        │
        ▼
First launch → Onboarding wizard
        │
        ├─► Step 1: Welcome / pitch screen
        │
        ├─► Step 2: Detect hardware (RAM/CPU) → recommend model tier
        │            → user clicks "Install" → Ollama pulls model (progress bar)
        │
        ├─► Step 3 (optional, skippable): Add cloud API key
        │
        ├─► Step 4: Register admin user + create workspace
        │
        ▼
Redirect to /knowledge (empty state, "Ingest your first document")
```

## 2. Authentication Flow

```
User visits app → auth.guard checks token
        │
        ├─ valid → proceed to requested route
        │
        └─ invalid/missing → redirect /login
                                  │
                    ┌─────────────┴─────────────┐
                    │                             │
              Sign In tab                   Register tab
              (POST /auth/token)        (POST /auth/register)
                    │                             │
                    └──────────► JWT stored, workspace_id bound ─────►
                                          redirect /knowledge
```

## 3. Ingestion Flow (Text / File / URL)

```
User selects mode (Text/File/URL) in Ingest Panel
        │
        ▼
POST /knowledge/artifacts (or /upload or /url)
        │
        ▼
ingestion_normalization: normalize format + extract metadata
        │
        ▼
knowledge_extraction (regex): decisions/risks/lessons/checklists/best-practices/how-tos
        │
        ▼
db: persist artifact + knowledge_items + CONTAINS relationships
        │
        ▼
neo4j_graph: upsert nodes + edges
        │
        ▼
EmbeddingProvider.embed(): local sentence-transformer generates vectors
        │
        ▼
neo4j_graph.upsert_item_embedding(): store vectors
        │
        ▼
LLMProvider._summarise_text(): local (or cloud, if enabled) generates artifact summary
        │
        ▼
neo4j_graph.upsert_artifact_summary(): store summary + embedding
        │
        ▼
Response → Knowledge Grid updates, new items shown with "pending review" state
```

## 4. Transcript / Slack / Email Ingestion Flow (LLM-powered path)

```
User pastes transcript, selects "Transcript" mode
        │
        ▼
POST /knowledge/artifacts/transcript
        │
        ▼
llm_extraction: routed through LLMProvider
        │
        ├─ LLM_PROVIDER=ollama (default) → local model extracts
        │        decisions / action_items / risks / summary as JSON
        │
        └─ LLM_PROVIDER=openai/anthropic (if enabled) → cloud model extracts
        │
        ▼
(same downstream path as §3: persist → graph → embed → summarize)
```

## 5. Review Flow

```
Reviewer opens /review
        │
        ▼
GET /knowledge/review → pending items list (grouped by source artifact,
                          tagged with extraction engine: Regex/Local LLM/Cloud LLM)
        │
        ├─ Accept → PATCH /knowledge/review/:id {status: accepted}
        │             → item becomes searchable, eligible for cross-linking
        │
        ├─ Edit + Accept → PATCH with modified fields → same as above
        │
        └─ Reject → PATCH {status: rejected} → excluded from search/RAG
```

## 6. Cross-Source Linking Flow (background/triggered)

```
User or scheduled job triggers POST /knowledge/link
        │
        ▼
cross_source_linker: pairwise Jaccard similarity across all accepted items
        from different artifacts
        │
        ▼
Items above 0.12 threshold → cross_links + relationships tables updated
        │
        ▼
Reflected in: Knowledge Detail "Related Items" section,
              GraphRAG graph expansion stage
```

## 7. GraphRAG Query Flow

```
User types question in /graphrag chat
        │
        ▼
POST /knowledge/graphrag/query
        │
        ▼
[1] transform_query → LLMProvider: sub-queries + HyDE doc
        │
        ▼
[2] route_query → intent classification (local embedding-similarity
                    classifier first; LLM fallback if ambiguous)
        │
        ▼
[3] embed question + HyDE → EmbeddingProvider (local)
        │
        ▼
[4] retrieve_for_rag:
        ├─ Neo4j available → vector ANN + graph expansion
        └─ Neo4j unavailable → SQLite cosine + BM25 + cross-link expansion
        │
        ▼
[5] _rrf: fuse ranked lists from all sub-queries
        │
        ▼
[6] summary index injected as context prefix
        │
        ▼
[7] rerank → LLMProvider scores candidates 0-10
        │
        ▼
[8] _build_context → structured window (summaries → items → graph neighbors)
        │
        ▼
[9] _generate → LLMProvider produces answer with [item_id] citations
        │
        ▼
db: query_logs entry written
        │
        ▼
Response streamed to chat UI with progressive status + citations + context nodes
```

## 8. Search Flow

```
User enters query + filters (type/source/tag) in /search
        │
        ▼
GET /knowledge/search
        │
        ▼
Full-text + filter match against knowledge_items and artifacts
        │
        ▼
Results split: Knowledge Items | Artifacts
        │
        ▼
URL updated (shareable link with query params)
```

## 9. Playbook Creation Flow

```
User selects a set of accepted knowledge items (e.g. how-to steps)
        │
        ▼
POST /knowledge/playbooks
        │
        ▼
curation_layer.build_playbook(): sequences steps, categorizes
        (event/lab/onboarding/general)
        │
        ▼
Playbook persisted → visible in Knowledge Hub / Detail views
```

## 10. OKF Import/Export Flow

```
Export:
  GET /knowledge/okf/export → okf.export_okf_payload()
        → full workspace serialized (nodes/edges/artifacts/metadata) → JSON download

Import:
  POST /knowledge/okf/import → okf.normalize_okf_payload()
        → tolerant field-mapping → validated → persisted into workspace
```
*(No frontend UI yet — flows above are API-level; UI is a Should-Have per PRD §7.2, useful for air-gapped transfer between environments.)*

## 11. Provider Switching Flow (admin)

```
Admin opens Model & Privacy panel
        │
        ▼
Selects new LLM or embedding provider
        │
        ├─ LLM change → takes effect on next request, no data migration needed
        │
        └─ Embedding change → triggers re-embedding job:
                 all existing knowledge_items + artifact summaries
                 re-vectorized under new provider signature,
                 old vector index dropped and rebuilt
        │
        ▼
Progress shown in Model & Privacy panel until complete
```
