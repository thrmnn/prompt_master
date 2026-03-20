"""Tests for must-have/should-have features: validation, config, history, sessions CLI, client retry, output formats."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from prompt_master.cli import main
from prompt_master.validation import ValidationError, validate_idea, validate_template
from prompt_master.config import load_config, DEFAULTS
from prompt_master.history import record, load_history, clear_history
from prompt_master.client import ClaudeClient, NoAPIKeyError, UsageStats, estimate_cost, MODELS, OpenClawClient


# ── Input validation ────────────────────────────────────────────────────────


class TestValidation:
    def test_validate_normal_idea(self):
        assert validate_idea("build an api") == "build an api"

    def test_validate_strips_whitespace(self):
        assert validate_idea("  hello world  ") == "hello world"

    def test_validate_empty_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_idea("")

    def test_validate_whitespace_only_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_idea("   ")

    def test_validate_too_short_raises(self):
        with pytest.raises(ValidationError, match="short"):
            validate_idea("ab")

    def test_validate_too_long_raises(self):
        with pytest.raises(ValidationError, match="long"):
            validate_idea("x" * 10001)

    def test_validate_cli_rejects_empty(self):
        runner = CliRunner()
        result = runner.invoke(main, ["optimize", "  ", "--no-api"])
        assert result.exit_code != 0

    def test_validate_template_valid(self):
        data = {"meta": {"name": "test", "description": "A test"}}
        warnings = validate_template(data, "test")
        assert warnings == []

    def test_validate_template_missing_meta(self):
        data = {"role": {"default": "x"}}
        warnings = validate_template(data, "test")
        assert any("meta" in w.lower() for w in warnings)

    def test_validate_template_bad_type_raises(self):
        with pytest.raises(ValidationError):
            validate_template("not a dict", "bad")


# ── Config ──────────────────────────────────────────────────────────────────


class TestConfig:
    def test_defaults_present(self):
        assert "target" in DEFAULTS
        assert "model" in DEFAULTS
        assert "max_tokens" in DEFAULTS

    def test_load_config_returns_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr("prompt_master.config.CONFIG_PATH", tmp_path / "nope.toml")
        config = load_config()
        assert config["target"] == "general"
        assert config["model"] == "sonnet"

    def test_load_config_reads_file(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('target = "code"\nmax_tokens = 2048\n')
        monkeypatch.setattr("prompt_master.config.CONFIG_PATH", cfg_file)
        config = load_config()
        assert config["target"] == "code"
        assert config["max_tokens"] == 2048
        assert config["model"] == "sonnet"  # default preserved


# ── History ─────────────────────────────────────────────────────────────────


class TestHistory:
    @pytest.fixture(autouse=True)
    def use_tmp_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr("prompt_master.history.HISTORY_PATH", tmp_path / "history.jsonl")

    def test_record_and_load(self):
        record("test idea", "# Role\nExpert", "code", True, "sonnet")
        entries = load_history()
        assert len(entries) == 1
        assert entries[0]["idea"] == "test idea"
        assert entries[0]["target"] == "code"
        assert entries[0]["used_api"] is True

    def test_load_empty(self):
        assert load_history() == []

    def test_multiple_records(self):
        for i in range(5):
            record(f"idea {i}", f"prompt {i}", "general", False)
        entries = load_history()
        assert len(entries) == 5

    def test_load_with_limit(self):
        for i in range(10):
            record(f"idea {i}", f"prompt {i}", "general", False)
        entries = load_history(limit=3)
        assert len(entries) == 3
        assert entries[-1]["idea"] == "idea 9"

    def test_clear_history(self):
        for i in range(3):
            record(f"idea {i}", f"prompt {i}", "general", False)
        count = clear_history()
        assert count == 3
        assert load_history() == []

    def test_clear_empty(self):
        assert clear_history() == 0

    def test_history_cli_list(self):
        record("test idea", "prompt", "code", False)
        runner = CliRunner()
        result = runner.invoke(main, ["history", "list"])
        assert result.exit_code == 0
        assert "test idea" in result.output

    def test_history_cli_show(self):
        record("my idea", "# Role\nExpert", "code", False)
        runner = CliRunner()
        result = runner.invoke(main, ["history", "show", "0"])
        assert result.exit_code == 0
        assert "my idea" in result.output

    def test_history_cli_clear(self):
        record("idea", "prompt", "general", False)
        runner = CliRunner()
        result = runner.invoke(main, ["history", "clear"])
        assert result.exit_code == 0
        assert "Cleared" in result.output


# ── Sessions CLI ────────────────────────────────────────────────────────────


class TestSessionsCLI:
    @pytest.fixture(autouse=True)
    def use_tmp_sessions(self, tmp_path, monkeypatch):
        monkeypatch.setattr("prompt_master.session.SESSIONS_DIR", tmp_path)
        self.sessions_dir = tmp_path

    def test_sessions_list_empty(self):
        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "list"])
        assert result.exit_code == 0
        assert "No saved sessions" in result.output

    def test_sessions_list_with_data(self):
        from prompt_master.session import save_session, generate_session_id
        from prompt_master.conversation import ConversationEngine
        engine = ConversationEngine(target="code")
        engine.add_user_message("test")
        save_session(generate_session_id(), engine)

        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "list"])
        assert result.exit_code == 0
        assert "code" in result.output

    def test_sessions_delete(self):
        from prompt_master.session import save_session, generate_session_id
        from prompt_master.conversation import ConversationEngine
        sid = generate_session_id()
        save_session(sid, ConversationEngine())

        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "delete", sid])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    def test_sessions_prune(self):
        # Create an old session by writing directly
        old_data = {
            "session_id": "old123",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            "engine": {"target": "general", "phase": "exploring", "messages": [],
                       "current_draft": "", "final_prompt": ""},
        }
        (self.sessions_dir / "old123.json").write_text(json.dumps(old_data))

        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "prune", "--older-than", "30"])
        assert result.exit_code == 0
        assert "Pruned 1" in result.output


# ── Client ──────────────────────────────────────────────────────────────────


class TestClientFeatures:
    def test_model_catalog(self):
        assert "sonnet" in MODELS
        assert "haiku" in MODELS
        assert "opus" in MODELS

    def test_estimate_cost(self):
        cost = estimate_cost("sonnet", input_tokens=1000, output_tokens=500)
        assert cost > 0

    def test_usage_stats(self):
        stats = UsageStats()
        stats.record("sonnet", 100, 50)
        stats.record("sonnet", 200, 100)
        assert stats.call_count == 2
        assert stats.total_input_tokens == 300
        assert stats.total_output_tokens == 150
        assert "Tokens:" in stats.summary()

    def test_no_provider_raises_when_nothing_available(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr("prompt_master.client._openclaw_available", lambda: False)
        with pytest.raises(NoAPIKeyError):
            ClaudeClient()

    def test_openclaw_preferred_over_anthropic(self, monkeypatch):
        monkeypatch.setattr("prompt_master.client._openclaw_available", lambda: True)
        client = ClaudeClient()
        assert isinstance(client, OpenClawClient)


# ── Output formats ──────────────────────────────────────────────────────────


class TestOutputFormats:
    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["optimize", "test idea", "--no-api", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "optimized_prompt" in data
        assert data["original_idea"] == "test idea"

    def test_plain_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["optimize", "test idea", "--no-api", "--format", "plain"]
        )
        assert result.exit_code == 0
        assert "#" not in result.output  # markdown headers stripped
        assert "ROLE" in result.output  # converted to uppercase

    def test_markdown_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["optimize", "test idea", "--no-api", "--format", "markdown"]
        )
        assert result.exit_code == 0
        assert "# Role" in result.output

    def test_model_option_accepted(self):
        runner = CliRunner()
        result = runner.invoke(main, ["optimize", "--help"])
        assert "--model" in result.output
        assert "haiku" in result.output

    def test_max_tokens_option_accepted(self):
        runner = CliRunner()
        result = runner.invoke(main, ["optimize", "--help"])
        assert "--max-tokens" in result.output
