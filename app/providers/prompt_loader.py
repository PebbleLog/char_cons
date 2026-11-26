"""版本化提示词加载。长提示词不散落在业务代码中。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def manifest() -> dict:
    path = PROMPTS_DIR / "manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": "unknown", "prompts": {}}


def prompt_version() -> str:
    return manifest().get("version", "unknown")
