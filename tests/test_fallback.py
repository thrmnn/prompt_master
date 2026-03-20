"""Tests for template-based fallback optimization."""

from prompt_master.fallback import fallback_optimize


def test_fallback_produces_sections():
    result = fallback_optimize("build a todo app")
    assert "# Role" in result
    assert "# Task" in result
    assert "# Output Format" in result


def test_fallback_includes_idea():
    result = fallback_optimize("build a todo app")
    assert "todo app" in result


def test_fallback_code_target():
    result = fallback_optimize("sort a list", target="code")
    assert "software engineer" in result.lower() or "code" in result.lower()


def test_fallback_creative_target():
    result = fallback_optimize("write a poem", target="creative")
    assert "creative" in result.lower() or "writer" in result.lower()


def test_fallback_analysis_target():
    result = fallback_optimize("market trends", target="analysis")
    assert "analy" in result.lower()


def test_fallback_with_clarifications():
    clarifications = {
        "audience": "developers",
        "format": "bullet points",
        "constraints": "keep it under 500 words",
    }
    result = fallback_optimize("explain REST APIs", clarifications=clarifications)
    assert "developers" in result
    assert "bullet points" in result
    assert "500 words" in result


def test_fallback_with_example():
    clarifications = {"example": "Here is a sample output."}
    result = fallback_optimize("test idea", clarifications=clarifications)
    assert "# Example" in result
    assert "sample output" in result


def test_fallback_code_with_language():
    clarifications = {"language": "Python / FastAPI"}
    result = fallback_optimize("build an API", target="code", clarifications=clarifications)
    assert "Python" in result
    assert "FastAPI" in result
