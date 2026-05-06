# Material Recommendation Agent

**Submission — Jonathan Hammond.** This repository is my solution to Acelab’s **material recommendation agent** take-home: a Python backend using an LLM for orchestration, **real SDK calls** (no mocks), **multi-step decomposition** instead of one-shot search, and **structured ranked output** with reasoning.

## Table of contents

**How to run**

- [Prerequisites](#prerequisites)
- [Install](#install)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)

**SDK & integration**

- [Acelab SDK](#acelab-sdk) — method overview; [Sync vs async](#sync-vs-async)

**Challenge write-up**

- [Approach and key design decisions](#approach-and-key-design-decisions)
- [Development process](#development-process)
- [Domain guardrail](#domain-guardrail)
- [What I would improve with more time](#what-i-would-improve-with-more-time)

---

An LLM-orchestrated assistant that reads a natural-language **architectural or interior** project brief and returns **ranked product recommendations with reasoning**, using the vendored **Acelab Python SDK** (real API calls, no mocks) and **OpenRouter** for chat + **function calling**. The agent plans **multiple targeted SDK lookups**—products, materials, certifications, manufacturers, taxonomy, and optional duplicate checks—rather than stuffing the entire brief into a single catalog search.

Each run returns **validated JSON** (Pydantic): executive summary, constraints, search narrative, ranked rows with `reasoning`, and **caveats**. Recommended **`product_id` values must come from `search_products` hits in that same run**; if the model invents or miscopies IDs, a **grounding repair** loop injects feedback and retries (`material_agent/agent.py`). A **domain heuristic** rejects clearly off-topic prompts before any OpenRouter or Acelab work (`material_agent/domain_guard.py`).

**Interfaces:** **`material-agent` CLI** (primary), optional **React + Vite** UI with **FastAPI SSE** (`material_agent/server.py`, `web/`).

---

## Prerequisites

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) for dependencies
- **Optional — web UI:** Node.js **18+** and npm

## Install

```bash
cp .env.example .env
# Set ACELAB_API_KEY, ACELAB_BASE_URL, OPENROUTER_API_KEY (optional: OPENROUTER_MODEL — see material_agent/config.py)

uv sync
# Optional FastAPI backend for the web UI:
uv sync --extra web
# Optional dev tools:
uv sync --extra dev --extra web
```

## Quick start

1. Configure `.env` as above (`OPENROUTER_MODEL` defaults to `openai/gpt-4o-mini` on OpenRouter unless set).
2. *(Optional)* Check Acelab connectivity:  
   `uv run python examples/basic_usage.py`
3. Run the agent (JSON on **stdout**):  
   `uv run material-agent "High-traffic hospital corridor, infection control, LEED Silver, calming aesthetic, mid-range budget."`
4. Inspect tool/SDK activity (**stderr**):  
   `uv run material-agent --trace "your brief"`

**Optional web UI** — two terminals:

```bash
# Terminal 1
uv run material-agent-api

# Terminal 2
cd web && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Use **Show agent trace** in the UI for a combined tool log after the run completes.

---

## CLI reference

Environment variables load via `python-dotenv` in `material_agent/config.py`.

```bash
uv run python examples/basic_usage.py

uv run material-agent "Single-line brief."

uv run material-agent --trace "…"

# Dedup workflow (evidence-only) plus grounded recommendations:
uv run material-agent --trace "Check whether a product like 'Quartz Countertop - White' from Caesarstone may already exist in the catalog, then recommend similar quartz surfaces for a healthcare reception desk that needs durability, cleanability, and a bright neutral aesthetic."

# Multi-line stdin (bash/zsh):
uv run python -m material_agent <<< $'First line.\nSecond line.'
```

Dedup results from `deduplicate_product` inform narrative only; **`product_id` in rankings still must come from `search_products`** in that run.

---

## Acelab SDK

The **`acelab/`** directory ships the upstream SDK; **`material_agent`** only calls into it (no edits under `acelab/`).

| Method | Role |
|---|---|
| `client.search(query)` | Product catalog semantic search |
| `client.materials.search(query)` | Material types |
| `client.certifications.search(query)` | Certifications |
| `client.companies.search(query)` | Brands / manufacturers |
| `client.taxonomy.search(...)` | Taxonomy classification |
| `client.deduplicate(name=..., supplier=...)` | Duplicate / near-match candidates |

Search-style methods support `similarity_score` and `limit` / `offset`. See **`examples/basic_usage.py`** for a full pass over every endpoint.

### Sync vs async

The example script uses the synchronous **`Acelab`** client. The agent runtime uses **`AsyncAcelab`** inside `asyncio` so waits don’t block an event loop.

```python
from acelab import Acelab, AsyncAcelab

client = Acelab(api_key="...", base_url="...")
results = client.search("porcelain tile")

async with AsyncAcelab(api_key="...", base_url="...") as client:
    results = await client.search("porcelain tile")
```

---

## Approach and key design decisions

Focused on **multi-step retrieval and synthesis**, not a large application surface.

- **CLI first** — Easiest path to run, diff, or grade the agent; JSON in / JSON out.
- **Small web layer** — Form + streaming status for demos; same `run_agent` as the CLI.
- **Tool orchestration** — OpenRouter function calling drives **`search_products`**, **`search_materials`**, **`search_certifications`**, **`search_companies`**, **`classify_taxonomy`**, and **`deduplicate_product`** (`material_agent/toolkit.py` → real `AsyncAcelab` calls).
- **Decomposed queries** — Briefs are broken into several narrow searches (space type, performance, sustainability, aesthetics, named brands) instead of one vague catalog query.
- **Grounded IDs** — Final recommendations only reference product IDs observed in **`search_products`** tool results for that run; otherwise a **repair** message feeds the catalog snapshot back into the model.
- **`--trace` / UI trace** — Makes the tool loop legible (`material_agent/agent.py`; SSE aggregates trace lines into the **complete** event when enabled).
- **Structured output** — Pydantic report schema for predictable parsing downstream.

---

## Development process

Scope, task breakdown, and early prompting were iterated in **ChatGPT**. Core Python (agent, tools, grounding, SSE API) was implemented in **Cursor** with repo norms in **`.cursorrules`**. The optional UI shell came from **ChatGPT** prompting plus **[Lovable](https://lovable.dev/)**, then wired to this codebase’s SSE stream and payload shapes.

---

## Domain guardrail

Clearly **non-architectural** prompts (consumer tech tropes, dev tutorials without building context, etc.) short-circuit to a polite JSON-shaped report — **no** OpenRouter and **no** `search_products`. Logic is keyword heuristics with **whole-word** checks for ambiguous tokens (for example **`react`** does not trip on **`reactive`** in coatings). If the brief carries normal **space/material/spec** cues — floors, LEED, corridors, renovations, coatings, etc. — it stays eligible even beside words like **office** or **software**.

---

## What I would improve with more time

- Stronger **intent routing** instead of purely heuristic rejection (including an explicit **needs clarification** path).
- **Clarifying questions** before searching when constraints are vague.
- A published **ranking rubric** (cost, durability, maintenance, sustainability, aesthetics, availability, risk) backed by retrieval per axis.
- **Richer citations** tying each recommendation to specific SDK fields.
- Better **supplier / near-duplicate** collapse in ranked lists.
- **Session caching** for repeated tool calls.
- Hardening **SSE / empty-state / error** paths in the UI.
- **Tests** around grounding, domain guard, JSON parsing, and `dispatch_tool`.
