from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .agent import run_agent
from .cli_report import format_report_basic_usage_style


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask the material agent for ranked product recommendations.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Project or space description. If omitted, read stdin.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Log each Acelab tool call to stderr (report still goes to stdout).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON on stdout (default: human-readable report, similar to examples/basic_usage.py).",
    )
    ns = parser.parse_args()
    text = ns.prompt
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        parser.error("Provide a prompt argument or pipe text on stdin.")
    report = asyncio.run(run_agent(text, verbose=ns.trace))
    if ns.json:
        print(json.dumps(report.model_dump(), indent=2))
    else:
        print(format_report_basic_usage_style(report), end="")


if __name__ == "__main__":
    main()
