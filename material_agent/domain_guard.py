"""Lightweight heuristic gate: skip LLM + Acelab when a prompt is clearly off-domain.

This is intentionally not ML-based. We only block prompts that strongly resemble
consumer tech, entertainment, personal services, software tutorials, etc., while
lacking any building-materials / spatial / construction cue that would justify a catalog search.
"""

from __future__ import annotations

# Phrases (or substrings) that strongly suggest non-architectural intent.
# Kept specific to reduce false positives (e.g. "job" alone is too broad).
# Software/dev entries are mostly multi-token phrases so we do not match "reactive resin" via "react".
_OFF_TOPIC_SIGNALS: frozenset[str] = frozenset(
    {
        "gaming keyboard",
        "mechanical keyboard",
        "video game",
        "twitch",
        "youtube channel",
        "stream setup",
        "haircut",
        "manicure",
        "dating app",
        "dating site",
        "netflix",
        "recipe for",
        "crypto wallet",
        "cryptocurrency",
        "stock tip",
        "stock market",
        "job search",
        "find me a job",
        "resume tips",
        "python tutorial",
        "leetcode",
        # --- Software / dev tutorial (substring-safe phrases) ---
        "programming tutorial",
        "coding tutorial",
        "docker tutorial",
        "node.js tutorial",
        "api tutorial",
        "css flexbox",
        "react tutorial",
        "useeffect",
        "use state",
        "usestate",
        "node.js",
        "nodejs",
        "dockerized",
    }
)

# Whole-word software tokens: "react" must not substring-match "reactive" / "reaction".
_DEV_WHOLE_WORDS: frozenset[str] = frozenset(
    {
        "react",
        "javascript",
        "typescript",
        "flexbox",
    }
)

# Tokens that indicate the user is talking about the built environment, specification, or product categories.
# If any of these appear, we treat the brief as plausibly in scope (heuristic is permissive).
_DOMAIN_HINTS: frozenset[str] = frozenset(
    {
        "floor",
        "flooring",
        "wall",
        "ceiling",
        "roof",
        "facade",
        "cladding",
        "curtain wall",
        "window",
        "door",
        "glazing",
        "skylight",
        "tile",
        "porcelain",
        "ceramic",
        "terrazzo",
        "mosaic",
        "carpet",
        "rug",
        "vinyl",
        "lvt",
        "lvp",
        "sheet vinyl",
        "rubber floor",
        "epoxy",
        "sealed concrete",
        "hardwood",
        "wood floor",
        "bamboo floor",
        "countertop",
        "surface",
        "quartz",
        "solid surface",
        "laminate",
        "metal panel",
        "insulation",
        "waterproof",
        "membrane",
        "coating",
        "paint",
        "plaster",
        "drywall",
        "gypsum",
        "acoustic",
        "stone",
        "masonry",
        "brick",
        "concrete",
        "precast",
        "steel",
        "aluminum",
        "lobby",
        "corridor",
        "hallway",
        "atrium",
        "reception",
        "waiting area",
        "hospital",
        "healthcare",
        "critical care",
        "operating room",
        "clean room",
        "clinic",
        "laboratory",
        "wet lab",
        "school",
        "classroom",
        "university",
        "office",
        "workplace",
        "open office",
        "hotel",
        "hospitality",
        "guest room",
        "restaurant",
        "kitchen commercial",
        "retail",
        "storefront",
        "warehouse",
        "industrial",
        "factory",
        "residential",
        "multifamily",
        "commercial",
        "mixed-use",
        "interior",
        "exterior",
        "renovation",
        "tenant improvement",
        "new construction",
        "building",
        "construction",
        "architect",
        "architectural",
        "specification",
        "masterformat",
        "drawing",
        "leed",
        "well building",
        "well certification",
        "living building",
        "epd",
        "fsc",
        "sustainability",
        "infection control",
        "cfa",
        "ductwork",
        "fire rated",
        "building material",
        "substrate",
        "adhesive",
        "grout",
        "sealant",
        "movement joint",
        "expansion joint",
    }
)


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _has_domain_hint(n: str) -> bool:
    return any(hint in n for hint in _DOMAIN_HINTS)


def _dev_whole_word_hit(padded_normalized: str) -> bool:
    """True if common dev keywords appear as tokens (not as part of 'reactive', etc.)."""
    return any(f" {w} " in padded_normalized for w in _DEV_WHOLE_WORDS)


def brief_appears_in_scope(prompt: str) -> bool:
    """Return False only when off-topic signals appear and no domain hint does."""
    raw = prompt.strip()
    if len(raw) < 8:
        # Too short to confidently reject; let the model/SDK handle it.
        return True

    n = _normalized(raw)
    padded = f" {n} "

    if any(signal in n for signal in _OFF_TOPIC_SIGNALS):
        if _has_domain_hint(n):
            return True
        return False

    if _dev_whole_word_hit(padded):
        if _has_domain_hint(n):
            return True
        return False

    # Peripherals / streaming without construction language
    if "keyboard" in n or "keycaps" in n or "mouse pad" in n or "mousepad" in n:
        if _has_domain_hint(n):
            return True
        return False

    return True


def out_of_scope_agent_report():
    """Structured report when the brief is blocked before any API orchestration."""
    from .agent import AgentReport

    return AgentReport(
        executive_summary=(
            "This assistant is specialized in **architectural and interior building materials** "
            "(flooring, wall and ceiling systems, finishes, resilient surfaces, ceramics, certifications, "
            "and similar product categories). Your message does not appear related to that domain, so "
            "no catalog searches were run."
        ),
        key_constraints=[],
        search_strategy=(
            "No Acelab SDK or OpenRouter tool calls were made — the brief failed a lightweight "
            "domain check intended to avoid irrelevant catalog results."
        ),
        recommendations=[],
        caveats=[
            "Please resubmit a **project- or space-oriented brief** (e.g. building type, room or circulation "
            "area, performance needs, aesthetic direction, sustainability targets, or named product categories).",
        ],
    )
