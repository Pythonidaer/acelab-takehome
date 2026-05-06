# Acelab Take-Home: Material Recommendation Agent

Acelab is building the definitive platform for material intelligence in the built environment. Architects and designers use our platform to find, evaluate, and select building materials across thousands of products.

We're giving you access to our search API via a Python SDK. Your task is to build an AI agent that helps architects find the right materials for their projects.

## The Challenge

Build an agent that takes a natural language description of a project or space and returns ranked material recommendations with reasoning.

**Example input:**
> "High-traffic hospital corridor that needs to meet infection control standards,
> LEED Silver minimum, and a calming aesthetic. Budget is mid-range."

**Your agent should:**

1. Analyze the request and identify what to search for — material types, performance criteria, certifications, manufacturers, etc.
2. Make multiple, targeted calls to the Acelab SDK to gather relevant products, materials, and certifications
3. Synthesize results into ranked recommendations that explain *why* each product fits — not just a list of search results

The key differentiator is **multi-step reasoning**. A good agent doesn't just forward the user's input as a single search query. It decomposes, searches across multiple dimensions, cross-references, and synthesizes.

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Install

```bash
# Copy env and fill in your keys (provided separately)
cp .env.example .env

# Install dependencies
uv sync
```

### Verify Setup

Run the example script to confirm your API connection:

```bash
uv run python examples/basic_usage.py
```

You should see search results printed for each endpoint. If you get auth errors, double-check your `.env` values.

## Acelab SDK

The `acelab/` directory contains our Python SDK. **Do not modify it.**

### Available Methods

| Method | Description |
|---|---|
| `client.search(query)` | Semantic search across the full product catalog |
| `client.materials.search(query)` | Search material types (e.g., "vinyl", "quartz") |
| `client.certifications.search(query)` | Search certifications (e.g., "LEED", "FSC") |
| `client.companies.search(query)` | Search manufacturers and brands |
| `client.taxonomy.search(category)` | Classify into product taxonomy |
| `client.deduplicate(name=, supplier=)` | Find duplicate products |

All search methods return results with `similarity_score` (0.0–1.0) and support `limit` and `offset` params. See `examples/basic_usage.py` for full usage of every method.

### Sync vs Async

```python
from acelab import Acelab, AsyncAcelab

# Synchronous
client = Acelab(api_key="...", base_url="...")
results = client.search("porcelain tile")

# Asynchronous (use as context manager)
async with AsyncAcelab(api_key="...", base_url="...") as client:
    results = await client.search("porcelain tile")
```

## Requirements

- Python backend using an LLM for orchestration and reasoning
- Must use the Acelab SDK to query real data (don't mock it)
- The agent must make multiple API calls — decompose the problem, don't just pipe input to a single search
- An OpenRouter API key is provided — use any model available there

### Interface

Pick one or more — your choice:
- Chat-style web UI
- Form-based web app
- CLI or TUI
- Async PDF report
- Something else entirely

We care more about the agent logic than the interface polish.

## Evaluation

| Criteria | What we're looking for |
|---|---|
| **Agent design** | How you decompose a vague request into structured API calls |
| **LLM integration** | Effective use of tool calling, structured output, or prompting |
| **Code quality** | Clean, well-structured, easy to run |
| **Product thinking** | Are the recommendations actually useful to an architect? |
| **Documentation** | Can we clone it and run it in under 2 minutes? |

**What we're NOT evaluating:** UI polish, test coverage (though it's a plus), specific framework choices.

## Time Budget

5–10 hours. We'd rather see a focused, working system than a polished but incomplete one. Scope ruthlessly.

## Using AI

We're an AI-native company. We expect you to use AI tools in your work — Claude Code, Cursor, ChatGPT, whatever makes you most productive. Using AI well is a skill we value, not something to hide.

## Solution: material recommendation agent

### How to run

Prerequisites: copy `.env.example` to `.env` and fill `ACELAB_API_KEY`, `ACELAB_BASE_URL`, and `OPENROUTER_API_KEY`. Optionally set `OPENROUTER_MODEL` (defaults to `openai/gpt-4o-mini` on [OpenRouter](https://openrouter.ai/)).

```bash
uv sync
uv run examples/basic_usage.py   # optional: sanity-check Acelab connectivity
uv run material-agent "High-traffic hospital corridor, infection control, LEED Silver, calming aesthetic, mid-range budget."
uv run material-agent --trace "…"   # log each SDK tool call on stderr; JSON still on stdout
# or: uv run python -m material_agent <<< "your multi-line brief"
```

The CLI prints a JSON report: executive summary, constraints, search strategy, ranked recommendations (with `product_id` and evidence-backed `reasoning`), and caveats. Recommendations are **grounded**: every `product_id` must come from a `search_products` tool result in that run (the agent will repair itself if the model invents IDs).

### Approach

- **Orchestration:** OpenRouter chat completions with **function calling**; the model plans multiple **narrow** SDK queries instead of one broad product search.
- **Tools (real `AsyncAcelab` calls):** `search_products`, `search_materials`, `search_certifications`, `search_companies`, and `classify_taxonomy` — each wraps the vendored SDK with typed responses serialized back to the model.
- **Output:** Structured JSON (`pydantic`-validated). Each `product_id` in `recommendations` must appear in a
  `search_products` response in the same run; otherwise the agent gets an automatic **grounding repair** turn.
- **`--trace`:** Logs each tool call to stderr for debugging.
- **Async:** `AsyncAcelab` is used inside `asyncio` so the agent never blocks an event loop with the sync client.

### Future improvements

- Explicit **budget / performance rubric** in the schema (e.g. cost band, slip resistance, VOC) with retrieval for each criterion.
- **Caching** of tool results per session to cut latency and tokens.
- **Web or TUI** for iterative refinement.

## Submission

Push your work to this repo. Work however you're comfortable — branching, committing to main, whatever. We'll review the final state of the repo and your git history.

Please include a short section (in this README or a separate doc) covering:
- How to run your solution
- Your approach and key design decisions
- What you'd improve with more time