"""CLI integration tests."""

from click.testing import CliRunner

from prompt_master.cli import main


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Prompt Master" in result.output


def test_optimize_quick_no_api():
    runner = CliRunner()
    result = runner.invoke(main, ["optimize", "build a todo app", "--no-api"])
    assert result.exit_code == 0
    assert "# Role" in result.output
    assert "todo app" in result.output


def test_optimize_code_target_no_api():
    runner = CliRunner()
    result = runner.invoke(main, ["optimize", "sort a list", "-t", "code", "--no-api"])
    assert result.exit_code == 0
    assert "code" in result.output.lower() or "engineer" in result.output.lower()


def test_optimize_output_to_file(tmp_path):
    runner = CliRunner()
    out_file = str(tmp_path / "prompt.md")
    result = runner.invoke(main, ["optimize", "build a todo app", "--no-api", "-o", out_file])
    assert result.exit_code == 0
    content = (tmp_path / "prompt.md").read_text()
    assert "todo app" in content


def test_optimize_with_api(mocker):
    mocker.patch("prompt_master.optimizer.ClaudeClient")
    mock_instance = mocker.patch("prompt_master.optimizer.ClaudeClient").return_value
    mock_instance.generate.return_value = "# Optimized prompt from API"

    runner = CliRunner()
    result = runner.invoke(main, ["optimize", "build a todo app"])
    assert result.exit_code == 0
    assert "Optimized prompt from API" in result.output


def test_templates_list():
    runner = CliRunner()
    result = runner.invoke(main, ["templates", "list"])
    assert result.exit_code == 0
    assert "general" in result.output


def test_templates_show():
    runner = CliRunner()
    result = runner.invoke(main, ["templates", "show", "general"])
    assert result.exit_code == 0
    assert "[meta]" in result.output


def test_templates_show_missing():
    runner = CliRunner()
    result = runner.invoke(main, ["templates", "show", "nonexistent_xyz"])
    assert result.exit_code != 0
