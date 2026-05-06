"""Human-readable CLI report layout aligned with examples/basic_usage.py typography."""

from __future__ import annotations

import textwrap

from .agent import AgentReport

_LINE_WIDTH = 88


def format_report_basic_usage_style(report: AgentReport) -> str:
    """Section headers and indentation similar to examples/basic_usage.py print style.

    This prints the agent's *synthesized* report, not the raw six-block SDK walkthrough
    that examples/basic_usage.py runs; see README for the distinction.
    """
    out: list[str] = []

    out.append("Executive summary:\n")
    out.extend(_wrap_prose(report.executive_summary.strip(), indent="  "))
    out.append("")

    out.append(f"Key constraints ({len(report.key_constraints)}):\n")
    if report.key_constraints:
        for item in report.key_constraints:
            out.append(f"  {item.strip()}")
    else:
        out.append("  (none)")
    out.append("")

    out.append("Search strategy:\n")
    out.extend(_wrap_prose(report.search_strategy.strip(), indent="  "))
    out.append("")

    recs = report.recommendations
    out.append(f"Recommended products ({len(recs)} grounded from catalog search):\n")
    if not recs:
        out.append("  —")
        out.append("")
    else:
        for rec in sorted(recs, key=lambda r: r.rank):
            score_s = ""
            if rec.similarity_score is not None:
                score_s = f"{float(rec.similarity_score):.2f}"
            else:
                score_s = "(n/a)"
            out.append(f"  {rec.product_name}")
            out.append(f"    Supplier:   {rec.supplier or '(unknown)'}")
            out.append(f"    Score:      {score_s}")
            out.append(f"    Product ID: {rec.product_id}")
            if rec.addresses:
                addr = ", ".join(rec.addresses)
                if len(f"    Addresses:  {addr}") <= _LINE_WIDTH:
                    out.append(f"    Addresses:  {addr}")
                else:
                    out.append("    Addresses:")
                    out.extend(
                        _wrap_lines(
                            addr,
                            indent="      ",
                        ),
                    )
            out.append("    Reasoning:")
            out.extend(
                _wrap_lines(
                    rec.reasoning.strip(),
                    indent="      ",
                ),
            )
            out.append("")

    out.append(f"Caveats ({len(report.caveats)}):\n")
    if report.caveats:
        for c in report.caveats:
            out.extend(_wrap_prose(c.strip(), indent="  "))
            out.append("")
    else:
        out.append("  —")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def _wrap_lines(text: str, *, indent: str, width: int = _LINE_WIDTH) -> list[str]:
    t = text.strip()
    if not t:
        return [f"{indent}—"]
    return textwrap.fill(
        t,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=False,
        break_on_hyphens=True,
    ).split("\n")


def _wrap_prose(text: str, *, indent: str, width: int = _LINE_WIDTH) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not parts:
        return _wrap_lines("", indent=indent, width=width)
    block: list[str] = []
    for i, part in enumerate(parts):
        if i:
            block.append("")
        block.extend(_wrap_lines(part, indent=indent, width=width))
    return block
