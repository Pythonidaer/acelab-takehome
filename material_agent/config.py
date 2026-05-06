from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL


def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v
