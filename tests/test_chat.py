"""CLI integration tests for the chat command."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from prompt_master.cli import main
from prompt_master.conversation import FINAL_PROMPT, PROMPT_END, PROMPT_START


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def mock_claude_client():
    """Mock ClaudeClient for chat tests."""
    with patch("prompt_master.chat.ClaudeClient") as mock_cls:
        instance = mock_cls.return_value
        yield instance


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    """Override SESSIONS_DIR to use a temp directory."""
    monkeypatch.setattr("prompt_master.session.SESSIONS_DIR", tmp_path)
    return tmp_path


class TestChatCommand:
    def test_chat_help(self, cli_runner):
        result = cli_runner.invoke(main, ["chat", "--help"])
        assert result.exit_code == 0
        assert "interactive chat session" in result.output.lower()

    def test_chat_no_api_key(self, cli_runner, sessions_dir):
        """Chat mode requires an API key."""
        with patch("prompt_master.chat.ClaudeClient") as mock_cls:
            from prompt_master.client import NoAPIKeyError

            mock_cls.side_effect = NoAPIKeyError("No key")
            result = cli_runner.invoke(main, ["chat", "test idea"])

        assert "Error" in result.output or "error" in result.output.lower()

    def test_chat_with_idea_and_done(self, cli_runner, mock_claude_client, sessions_dir):
        """Full flow: idea → response → /done → final prompt."""
        responses = iter(
            [
                # Response to initial idea
                f"Great idea! Here's a draft:\n{PROMPT_START}\nYou are an expert.\n{PROMPT_END}\nHow's this?",
                # Response to /done finalization
                f"{FINAL_PROMPT}\nYou are an expert at building things.\n{FINAL_PROMPT}",
            ]
        )

        def stream_side_effect(**kwargs):
            text = next(responses)
            return iter([text])

        mock_claude_client.converse_stream.side_effect = stream_side_effect

        result = cli_runner.invoke(main, ["chat", "build something cool"], input="/done\n")

        assert result.exit_code == 0
        assert mock_claude_client.converse_stream.call_count == 2

    def test_chat_quit_saves_session(self, cli_runner, mock_claude_client, sessions_dir):
        """Quitting saves the session."""
        mock_claude_client.converse_stream.return_value = iter(["Interesting! Tell me more."])

        result = cli_runner.invoke(main, ["chat", "my idea"], input="/quit\n")

        assert result.exit_code == 0
        # Session file should exist
        session_files = list(sessions_dir.glob("*.json"))
        assert len(session_files) == 1

    def test_chat_save_command(self, cli_runner, mock_claude_client, sessions_dir):
        """/save saves the session mid-conversation."""
        mock_claude_client.converse_stream.return_value = iter(["Let's work on this."])

        result = cli_runner.invoke(main, ["chat", "my idea"], input="/save\n/quit\n")

        assert result.exit_code == 0
        assert "Session saved" in result.output or "session saved" in result.output.lower()

    def test_chat_help_command(self, cli_runner, mock_claude_client, sessions_dir):
        """/help shows commands."""
        mock_claude_client.converse_stream.return_value = iter(["What shall we build?"])

        result = cli_runner.invoke(main, ["chat", "my idea"], input="/help\n/quit\n")

        assert result.exit_code == 0
        assert "/done" in result.output
        assert "/save" in result.output

    def test_chat_draft_command_no_draft(self, cli_runner, mock_claude_client, sessions_dir):
        """/draft with no draft yet shows message."""
        mock_claude_client.converse_stream.return_value = iter(["Tell me more about your idea."])

        result = cli_runner.invoke(main, ["chat", "idea"], input="/draft\n/quit\n")

        assert result.exit_code == 0
        assert "No draft yet" in result.output or "no draft" in result.output.lower()

    def test_chat_target_option(self, cli_runner, mock_claude_client, sessions_dir):
        """Target option is passed to the engine."""
        mock_claude_client.converse_stream.return_value = iter(["What language?"])

        result = cli_runner.invoke(main, ["chat", "build a CLI", "-t", "code"], input="/quit\n")

        assert result.exit_code == 0
        # Verify target appears in banner
        assert "code" in result.output.lower()

    def test_chat_output_file(self, cli_runner, mock_claude_client, sessions_dir, tmp_path):
        """Output file receives the final prompt."""
        outfile = tmp_path / "result.md"

        responses = iter(
            [
                f"{PROMPT_START}\nDraft\n{PROMPT_END}",
                f"{FINAL_PROMPT}\nFinal output here.\n{FINAL_PROMPT}",
            ]
        )
        mock_claude_client.converse_stream.side_effect = lambda **kw: iter([next(responses)])

        result = cli_runner.invoke(
            main,
            ["chat", "idea", "-o", str(outfile)],
            input="/done\n",
        )

        assert result.exit_code == 0
        assert outfile.exists()
        assert "Final output here." in outfile.read_text()

    def test_chat_resume_nonexistent(self, cli_runner, sessions_dir):
        """Resuming a nonexistent session shows error."""
        with patch("prompt_master.chat.ClaudeClient"):
            result = cli_runner.invoke(main, ["chat", "--resume", "nonexistent"])

        assert "error" in result.output.lower() or "Error" in result.output

    def test_chat_open_ended_no_idea(self, cli_runner, mock_claude_client, sessions_dir):
        """Chat can start without an initial idea."""
        result = cli_runner.invoke(main, ["chat", "-t", "code"], input="/quit\n")

        assert result.exit_code == 0
        # Should not have called the API (no initial idea, quit immediately)
        assert mock_claude_client.converse_stream.call_count == 0
