"""Tests for the interactive clarifying-question flow."""

from click.testing import CliRunner

from prompt_master.cli import main


def test_interactive_mode_asks_questions(mocker):
    mocker.patch("prompt_master.optimizer.ClaudeClient")
    mock_instance = mocker.patch("prompt_master.optimizer.ClaudeClient").return_value
    mock_instance.generate.return_value = "# Optimized prompt here"

    runner = CliRunner()
    # Provide answers for: audience, constraints, format, example (4 "all" questions)
    result = runner.invoke(
        main,
        ["optimize", "build a todo app", "-m", "interactive"],
        input="developers\nmust use React\nbullet points\n\n",
    )
    assert result.exit_code == 0


def test_interactive_code_target_asks_language(mocker):
    mocker.patch("prompt_master.optimizer.ClaudeClient")
    mock_instance = mocker.patch("prompt_master.optimizer.ClaudeClient").return_value
    mock_instance.generate.return_value = "# Optimized prompt here"

    runner = CliRunner()
    # Code target adds "language" question
    result = runner.invoke(
        main,
        ["optimize", "sort a list", "-m", "interactive", "-t", "code"],
        input="devs\nnone\ncode block\nPython\n\n",
    )
    assert result.exit_code == 0


def test_interactive_skips_empty_answers(mocker):
    mocker.patch("prompt_master.optimizer.ClaudeClient")
    mock_instance = mocker.patch("prompt_master.optimizer.ClaudeClient").return_value
    mock_instance.generate.return_value = "# Optimized prompt here"

    runner = CliRunner()
    # All empty answers
    result = runner.invoke(
        main,
        ["optimize", "test idea", "-m", "interactive"],
        input="\n\n\n\n",
    )
    assert result.exit_code == 0
