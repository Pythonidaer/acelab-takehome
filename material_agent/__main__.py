from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .agent import run_agent


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
        help="Log each Acelab tool call to stderr (JSON still goes to stdout).",
    )
    ns = parser.parse_args()
    text = ns.prompt
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        parser.error("Provide a prompt argument or pipe text on stdin.")
    report = asyncio.run(run_agent(text, verbose=ns.trace))
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
