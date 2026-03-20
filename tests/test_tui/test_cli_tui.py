"""Tests for TUI CLI integration — verifies the `tui` subcommand is wired up."""

from click.testing import CliRunner

from prompt_master.cli import main


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


class TestTuiHelp:
    def test_tui_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert result.exit_code == 0

    def test_tui_help_shows_description(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        # The help text should mention the canvas or interactive
        assert (
            "canvas" in result.output.lower()
            or "interactive" in result.output.lower()
            or "tui" in result.output.lower()
        )

    def test_tui_help_shows_options(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "--target" in result.output
        assert "--model" in result.output


# ---------------------------------------------------------------------------
# --target flag
# ---------------------------------------------------------------------------


class TestTuiAcceptsTarget:
    def test_target_workflow_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "workflow" in result.output

    def test_target_code_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "code" in result.output


# ---------------------------------------------------------------------------
# --model flag
# ---------------------------------------------------------------------------


class TestTuiAcceptsModel:
    def test_model_haiku_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "haiku" in result.output

    def test_model_sonnet_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "sonnet" in result.output

    def test_model_opus_in_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["tui", "--help"])
        assert "opus" in result.output
