# Product Requirements Document (PRD)
## Knowledge Hubs — Local-First Organizational Memory

**Version:** 1.0
**Status:** Draft
**Owner:** [Your name]

---

## 1. Problem Statement

Every team generates knowledge — decisions, risks, lessons learned, checklists, how-to patterns — and almost none of it survives past the meeting it was created in. It's buried in Slack threads, retro docs, and meeting notes that nobody re-reads. Existing "AI knowledge base" tools solve this by piping everything through a cloud LLM, which is a non-starter for a large chunk of organizations:

- **Regulated industries** (healthcare, legal, finance, government) often cannot legally send internal documents to third-party APIs.
- **Air-gapped or high-security environments** (defense, critical infrastructure, some enterprise IT) have no internet egress at all.
- **Cost-sensitive orgs** (schools, nonprofits, early-stage teams) can't justify recurring per-token API bills for something as basic as "search our own notes."
- **Data-sovereignty-conscious teams** simply don't want their institutional knowledge — including sensitive decisions — sitting in a third party's logs.

For all of these groups, "just use ChatGPT to summarize your docs" is not an option. They're left with either doing nothing (knowledge dies) or building brittle internal wikis that nobody maintains.

## 2. Vision / Pitch

**Knowledge Hubs is a local-first knowledge extraction and retrieval system that works completely offline, with no API key required, and gets better if you choose to plug in a cloud model.**

The default experience — extraction, storage, search, and question-answering — runs entirely on the user's own machine or server, using local models. Cloud LLMs are an opt-in enhancement for teams who want them, never a requirement for the tool to function.

This is the inversion of how most "AI-powered" tools are built today (cloud-first, offline as a crippled fallback). Here, local is the product; cloud is the upsell.

## 3. Target Users / Personas

| Persona | Context | Why local-first matters to them |
|---|---|---|
| **Compliance-bound team lead** (hospital ops, legal firm) | Handles PHI/PII/privileged docs | Cannot legally use cloud LLMs on this data |
| **Security engineer at a regulated enterprise** | Air-gapped or VPN-only network | No API egress possible at all |
| **Nonprofit / school program manager** | Small budget, high document volume | Can't sustain per-query API costs |
| **Open-source / self-hosting enthusiast** | Runs personal infra | Wants ownership of data and stack, no vendor lock-in |
| **Startup team (secondary)** | Wants convenience | Will happily plug in an API key if it improves answer quality |

## 4. Goals

1. Deliver decision/risk/lesson/checklist extraction that works with **zero external API calls**.
2. Deliver semantic search and question-answering (GraphRAG) that works **fully offline**, using local embedding and generation models.
3. Make cloud LLM/embedding providers a **pluggable, optional upgrade**, not a dependency baked into the core pipeline.
4. Be deployable in **under 15 minutes** via Docker Compose on a laptop or single server, no internet required after image pull.
5. Preserve data ownership: all artifacts, extracted knowledge, and embeddings live in the user's own SQLite/Neo4j instance.

## 5. Non-Goals

- Not building a hosted multi-tenant SaaS in v1. Self-hosted only.
- Not competing on raw LLM answer quality with cloud-only tools — local models will lag GPT-4-class output. The pitch is availability and privacy, not best-in-class fluency.
- Not supporting real-time collaborative editing of knowledge items (single-workspace, async review workflow is sufficient).
- Not attempting full enterprise SSO/RBAC in v1 (JWT + workspace scoping is sufficient for initial real-world pilots).

## 6. Success Metrics

| Metric | Target |
|---|---|
| % of core features usable with zero API key | 100% |
| Time to first extracted knowledge item on a fresh local install | < 5 minutes |
| GraphRAG query latency, fully local mode, on commodity hardware (16GB RAM, no GPU) | < 15s per query |
| Pilot orgs in regulated/offline environments (design partners) | 3+ in first 2 quarters |
| Extraction precision (regex + local LLM combined) vs. human review | ≥ 75% accept rate in review queue |

## 7. Features

### 7.1 Must-Have (v1)

- **Local-first extraction**: regex extractor (existing) + local LLM extractor (new, via Ollama or equivalent) as the default path for transcript/Slack/email ingestion — no cloud call required.
- **Local embeddings**: replace OpenAI embeddings with a local sentence-embedding model (e.g. `all-MiniLM-L6-v2` or similar) as the default for vector search and cross-source linking.
- **Local GraphRAG**: query transformation, reranking, and answer generation all runnable against a local LLM, with graceful quality scaling (smaller/faster local model vs. larger local model vs. optional cloud model).
- **Provider abstraction layer**: a single interface (`LLMProvider`, `EmbeddingProvider`) so local (Ollama) and cloud (OpenAI, Anthropic, etc.) are interchangeable via config, not code changes.
- **Offline-mode indicator**: UI clearly shows which provider is active (Local / Cloud) per feature, and whether internet/API access is available.
- **Existing features preserved**: ingestion (text/file/URL/transcript), review queue, cross-source linking, playbooks, OKF import/export, graph visualization.

### 7.2 Should-Have (v1.1)

- Model manager UI: pick/download local models (quantized GGUF via Ollama) from within the app.
- Per-workspace policy: admin can **disable cloud providers entirely** (hard privacy guarantee) or allow-list them.
- Local model performance presets (fast/low-RAM vs. accurate/high-RAM).
- Export/import full workspace as a portable bundle (SQLite + Neo4j dump) for air-gapped transfer.

### 7.3 Nice-to-Have (Later)

- On-device fine-tuning / adapter support for domain-specific extraction (e.g. clinical terminology).
- Multi-workspace federation without a central server.
- Browser extension for one-click Slack/webpage capture.

## 8. Key Risks & Assumptions

| Risk | Mitigation |
|---|---|
| Local LLMs produce lower-quality extraction/answers than GPT-4-class models | Set expectations clearly in UI/docs; allow optional cloud upgrade; invest in prompt tuning per local model |
| Local inference is slow on modest hardware | Ship sane defaults (small quantized models), document hardware tiers, allow async/background processing |
| Users assume "local-first" but framework still silently calls out to the internet somewhere (telemetry, model downloads) | Explicit "airplane mode" test in QA; document exactly what network calls occur and when |
| Local + cloud dual providers introduce config complexity | Single unified provider abstraction, sensible zero-config default (local) |

## 9. Real-World Impact Framing

This project's core impact claim: **it makes AI-assisted institutional knowledge management accessible to organizations that are currently locked out of that category entirely** because of privacy, compliance, connectivity, or cost — not because they don't need it, but because every existing tool assumes cloud access. Pilot targets should include at least one organization in a regulated or offline-constrained environment to validate this claim with real usage, not just architecture.
