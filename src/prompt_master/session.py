"""Save, load, and resume conversation sessions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from prompt_master.conversation import ConversationEngine

SESSIONS_DIR = Path.home() / ".prompt_master" / "sessions"


def _ensure_dir():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_session_id() -> str:
    return uuid.uuid4().hex


def save_session(session_id: str, engine: ConversationEngine) -> Path:
    """Save a conversation session to disk."""
    _ensure_dir()
    data = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engine": engine.to_dict(),
    }
    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def load_session(session_id: str) -> tuple[str, ConversationEngine]:
    """Load a session by ID (full or prefix match).

    Returns (full_session_id, engine).
    Raises FileNotFoundError if no match found.
    """
    _ensure_dir()
    # Try exact match first
    exact = SESSIONS_DIR / f"{session_id}.json"
    if exact.exists():
        return _load_file(exact)

    # Try prefix match
    matches = list(SESSIONS_DIR.glob(f"{session_id}*.json"))
    if len(matches) == 1:
        return _load_file(matches[0])
    elif len(matches) > 1:
        ids = [m.stem[:8] for m in matches]
        raise FileNotFoundError(f"Ambiguous session ID '{session_id}'. Matches: {', '.join(ids)}")
    else:
        raise FileNotFoundError(f"No session found matching '{session_id}'")


def _load_file(path: Path) -> tuple[str, ConversationEngine]:
    data = json.loads(path.read_text())
    engine = ConversationEngine.from_dict(data["engine"])
    return data["session_id"], engine


def list_sessions() -> list[dict]:
    """List all saved sessions with metadata."""
    _ensure_dir()
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            engine_data = data.get("engine", {})
            messages = engine_data.get("messages", [])
            # Get first user message as preview
            preview = ""
            for m in messages:
                if m["role"] == "user":
                    preview = m["content"][:80]
                    break
            sessions.append(
                {
                    "session_id": data["session_id"],
                    "created_at": data.get("created_at", ""),
                    "target": engine_data.get("target", "general"),
                    "phase": engine_data.get("phase", "exploring"),
                    "message_count": len(messages),
                    "preview": preview,
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return sessions


def prune_sessions(older_than_days: int = 30) -> int:
    """Delete sessions older than the given number of days. Returns count deleted."""
    _ensure_dir()
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=older_than_days)
    deleted = 0
    for path in list(SESSIONS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            created = data.get("created_at", "")
            if created:
                ts = datetime.fromisoformat(created)
                if ts < cutoff:
                    path.unlink()
                    deleted += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    return deleted


def delete_session(session_id: str) -> bool:
    """Delete a session file. Returns True if deleted."""
    _ensure_dir()
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    # Try prefix match
    matches = list(SESSIONS_DIR.glob(f"{session_id}*.json"))
    if len(matches) == 1:
        matches[0].unlink()
        return True
    return False
