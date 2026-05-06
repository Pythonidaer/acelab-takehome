from __future__ import annotations

import inspect
import json
import re
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from acelab import AsyncAcelab

from .config import OPENROUTER_BASE_URL, get_openrouter_model, require_env
from .domain_guard import brief_appears_in_scope, out_of_scope_agent_report
from .toolkit import TOOL_SPECS, dispatch_tool

SYSTEM_PROMPT = """You are an architect-facing materials consultant with access to Acelab search tools.

Your job:
1) Extract explicit and implicit constraints from the user's brief (space type, traffic, hygiene, acoustics,
   fire/safety, sustainability certifications, budget level, aesthetics, maintenance, regional norms).
2) Plan several *different* tool queries — not one mega-query. Use taxonomy classification when it helps
   align product language. Cross-check certifications and material families.
3) You MUST call `search_products` at least once before the final answer. Every recommendation's
   `product_id` must be **exactly** one of the `product_id` values returned by your `search_products` tool
   calls (character-for-character). Copy `manufacturer_product_name` to `product_name`, `supplier_name` to
   `supplier`, and `similarity_score` from the same row — do not invent catalog entries.
   Call `deduplicate_product` when the user asks whether a named item may already exist in the catalog or
   wants duplicate checking; candidate matches are **supporting evidence only** and do not unlock new
   `product_id`s for recommendations.
4) When you are done calling tools, respond with **ONLY** a single JSON object (no markdown fences, no prose)
   matching this shape:
{
  "executive_summary": "string",
  "key_constraints": ["string"],
  "search_strategy": "string describing the SDK calls you made and why",
  "recommendations": [
    {
      "rank": 1,
      "product_id": "string from search_products results",
      "product_name": "string",
      "supplier": "string or null",
      "similarity_score": 0.0,
      "reasoning": "2-5 sentences tying product attributes to the brief",
      "addresses": ["which constraints this option serves"]
    }
  ],
  "caveats": ["gaps, assumptions, or follow-ups for the designer"]
}
Rules:
- Include 3–7 recommendations unless the data is extremely thin; then explain in caveats.
- Do not fabricate certifications or brands not supported by tool outputs.
- reasoning must cite concrete signals (e.g. score, taxonomy, material notes) when available.
"""

TOOL_PROGRESS_LABELS: dict[str, str] = {
    "search_products": "Searching products",
    "search_materials": "Searching materials",
    "search_certifications": "Checking certifications",
    "search_companies": "Comparing manufacturers",
    "classify_taxonomy": "Classifying taxonomy",
    "deduplicate_product": "Checking catalog for duplicates",
}

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


async def _emit(on_event: ProgressCallback | None, payload: dict[str, Any]) -> None:
    if on_event is None:
        return
    out = on_event(payload)
    if inspect.isawaitable(out):
        await out


class ProductRecommendation(BaseModel):
    rank: int = Field(..., ge=1)
    product_id: str
    product_name: str
    supplier: str | None = None
    similarity_score: float | None = None
    reasoning: str
    addresses: list[str]


class AgentReport(BaseModel):
    executive_summary: str
    key_constraints: list[str]
    search_strategy: str
    recommendations: list[ProductRecommendation]
    caveats: list[str] = Field(default_factory=list)


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _parse_report(content: str) -> AgentReport:
    payload = _extract_json_text(content)
    return AgentReport.model_validate_json(payload)


def _merge_seen_products(seen: dict[str, dict[str, Any]], search_payload: dict[str, Any]) -> None:
    for row in search_payload.get("results", []):
        pid = row.get("product_id")
        if not isinstance(pid, str) or not pid:
            continue
        seen[pid] = {
            "product_id": pid,
            "manufacturer_product_name": row.get("manufacturer_product_name"),
            "supplier_name": row.get("supplier_name"),
            "similarity_score": row.get("similarity_score"),
        }


def _snapshot_catalog(seen: dict[str, dict[str, Any]], *, max_rows: int = 45) -> str:
    rows = list(seen.values())
    rows.sort(key=lambda r: -float(r.get("similarity_score") or 0.0))
    return json.dumps(rows[:max_rows], indent=2, default=str)


def _grounding_issues(report: AgentReport, seen: dict[str, dict[str, Any]]) -> list[str]:
    if not seen:
        return ["__no_product_search__"]
    bad: list[str] = []
    for rec in report.recommendations:
        if rec.product_id not in seen:
            bad.append(rec.product_id)
    return bad


