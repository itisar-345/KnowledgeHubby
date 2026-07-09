# Technical Requirements Document (TRD)
## Knowledge Hubs — Local-First Architecture

**Version:** 1.0
**Status:** Draft

---

## 1. Architecture Principle

**Local is the default execution path for every AI-dependent feature. Cloud providers are pluggable adapters behind a common interface, never a hard dependency.**

```
                        ┌─────────────────────────┐
                        │      FastAPI Backend      │
                        └───────────┬───────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
          ┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
          │ LLMProvider  │   │ EmbeddingProv. │   │  Storage    │
          │  interface   │   │   interface    │   │ (SQLite +   │
          └──────┬──────┘   └───────┬───────┘   │  Neo4j)     │
                 │                  │            └─────────────┘
       ┌─────────┴───────┐  ┌───────┴────────┐
       │                 │  │                │
┌──────▼──────┐  ┌───────▼──▼───┐   ┌────────▼────────┐
│ LocalOllama  │  │ CloudOpenAI  │   │ LocalSentence-   │
│  Provider    │  │  Provider    │   │ Transformers     │
│ (default)    │  │  (optional)  │   │ Provider(default)│
└─────────────┘  └──────────────┘   └──────────────────┘
```

## 2. Provider Abstraction Layer

### 2.1 LLM Provider Interface

```python
class LLMProvider(ABC):
    async def complete(self, prompt: str, system: str = "", json_mode: bool = False) -> str: ...
    async def complete_structured(self, prompt: str, schema: dict) -> dict: ...
    @property
    def is_local(self) -> bool: ...
    @property
    def name(self) -> str: ...
```

Implementations:
- `OllamaProvider` (default) — talks to a local Ollama daemon over `localhost:11434`. No network egress.
- `OpenAIProvider` (optional) — existing `gpt-4o-mini` integration, used only if a key is present and the workspace policy allows it.
- `AnthropicProvider` (optional) — same pattern, for teams that prefer Claude via API.

### 2.2 Embedding Provider Interface

```python
class EmbeddingProvider(ABC):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int: ...
```

Implementations:
- `LocalSentenceTransformerProvider` (default) — `sentence-transformers/all-MiniLM-L6-v2` (384-dim) or `bge-small-en-v1.5`, run via `sentence-transformers` in-process. CPU-friendly.
- `OpenAIEmbeddingProvider` (optional) — `text-embedding-3-small`, used only when explicitly enabled.

**Note:** Neo4j vector index dimensionality must match the active embedding provider. Vector index is created per-provider-signature so switching providers doesn't silently corrupt search (see §5.3).

### 2.3 Provider Resolution & Config

Config precedence (highest wins): workspace admin policy → `.env` → built-in default (local).

```env
# .env.example (relevant additions)
LLM_PROVIDER=ollama            # ollama | openai | anthropic
EMBEDDING_PROVIDER=local        # local | openai
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b-instruct-q4_K_M
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
OPENAI_API_KEY=                 # optional, only used if LLM_PROVIDER=openai
ALLOW_CLOUD_PROVIDERS=true      # admin kill-switch, false = hard local-only
```

## 3. Local Model Requirements

### 3.1 LLM (generation, extraction, reranking, query transform)

| Tier | Model | RAM | Use case |
|---|---|---|---|
| Minimum | `llama3.2:3b-instruct-q4` | ~4GB | Low-resource laptops, extraction only |
| Recommended | `llama3.1:8b-instruct-q4_K_M` | ~8GB | Default balanced tier |
| High-accuracy | `qwen2.5:14b-instruct-q4` or `llama3.1:70b` (if GPU available) | 16GB+/GPU | Power users, servers |

Served via **Ollama** (simplest local-inference story, handles quantization, model pulling, and a stable HTTP API). Alternative considered: `llama.cpp` server directly — rejected for v1 due to more manual setup burden on non-technical users.

### 3.2 Embeddings

- Default: `all-MiniLM-L6-v2` (384 dims, ~80MB, fast on CPU) via `sentence-transformers`, run in-process in the FastAPI backend (no separate service needed).
- Upgrade path: `bge-base-en-v1.5` (768 dims) for better retrieval quality at higher compute cost.

