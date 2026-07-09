# UI/UX Design Document
## Knowledge Hubs — Local-First Experience

**Version:** 1.0
**Status:** Draft

---

## 1. Design Principles

1. **Show the provider, always.** The user should never wonder "did that just leave my machine?" Every AI-touched surface shows a Local / Cloud badge.
2. **Local is the default and the "safe" choice, not the degraded one.** Avoid language like "fallback mode" or "limited mode" for local — that undersells the pitch. Cloud is the "enhanced, optional" mode.
3. **Set latency expectations honestly.** Local inference is slower; show progress, not a spinner that implies something's broken.
4. **No dead ends.** If a local model isn't installed yet, guide the user to install one in 1-2 clicks rather than failing silently.

## 2. Global UI Elements

### 2.1 Provider Status Badge (persistent, top navbar)

```
┌───────────────────────────────────────┐
│  Knowledge Hubs      🟢 Local · llama3.1:8b   [Hub] [Search] [Review] [GraphRAG]  👤 │
└───────────────────────────────────────┘
```
- 🟢 Local — green, "fully offline" reassurance.
- 🔵 Cloud (OpenAI) — blue, distinct color so it's never mistaken for local.
- 🔴 Not configured — red, links directly to setup.
- Clicking the badge opens the **Model & Privacy panel** (§2.2).

### 2.2 Model & Privacy Panel (slide-over, from navbar badge)

- Current LLM provider + model, current embedding provider + model.
- Toggle: "Allow cloud providers for this workspace" (admin-only, off by default).
- "Download a local model" button → opens Model Manager (§2.3).
- Link: "What data ever leaves this device?" → static explainer page, plain language, no marketing spin.

### 2.3 Model Manager (new page, `/settings/models`)

- List of recommended local models with size, RAM requirement, and a one-click "Install" (triggers `ollama pull` server-side, progress bar).
- Currently installed models, with "Set as default" and "Remove" actions.
- Clear hardware-tier guidance inline: "Your system has 16GB RAM — recommended tier: llama3.1:8b."

## 3. Key Screens (building on existing Angular pages)

### 3.1 Knowledge Hub (`/knowledge`) — unchanged core, additive elements

```
┌────────────────────────────────────────────────────────┐
│ Ingest Panel                                             │
│  [Text] [File] [URL] [Transcript]                       │
│  ┌──────────────────────────────────────────────────┐   │
│  │  paste text / drop file...                        │   │
│  └──────────────────────────────────────────────────┘   │
│  ⓘ Transcript mode uses your local model (llama3.1:8b)  │
│  [ Extract Knowledge ]                                  │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ Knowledge Grid            [Filter: type ▾] [Filter: tag▾]│
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │
│  │Decision│ │  Risk  │ │Lesson  │ │Checklist│            │
│  └────────┘ └────────┘ └────────┘ └────────┘            │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ Knowledge Graph (SVG canvas)                             │
└────────────────────────────────────────────────────────┘
```
- New: inline provider hint under the ingest panel so users always know which engine will process their paste, *before* they submit — important for trust when handling sensitive text.

### 3.2 GraphRAG Chat (`/graphrag`)

```
┌────────────────────────────────────────────────────────┐
│ 🟢 Local · llama3.1:8b            [Top-K: 8 ▾] [History]│
├────────────────────────────────────────────────────────┤
│  You: What decisions did we make about the auth system? │
│                                                          │
│  Assistant: [thinking… retrieving context]  ~6s          │
│  Based on 3 sources, the team decided to use JWT-based  │
│  auth with workspace scoping [1][2].                     │
│  ▸ View context nodes (3)                                │
├────────────────────────────────────────────────────────┤
│  [ Ask a question...                          ] [Send]  │
└────────────────────────────────────────────────────────┘
```
- **Progressive status text** during the 8-stage pipeline (e.g. "Rewriting your question…" → "Searching knowledge graph…" → "Ranking results…" → "Generating answer…") instead of a bare spinner — makes local latency feel purposeful rather than broken.
- Context node inspector unchanged from existing design.

### 3.3 Review Queue (`/review`)

- Unchanged interaction model (accept/reject/edit).
- New: badge on each item showing which engine extracted it (Regex / Local LLM / Cloud LLM) — helps reviewers calibrate trust per item, and surfaces real-world accuracy differences over time.

### 3.4 Search (`/search`)

- Unchanged; local embeddings mean search "just works" with no setup beyond initial model install.

### 3.5 Onboarding (new, first-run only)

```
Step 1: Welcome — "Knowledge Hubs runs fully on your machine. No API key needed."
Step 2: Install a local model (Model Manager, pre-selected recommended tier based on detected RAM)
Step 3: (Optional, skippable) Add a cloud API key for enhanced answers
Step 4: Create workspace → done
```
- Cloud setup is explicitly optional and skippable, reinforcing the local-first pitch from the very first screen.

## 4. Copy / Tone Guidelines

- Never use "offline mode" or "degraded" for local — use "Local" plainly, as the default state.
- When cloud is unavailable/unset, don't show error-red language — show it as simply "not configured," neutral tone.
- Any place that shows latency, pair it with a one-line reason ("Generating locally — no data leaves this device") so slowness reads as a feature tradeoff, not a bug.

## 5. Accessibility

- Provider badges use both color and icon/text (not color alone) for colorblind users.
- Progressive status text in GraphRAG chat is screen-reader announced via `aria-live="polite"`.