def _grounding_user_message(issues: list[str], seen: dict[str, dict[str, Any]]) -> str:
    if issues == ["__no_product_search__"]:
        return (
            "You did not return any `search_products` tool results in this session. "
            "Call `search_products` one or more times with focused queries (different angles), "
            "then output the final JSON using only `product_id` values from those results."
        )
    catalog = _snapshot_catalog(seen)
    invalid = ", ".join(repr(i) for i in issues)
    return (
        f"These recommendation product_id values are NOT from your `search_products` results: {invalid}. "
        "Revise: either call `search_products` again to widen the candidate set, or fix the JSON so every "
        "`product_id` is copied exactly from the catalog below. Use the matching "
        "`manufacturer_product_name` as `product_name`, `supplier_name` as `supplier`, and the same "
        "`similarity_score`.\n\nCatalog from your tool results:\n"
        f"{catalog}"
    )


def _trace_print(verbose: bool, name: str, args_preview: str, payload: dict[str, Any]) -> None:
    if not verbose:
        return
    if name == "search_products":
        rows = payload.get("results") or []
        top = [r.get("manufacturer_product_name", "?") for r in rows[:4]]
        print(
            f"[trace] search_products({args_preview}) -> {len(rows)} rows; "
            f"sample: {', '.join(top)}",
            file=sys.stderr,
        )
        return
    if name in ("search_materials", "search_certifications", "search_companies"):
        n = len(payload.get("results") or [])
        print(f"[trace] {name}({args_preview}) -> {n} rows", file=sys.stderr)
        return
    if name == "classify_taxonomy":
        st = payload.get("match_status")
        print(f"[trace] classify_taxonomy({args_preview}) -> status={st}", file=sys.stderr)
        return
    if name == "deduplicate_product":
        cands = payload.get("candidates") or []
        n = len(cands)
        likely = 0
        if cands and isinstance(cands[0], dict) and "is_likely_duplicate" in cands[0]:
            likely = sum(1 for x in cands if x.get("is_likely_duplicate"))
            print(
                f"[trace] deduplicate_product({args_preview}) -> {n} candidates; likely dupes: {likely}",
                file=sys.stderr,
            )
        else:
            print(f"[trace] deduplicate_product({args_preview}) -> {n} candidates", file=sys.stderr)
        return
    print(f"[trace] {name}({args_preview})", file=sys.stderr)


def _format_trace_line(name: str, args_preview: str, payload: dict[str, Any]) -> str:
    ap = args_preview[:180]
    if name == "search_products":
        rows = payload.get("results") or []
        top = [r.get("manufacturer_product_name", "?") for r in rows[:4]]
        return (
            f"search_products({ap}) → {len(rows)} rows · " f"{', '.join(top)}"
        )
    if name in ("search_materials", "search_certifications", "search_companies"):
        n = len(payload.get("results") or [])
        return f"{name}({ap}) → {n} rows"
    if name == "classify_taxonomy":
        st = payload.get("match_status")
        return f"classify_taxonomy({ap}) → {st}"
    if name == "deduplicate_product":
        cands = payload.get("candidates") or []
        n = len(cands)
        if cands and isinstance(cands[0], dict) and "is_likely_duplicate" in cands[0]:
            likely = sum(1 for x in cands if x.get("is_likely_duplicate"))
            return f"deduplicate_product({ap}) → {n} candidates · likely dupes: {likely}"
        return f"deduplicate_product({ap}) → {n} candidates"
    if payload.get("error"):
        return f"{name}({ap}) → error: {payload['error']}"
    return f"{name}({ap})"


def _tool_summary(name: str, payload: dict[str, Any]) -> str:
    if payload.get("error"):
        return str(payload["error"])
    if name == "search_products":
        rows = payload.get("results") or []
        top = [str(r.get("manufacturer_product_name") or "?") for r in rows[:3]]
        return f"{len(rows)} matches · {', '.join(top)}{'…' if len(rows) > 3 else ''}"
    if name in ("search_materials", "search_certifications", "search_companies"):
        n = len(payload.get("results") or [])
        return f"{n} semantic matches"
    if name == "classify_taxonomy":
        return f"Taxonomy status: {payload.get('match_status', '?')}"
    if name == "deduplicate_product":
        cands = payload.get("candidates") or []
        if cands and isinstance(cands[0], dict) and "is_likely_duplicate" in cands[0]:
            likely = sum(1 for x in cands if x.get("is_likely_duplicate"))
            return f"{len(cands)} candidates · {likely} likely duplicate(s)"
        return f"{len(cands)} similar catalog entries"
    return "Done"


async def _tool_completed(
    *,
    verbose: bool,
    on_event: ProgressCallback | None,
    show_trace: bool,
    trace_capture: list[str] | None,
    name: str,
    args_preview: str,
    payload: dict[str, Any],
) -> None:
    _trace_print(verbose, name, args_preview, payload)
    line = _format_trace_line(name, args_preview, payload)
    if trace_capture is not None:
        trace_capture.append(line)
    if on_event is not None:
        await _emit(
            on_event,
            {
                "kind": "tool",
                "tool": name,
                "label": TOOL_PROGRESS_LABELS.get(name, name),
                "args_preview": args_preview[:200],
                "summary": _tool_summary(name, payload),
            },
        )
    if show_trace and on_event is not None:
        await _emit(
            on_event,
            {
                "kind": "trace",
                "message": line,
            },
        )


