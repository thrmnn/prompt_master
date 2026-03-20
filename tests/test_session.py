"""Tests for session persistence: save, load, resume, list, delete."""

import json

import pytest

from prompt_master.conversation import ConversationEngine, Phase
from prompt_master.session import (
    delete_session,
    generate_session_id,
    list_sessions,
    load_session,
    save_session,
)


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Override SESSIONS_DIR to use a temp directory."""
    monkeypatch.setattr("prompt_master.session.SESSIONS_DIR", tmp_path)
    return tmp_path


class TestSessionPersistence:
    def test_generate_session_id_is_unique(self):
        ids = {generate_session_id() for _ in range(100)}
        assert len(ids) == 100

    def test_save_and_load_roundtrip(self, sessions_dir):
        engine = ConversationEngine(target="code")
        engine.add_user_message("Build a CLI tool")
        engine.add_assistant_message("Sure, what language?")
        engine.current_draft = "You are a CLI expert."
        engine.phase = Phase.DRAFTING

        sid = generate_session_id()
        path = save_session(sid, engine)

        assert path.exists()
        assert path.suffix == ".json"

        loaded_sid, loaded_engine = load_session(sid)
        assert loaded_sid == sid
        assert loaded_engine.target == "code"
        assert loaded_engine.phase == Phase.DRAFTING
        assert loaded_engine.current_draft == "You are a CLI expert."
        assert len(loaded_engine.messages) == 2

    def test_load_by_prefix(self, sessions_dir):
        engine = ConversationEngine()
        engine.add_user_message("Hello")
        sid = generate_session_id()
        save_session(sid, engine)

        loaded_sid, loaded_engine = load_session(sid[:8])
        assert loaded_sid == sid

    def test_load_not_found_raises(self, sessions_dir):
        with pytest.raises(FileNotFoundError, match="No session found"):
            load_session("nonexistent")

    def test_load_ambiguous_raises(self, sessions_dir):
        # Create two sessions with same prefix (forge filenames)
        for suffix in ("aaa", "bbb"):
            engine = ConversationEngine()
            data = {
                "session_id": f"abcd{suffix}",
                "created_at": "2024-01-01",
                "engine": engine.to_dict(),
            }
            (sessions_dir / f"abcd{suffix}.json").write_text(json.dumps(data))

        with pytest.raises(FileNotFoundError, match="Ambiguous"):
            load_session("abcd")

    def test_list_sessions(self, sessions_dir):
        for i in range(3):
            engine = ConversationEngine(target="code")
            engine.add_user_message(f"Idea {i}")
            save_session(generate_session_id(), engine)

        sessions = list_sessions()
        assert len(sessions) == 3
        assert all(s["target"] == "code" for s in sessions)
        assert all(s["message_count"] == 1 for s in sessions)

    def test_list_sessions_empty(self, sessions_dir):
        assert list_sessions() == []

    def test_delete_session(self, sessions_dir):
        engine = ConversationEngine()
        sid = generate_session_id()
        save_session(sid, engine)

        assert delete_session(sid)
        assert not (sessions_dir / f"{sid}.json").exists()

    def test_delete_by_prefix(self, sessions_dir):
        engine = ConversationEngine()
        sid = generate_session_id()
        save_session(sid, engine)

        assert delete_session(sid[:8])
        assert list_sessions() == []

    def test_delete_nonexistent_returns_false(self, sessions_dir):
        assert not delete_session("nonexistent")

    def test_session_file_format(self, sessions_dir):
        engine = ConversationEngine(target="analysis")
        engine.add_user_message("Analyze data")
        engine.phase = Phase.EXPLORING

        sid = generate_session_id()
        path = save_session(sid, engine)

        data = json.loads(path.read_text())
        assert data["session_id"] == sid
        assert "created_at" in data
        assert data["engine"]["target"] == "analysis"
        assert data["engine"]["phase"] == "exploring"

    def test_list_sessions_skips_corrupted(self, sessions_dir):
        # Write a valid session
        engine = ConversationEngine()
        engine.add_user_message("Valid")
        save_session(generate_session_id(), engine)

        # Write a corrupted file
        (sessions_dir / "bad.json").write_text("not json{{{")

        sessions = list_sessions()
        assert len(sessions) == 1
