"""Prompt history — saves all generated prompts to a JSONL log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

HISTORY_PATH = Path.home() / ".prompt_master" / "history.jsonl"


def record(
    idea: str,
    optimized_prompt: str,
    target: str,
    used_api: bool,
    model: Optional[str] = None,
):
    """Append a prompt generation to the history log."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idea": idea,
        "target": target,
        "used_api": used_api,
        "model": model or "",
        "prompt_length": len(optimized_prompt),
        "prompt": optimized_prompt,
    }
    with open(HISTORY_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(limit: int = 50) -> List[dict]:
    """Load the most recent history entries."""
    if not HISTORY_PATH.exists():
        return []
    entries = []
    try:
        with open(HISTORY_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return entries[-limit:]


def clear_history() -> int:
    """Clear all history. Returns number of entries deleted."""
    if not HISTORY_PATH.exists():
        return 0
    entries = load_history(limit=999999)
    count = len(entries)
    HISTORY_PATH.unlink()
    return count
