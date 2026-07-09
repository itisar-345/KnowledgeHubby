# Backend Schema Document
## Knowledge Hubs — SQLite + Neo4j Data Model

**Version:** 1.0
**Status:** Draft

---

## 1. SQLite Schema (System of Record)

### 1.1 `users`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| username | TEXT UNIQUE | |
| password_hash | TEXT | bcrypt via passlib |
| workspace_id | UUID FK → workspaces.id | |
| role | TEXT | `admin` \| `member` |
| created_at | DATETIME | |

### 1.2 `workspaces` *(new — currently implicit; made explicit for provider policy)*

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | |
| allow_cloud_providers | BOOLEAN | default `false` — admin kill-switch |
| default_llm_provider | TEXT | `ollama` \| `openai` \| `anthropic` |
| default_embedding_provider | TEXT | `local` \| `openai` |
| created_at | DATETIME | |

### 1.3 `artifacts`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| workspace_id | UUID FK | |
| source_type | TEXT | `text` \| `file` \| `url` \| `transcript` |
| raw_content | TEXT | normalized content |
| original_filename | TEXT NULL | |
| source_url | TEXT NULL | |
| content_hash | TEXT | for dedup (ingestion_normalization) |
| metadata | JSON | author/date/tags extracted |
| extraction_engine | TEXT | `regex` \| `local_llm` \| `cloud_llm` — **new**, tracks provenance |
| created_at | DATETIME | |

### 1.4 `artifact_summaries`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| artifact_id | UUID FK → artifacts.id | |
| summary_text | TEXT | 2-3 sentence LLM summary |
| embedding | BLOB/JSON | vector, fallback store |
| embedding_provider | TEXT | **new** — e.g. `local:all-MiniLM-L6-v2` |
| embedding_dims | INTEGER | **new** |
| created_at | DATETIME | |

### 1.5 `knowledge_items`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| artifact_id | UUID FK | |
| workspace_id | UUID FK | |
| type | TEXT | `decision` \| `risk` \| `lesson` \| `checklist` \| `best_practice` \| `how_to` |
| content | TEXT | extracted text |
| confidence_score | FLOAT | keyword-density/LLM-confidence based |
| extraction_engine | TEXT | **new** — `regex` \| `local_llm` \| `cloud_llm`, surfaced in Review UI |
| embedding | BLOB/JSON | vector fallback store |
| embedding_provider | TEXT | **new** |
| embedding_dims | INTEGER | **new** |
| status | TEXT | `pending` \| `accepted` \| `rejected` |
| reviewed_by | UUID FK → users.id NULL | |
| reviewed_at | DATETIME NULL | |
| tags | JSON | |
| created_at | DATETIME | |

### 1.6 `relationships`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| source_id | UUID | artifact or item id |
| source_type | TEXT | `artifact` \| `knowledge_item` |
| target_id | UUID | |
| target_type | TEXT | |
| relationship_type | TEXT | `CONTAINS` \| `RELATED_TO` \| `DEPENDS_ON` etc. |
| weight | FLOAT NULL | e.g. similarity score for RELATED_TO |
| created_at | DATETIME | |

### 1.7 `cross_links`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| item_a_id | UUID FK → knowledge_items.id | |
| item_b_id | UUID FK → knowledge_items.id | |
| similarity_score | FLOAT | Jaccard, threshold 0.12 |
| created_at | DATETIME | |

### 1.8 `playbooks`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| workspace_id | UUID FK | |
| title | TEXT | |
| category | TEXT | `event` \| `lab` \| `onboarding` \| `general` |
| steps | JSON | ordered step sequence |
| source_item_ids | JSON | array of knowledge_item ids used |
| created_by | UUID FK → users.id | |
| created_at | DATETIME | |

### 1.9 `query_logs`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| workspace_id | UUID FK | |
| user_id | UUID FK | |
| query_text | TEXT | |
| sub_queries | JSON | from query transformation stage |
| llm_provider | TEXT | **new** — which provider answered this query |
| embedding_provider | TEXT | **new** |
| context_node_ids | JSON | items/summaries used in context |
| answer_text | TEXT | |
| latency_ms | INTEGER | **new** — for perf monitoring, esp. relevant given local latency tradeoffs |
| created_at | DATETIME | |

### 1.10 Migration Notes

- New columns (`extraction_engine`, `embedding_provider`, `embedding_dims`, `llm_provider`, `latency_ms`, and the new `workspaces` table) ship as **additive `ALTER TABLE` migrations** consistent with existing startup-migration pattern — no destructive changes, existing DBs upgrade in place.
- `workspaces` table is new; a migration backfills one default workspace row per existing distinct `workspace_id` currently referenced in `users`.

---

## 2. Neo4j Graph Schema

### 2.1 Node Types

```
(:Artifact {
  id, workspace_id, source_type, content_hash, created_at
})

(:KnowledgeItem {
  id, artifact_id, workspace_id, type, content,
  confidence_score, extraction_engine, status,
  embedding: VECTOR, embedding_provider, embedding_dims, tags
})

(:ArtifactSummary {
  id, artifact_id, summary_text,
  embedding: VECTOR, embedding_provider, embedding_dims
})

(:Playbook {
  id, workspace_id, title, category
})
```

### 2.2 Relationship Types

```
(:Artifact)-[:CONTAINS]->(:KnowledgeItem)
(:Artifact)-[:HAS_SUMMARY]->(:ArtifactSummary)
(:KnowledgeItem)-[:RELATED_TO {similarity_score}]->(:KnowledgeItem)
(:KnowledgeItem)-[:DEPENDS_ON]->(:KnowledgeItem)
(:KnowledgeItem)-[:PART_OF]->(:Playbook)
(:KnowledgeItem)-[:DECISION_RATIONALE]->(:KnowledgeItem)   # typed edges from graph_builder
```

### 2.3 Vector Indexes

```cypher
CREATE VECTOR INDEX knowledge_item_embedding IF NOT EXISTS
FOR (n:KnowledgeItem) ON (n.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: $dims,        // 384 for local MiniLM, 1536 for OpenAI small
  `vector.similarity_function`: 'cosine'
}}

CREATE VECTOR INDEX artifact_summary_embedding IF NOT EXISTS
FOR (n:ArtifactSummary) ON (n.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: $dims,
  `vector.similarity_function`: 'cosine'
}}
```

**Provider-switch handling:** index is named/versioned by dims (e.g. `knowledge_item_embedding_384`), so switching embedding providers creates a new index and triggers the re-embedding job (see App Flow §11) rather than corrupting the existing one. Old index dropped after successful backfill.

### 2.4 Workspace Isolation

All Cypher queries scoped with `WHERE n.workspace_id = $workspace_id` — enforced at the `neo4j_graph.py` service layer, mirroring the SQLite JWT-workspace scoping pattern, never left to the frontend.

---

## 3. Provider Metadata Table *(new, small reference table)*

### 3.1 `provider_configs`

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| workspace_id | UUID FK | |
| provider_type | TEXT | `llm` \| `embedding` |
| provider_name | TEXT | `ollama` \| `openai` \| `anthropic` \| `local_sentence_transformer` |
| model_name | TEXT | e.g. `llama3.1:8b-instruct-q4_K_M` |
| config_json | JSON | provider-specific settings (host, base_url) — **never stores raw API keys** |
| api_key_ref | TEXT NULL | reference to encrypted secret store, not the key itself |
| is_active | BOOLEAN | |
| created_at | DATETIME | |

Keeps provider history/audit trail per workspace — useful for compliance-minded pilot orgs to prove which engine touched which data, when.
