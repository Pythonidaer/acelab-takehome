from __future__ import annotations

import json
from typing import Any

from acelab import AsyncAcelab

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Semantic search across the full Acelab product catalog. Use several focused "
                "queries (performance, space type, finish, constraints) rather than one vague blob."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language product query."},
                    "limit": {
                        "type": "integer",
                        "description": "Max hits to return (default 8, cap 15).",
                        "default": 8,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_materials",
            "description": "Find material types (e.g. LVT, terrazzo, solid surface) relevant to the brief.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_certifications",
            "description": (
                "Find certifications or programs (LEED, WELL, FloorScore, EPD, etc.) mentioned or implied."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_companies",
            "description": "Look up manufacturers or brands when the user names them or you need anchor entities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_taxonomy",
            "description": (
                "Map a product category plus description into Acelab taxonomy to narrow product language."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_category_scraped": {
                        "type": "string",
                        "description": "Short category label, e.g. 'commercial sheet vinyl flooring'.",
                    },
                    "product_description": {
                        "type": "string",
                        "description": "1–3 sentences of context from the user's brief.",
                        "default": "",
                    },
                },
                "required": ["product_category_scraped"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deduplicate_product",
            "description": (
                "Check whether a specific named product may already exist in the catalog (near-duplicates / similar "
                "matches). Use when the user asks about duplicates, exact product matching, or whether something "
                "'already exists'. Results are supporting evidence only — not a substitute for product search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Manufacturer product name as the user described it."},
                    "supplier": {
                        "type": "string",
                        "description": "Supplier or brand name if known; omit if unknown.",
                    },
                    "description": {"type": "string", "description": "Optional product description for better matching."},
                    "attributes": {
                        "type": "object",
                        "description": 'Optional key/value attributes (string values), e.g. {"material": "quartz"}.',
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["name"],
            },
        },
    },
]


def _clamp_limit(raw: int | None, default: int, cap: int) -> int:
    if raw is None:
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, cap))


async def dispatch_tool(
    acelab: AsyncAcelab,
    name: str,
    arguments: str | dict[str, Any] | None,
) -> dict[str, Any]:
    args: dict[str, Any]
    if arguments is None or arguments == "":
        args = {}
    elif isinstance(arguments, dict):
        args = arguments
    else:
        args = json.loads(arguments)

    if name == "search_products":
        q = args["query"]
        limit = _clamp_limit(args.get("limit"), 8, 15)
        r = await acelab.search(q, limit=limit)
        return {
            "query": r.query,
            "total_results": r.total_results,
            "results": [p.model_dump() for p in r.results],
        }

    if name == "search_materials":
        q = args["query"]
        limit = _clamp_limit(args.get("limit"), 6, 15)
        r = await acelab.materials.search(q, limit=limit)
        return {
            "query": r.query,
            "total_results": r.total_results,
            "results": [m.model_dump() for m in r.results],
        }

    if name == "search_certifications":
        q = args["query"]
        limit = _clamp_limit(args.get("limit"), 6, 15)
        r = await acelab.certifications.search(q, limit=limit)
        return {
            "query": r.query,
            "total_results": r.total_results,
            "results": [c.model_dump() for c in r.results],
        }

    if name == "search_companies":
        q = args["query"]
        limit = _clamp_limit(args.get("limit"), 6, 15)
        r = await acelab.companies.search(q, limit=limit)
        return {
            "query": r.query,
            "total_results": r.total_results,
            "results": [c.model_dump() for c in r.results],
        }

    if name == "classify_taxonomy":
        cat = args["product_category_scraped"]
        desc = str(args.get("product_description") or "")
        r = await acelab.taxonomy.search(product_category_scraped=cat, product_description=desc)
        matched = None
        if r.new_taxonomy.matched_taxonomy:
            matched = r.new_taxonomy.matched_taxonomy.model_dump()
        candidates = [c.model_dump() for c in r.new_taxonomy.top_candidates[:5]]
        return {
            "match_status": r.new_taxonomy.match_status,
            "matched_taxonomy": matched,
            "top_candidates": candidates,
            "query_input": r.query_input,
        }

    if name == "deduplicate_product":
        product_name = args["name"]
        supplier = str(args.get("supplier") or "")
        description = args.get("description")
        if description is not None:
            description = str(description)
        attrs_raw = args.get("attributes")
        attributes: dict[str, str] | None = None
        if attrs_raw is not None:
            if not isinstance(attrs_raw, dict):
                return {"error": "deduplicate_product.attributes must be an object"}
            attributes = {str(k): str(v) for k, v in attrs_raw.items()}
        r = await acelab.deduplicate(
            name=product_name,
            supplier=supplier,
            description=description,
            attributes=attributes,
        )
        return {
            "query": {
                "name": product_name,
                "supplier": supplier if supplier else None,
                "description": description,
                "attributes": attributes,
            },
            "candidates": [c.model_dump() for c in r.candidates],
        }

    return {"error": f"unknown_tool:{name}"}
