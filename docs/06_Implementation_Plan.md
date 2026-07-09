# Implementation Plan
## Knowledge Hubs — Local-First Rollout

**Version:** 1.0
**Status:** Draft

---

## 1. Guiding Constraint

Ship in phases that each leave the system in a **fully working, demoable state**. Never merge a phase that breaks the "no API key required" claim, even temporarily.

## 2. Phase 0 — Baseline (current state)

- Existing regex extractor, OpenAI-dependent transcript extraction and GraphRAG, SQLite + Neo4j storage, Angular frontend.
- **Deliverable:** documented as-is architecture (done via TRD).

## 3. Phase 1 — Provider Abstraction Layer (foundation)

**Goal:** introduce the `LLMProvider` / `EmbeddingProvider` interfaces without changing default behavior yet.

- Define abstract interfaces (TRD §2.1, §2.2).
- Wrap existing OpenAI calls in `OpenAIProvider` / `OpenAIEmbeddingProvider` implementations.
- Refactor `llm_extraction.py`, `graphrag.py`, `neo4j_graph.py` embedding calls to go through the interface instead of calling OpenAI directly.
- No behavior change yet — default provider is still OpenAI at end of this phase.
- **Deliverable:** all AI calls in the codebase route through the abstraction; test suite passes unchanged.
- **Est. effort:** 1–1.5 weeks.

## 4. Phase 2 — Local Embeddings

**Goal:** ship `LocalSentenceTransformerProvider`, make it the default.

- Add `sentence-transformers` dependency, implement provider (`all-MiniLM-L6-v2` default).
- Add `embedding_provider` / `embedding_dims` columns (SQLite migration).
- Version Neo4j vector indexes by dimension (TRD §5.3 / Schema §2.3).
- Write re-embedding job for provider switches (App Flow §11).
- Flip default `EMBEDDING_PROVIDER=local` in `.env.example`.
- **Deliverable:** search, cross-linking, and GraphRAG retrieval work with zero API key.
- **Est. effort:** 1.5–2 weeks.

## 5. Phase 3 — Local LLM (Ollama Integration)

**Goal:** ship `OllamaProvider`, make it the default for extraction and GraphRAG.

- Add `ollama` service to `docker-compose.yml` with health check.
- Implement `OllamaProvider` against Ollama's HTTP API, including JSON-mode/structured-output handling (prompt-engineered, since not all local models support native function calling as reliably as OpenAI).
- Tune prompts per pipeline stage (extraction, query transform, rerank, generation) specifically for the recommended local model — local models often need more explicit formatting instructions than GPT-4-class models.
- Add local classifier fallback for query routing (embedding-similarity based) to reduce LLM calls per query (TRD §4).
- Flip default `LLM_PROVIDER=ollama`.
- **Deliverable:** full ingestion + GraphRAG cycle works end-to-end offline, no API key required at any point.
- **Est. effort:** 2.5–3 weeks (prompt tuning is the long pole here).

## 6. Phase 4 — Data Model & Backend Hardening

- Add `workspaces` and `provider_configs` tables (Schema §1.2, §3.1).
- Add `extraction_engine`, `llm_provider`, `latency_ms` tracking columns.
- Backfill migration for existing workspace-scoped rows.
- Implement `ALLOW_CLOUD_PROVIDERS` admin kill-switch, enforced server-side.
- **Deliverable:** provenance and policy fully tracked; admins can hard-disable cloud providers.
- **Est. effort:** 1 week.

## 7. Phase 5 — UI/UX Updates

- Provider status badge + Model & Privacy panel (UI/UX §2.1–2.2).
- Model Manager page with install/progress UI (UI/UX §2.3).
- Onboarding wizard (App Flow §1).
- Ingest panel provider hint, Review queue engine badges, GraphRAG progressive status text.
- **Deliverable:** local-first story is visible and legible in the product, not just true under the hood.
- **Est. effort:** 2 weeks.

## 8. Phase 6 — Testing & Validation

- "Airplane mode" integration test: full cycle with network disabled, must pass (TRD §7).
- Hardware-tier benchmarking: run ingestion + GraphRAG on min/recommended tiers, record actual latency against TRD §5.2 targets.
- Extraction quality regression suite: compare regex vs. local LLM vs. cloud LLM output on a fixed test document set, track review-queue accept rates per engine.
- **Deliverable:** performance and quality numbers to back up PRD success metrics with real data, not estimates.
- **Est. effort:** 1.5 weeks.

## 9. Phase 7 — Pilot & Real-World Validation

- Recruit 2–3 design partners matching PRD personas (at least one regulated/offline-constrained org).
- Package fully offline install method (pre-pulled images + model weights transfer, TRD §6).
- Collect: setup friction, latency tolerance, extraction accept-rate, and — critically — whether the local-first claim actually removed their original blocker (legal/compliance/connectivity).
- **Deliverable:** case study / validation writeup feeding back into PRD §6 metrics and future roadmap.
- **Est. effort:** 3–4 weeks (mostly partner-paced, not engineering-paced).

## 10. Timeline Summary

| Phase | Focus | Est. Duration |
|---|---|---|
| 1 | Provider abstraction | 1–1.5 wk |
| 2 | Local embeddings | 1.5–2 wk |
| 3 | Local LLM (Ollama) | 2.5–3 wk |
| 4 | Data model hardening | 1 wk |
| 5 | UI/UX updates | 2 wk |
| 6 | Testing & validation | 1.5 wk |
| 7 | Pilot & real-world validation | 3–4 wk |
| **Total** | | **~13–16 weeks** (single engineer pace; parallelizable across phases 4–5 with a second contributor) |

## 11. Sequencing Risks

- **Phase 3 (Ollama prompt tuning) is the highest-risk, highest-variance phase.** Local models are noticeably less reliable at structured JSON output than GPT-4-class models; budget extra time here rather than compressing it to hit a date.
- **Don't start Phase 5 (UI) before Phase 3 is functionally stable** — building "Local · llama3.1:8b" badges around a pipeline that isn't actually reliable yet undermines the pitch it's meant to support.
- **Phase 7 should not be gated behind 100% feature completeness** — a design partner in a regulated environment will validate the core claim (works without sending data out) even if Should-Have features like the Model Manager UI aren't finished yet.