async def run_agent(
    user_prompt: str,
    *,
    max_tool_rounds: int = 16,
    max_grounding_repairs: int = 4,
    verbose: bool = False,
    on_event: ProgressCallback | None = None,
    stream_trace: bool = False,
    trace_capture: list[str] | None = None,
) -> AgentReport:
    # Block obvious off-domain prompts before any LLM/SDK work (saves tokens + avoids nonsense results).
    if not brief_appears_in_scope(user_prompt):
        await _emit(
            on_event,
            {"kind": "step", "id": "domain_guard", "label": "Validating brief scope"},
        )
        return out_of_scope_agent_report()

    openrouter_key = require_env("OPENROUTER_API_KEY")
    acelab_key = require_env("ACELAB_API_KEY")
    acelab_base = require_env("ACELAB_BASE_URL")

    llm = AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=openrouter_key,
        default_headers={
            "HTTP-Referer": "https://github.com/acelab-takehome",
            "X-Title": "Acelab material agent take-home",
        },
    )
    model = get_openrouter_model()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    seen_products: dict[str, dict[str, Any]] = {}

    async with AsyncAcelab(api_key=acelab_key, base_url=acelab_base) as acelab:
        await _emit(
            on_event,
            {"kind": "step", "id": "analyzing_brief", "label": "Analyzing brief"},
        )
        for _repair in range(max_grounding_repairs + 1):
            emit_planning_step = True
            for _ in range(max_tool_rounds):
                if emit_planning_step:
                    await _emit(
                        on_event,
                        {"kind": "step", "id": "agent_reasoning", "label": "Planning & tool orchestration"},
                    )
                    emit_planning_step = False
                completion = await llm.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOL_SPECS,
                    tool_choice="auto",
                    temperature=0.2,
                )
                choice = completion.choices[0]
                msg = choice.message

                assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ]

                messages.append(assistant_msg)

                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        name = tc.function.name
                        result = await dispatch_tool(acelab, name, tc.function.arguments)
                        if name == "search_products":
                            _merge_seen_products(seen_products, result)
                        args_preview = (tc.function.arguments or "")[:200].replace("\n", " ")
                        await _tool_completed(
                            verbose=verbose,
                            on_event=on_event,
                            show_trace=stream_trace,
                            trace_capture=trace_capture,
                            name=name,
                            args_preview=args_preview,
                            payload=result,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(result, default=str),
                            }
                        )
                    emit_planning_step = True
                    continue

                text = msg.content or ""
                if not text.strip():
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Return the final JSON report only (no empty replies). "
                                "Use tool calls first if you still need data."
                            ),
                        }
                    )
                    break

                try:
                    report = _parse_report(text)
                except Exception:
                    await _emit(
                        on_event,
                        {"kind": "step", "id": "format_json", "label": "Structuring final report"},
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your last message was not valid JSON for the required schema. "
                                "Output ONLY the JSON object now, with no markdown or commentary."
                            ),
                        }
                    )
                    fix = await llm.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.0,
                    )
                    fixed_text = fix.choices[0].message.content or ""
                    try:
                        report = _parse_report(fixed_text)
                    except Exception as e:
                        raise RuntimeError(
                            "Model returned invalid JSON twice; last snippet: "
                            f"{fixed_text[:400]!r}"
                        ) from e

                bad = _grounding_issues(report, seen_products)
                if not bad:
                    await _emit(
                        on_event,
                        {"kind": "step", "id": "grounding", "label": "Grounding recommendations"},
                    )
                    return report

                if verbose:
                    print(f"[trace] grounding repair ({bad[:5]}{'...' if len(bad) > 5 else ''})", file=sys.stderr)
                await _emit(
                    on_event,
                    {
                        "kind": "step",
                        "id": "grounding_repair",
                        "label": "Aligning recommendations with catalog search results",
                    },
                )
                gr_line = f"grounding repair · invalid product_ids: {bad[:8]!s}"
                if trace_capture is not None:
                    trace_capture.append(gr_line)
                if stream_trace and on_event is not None:
                    await _emit(
                        on_event,
                        {
                            "kind": "trace",
                            "message": gr_line,
                        },
                    )
                messages.append({"role": "user", "content": _grounding_user_message(bad, seen_products)})
                break
            else:
                raise RuntimeError("Exceeded tool round budget without a final answer.")

        raise RuntimeError(
            "Exceeded grounding repair budget — recommendations still not tied to search_products results."
        )