### 3.3 Hardware Baseline

- **Minimum supported:** 4-core CPU, 8GB RAM, no GPU — runs on `llama3.2:3b` tier, extraction + basic Q&A functional, GraphRAG generation slower (~20-30s/query acceptable).
- **Recommended:** 8-core CPU, 16GB RAM — `llama3.1:8b` tier, GraphRAG under 15s/query.
- **GPU optional:** if CUDA/Metal available, Ollama auto-offloads layers; no code changes required.

## 4. GraphRAG Pipeline — Local Adaptation

The existing 8-stage pipeline is preserved; each LLM/embedding call is routed through the provider interfaces:

1. Query transformation (sub-queries + HyDE) — local LLM, shorter prompt budget to keep latency reasonable.
2. Query routing (intent classification) — can run as a **local, non-LLM classifier** (keyword/embedding-similarity based) to save a full generation call; falls back to LLM classification if ambiguous.
3. Fusion retrieval — local embeddings + Neo4j vector index (or SQLite cosine fallback), RRF unchanged.
4. Summary index injection — unchanged, summaries generated by local LLM at ingestion time.
5. Graph expansion — unchanged (pure graph traversal, no model call).
6. Reranking — local LLM scoring; batch candidates into a single prompt to minimize round-trips.
7. Context assembly — unchanged.
8. Generation — local LLM; **streaming response** recommended to offset higher local latency with perceived responsiveness.

**Performance guardrail:** cap total pipeline LLM calls per query (transform + route + rerank + generate) at 4 by default in local mode, vs. current unrestricted sub-query fan-out, to keep local latency acceptable. Configurable per deployment.

## 5. Non-Functional Requirements

### 5.1 Privacy / Network

- With `ALLOW_CLOUD_PROVIDERS=false`, the backend must make **zero outbound network calls** during normal operation (verified via network-isolated integration test — "airplane mode" CI job).
- Model downloads (Ollama pulling a model, sentence-transformers first-run download) are a one-time, explicit, user-initiated action — never automatic in the background.

### 5.2 Performance

- Ingestion (regex path): < 2s for a 5,000-word document.
- Ingestion (local LLM path): < 20s for a 5,000-word transcript on recommended-tier hardware.
- GraphRAG query: < 15s p50 on recommended tier, < 30s p95.

### 5.3 Data Integrity

- Embedding provider signature (`provider_name:model_name:dimensions`) stored alongside each vector. Switching providers triggers a **re-embedding job** rather than silently mixing incompatible vector spaces.
- Neo4j vector index recreated (not altered in place) when dimensionality changes.

### 5.4 Reliability / Degradation Order

1. Neo4j unreachable → SQLite cosine + BM25 fallback (existing behavior, preserved).
2. Ollama unreachable → clear error surfaced in UI ("Local model service not running"), not a silent fallback to cloud (avoids accidental data exfiltration).
3. Cloud provider selected but unreachable/rate-limited → clear error, **no automatic fallback to local** without explicit user action (avoids silent quality changes mid-session without user awareness) — configurable.

### 5.5 Security

- JWT auth, workspace scoping — unchanged from current implementation.
- Cloud API keys, if used, stored server-side only (never sent to frontend), encrypted at rest.
- Admin-level `ALLOW_CLOUD_PROVIDERS` flag enforced server-side, not just hidden in UI.

## 6. Deployment

- `docker-compose.yml` extended with an `ollama` service (official Ollama image), health-checked before backend starts.
- Fully offline install path: Docker images + model weights can be pre-pulled and shipped via `docker save` / `ollama pull` on a connected machine, then transferred to an air-gapped one — documented as a supported install method.
- Existing `neo4j`, `backend`, `frontend` services unchanged in shape, just gain the new provider config env vars.

## 7. Testing Requirements

- Unit tests for both `OllamaProvider` and `OpenAIProvider` against the same interface contract (shared test suite, swappable fixture).
- Integration test: full ingestion → extraction → GraphRAG query cycle with network disabled, `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=local` — must pass with zero network calls.
- Regression test: extraction output schema parity between regex, local LLM, and cloud LLM paths (same shape, may differ in content quality).
