"""Tests for the core optimization pipeline."""

from prompt_master.optimizer import optimize_prompt


def test_optimize_with_api(mock_client):
    result = optimize_prompt("build a todo app", use_api=True)
    assert result.used_api is True
    assert result.optimized_prompt
    assert result.original_idea == "build a todo app"
    mock_client.generate.assert_called_once()


def test_optimize_with_api_includes_target(mock_client):
    optimize_prompt("sort a list", target="code", use_api=True)
    call_args = mock_client.generate.call_args
    user_msg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("user_message", "")
    assert "code" in user_msg.lower()


def test_optimize_with_api_includes_clarifications(mock_client):
    clarifications = {"audience": "beginners", "format": "step by step"}
    optimize_prompt("learn python", clarifications=clarifications, use_api=True)
    call_args = mock_client.generate.call_args
    user_msg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("user_message", "")
    assert "beginners" in user_msg
    assert "step by step" in user_msg


def test_optimize_fallback_when_no_api():
    result = optimize_prompt("build a todo app", use_api=False)
    assert result.used_api is False
    assert "# Role" in result.optimized_prompt
    assert "todo app" in result.optimized_prompt


def test_optimize_result_has_target(mock_client):
    result = optimize_prompt("test", target="analysis", use_api=True)
    assert result.target == "analysis"
