"""Tests for Vibe Mode — prompt variation generation and exploration."""

import pytest
from click.testing import CliRunner

from prompt_master.cli import main
from prompt_master.vibe import (
    DIMENSIONS,
    VARIATION_END,
    VARIATION_START,
    Variation,
    VibeEngine,
    _apply_dimension,
    parse_variations,
)


# ── Variation parsing ───────────────────────────────────────────────────────


class TestVariationParsing:
    def test_parse_single_variation(self):
        text = (
            f"Here's a variation:\n"
            f"{VARIATION_START}\n"
            f"dimension: tone\n"
            f"value: formal\n"
            f"---\n"
            f"# Role\nYou are a formal expert.\n\n# Task\nDo the thing.\n"
            f"{VARIATION_END}\n"
        )
        variations = parse_variations(text)
        assert len(variations) == 1
        assert variations[0].dimension == "tone"
        assert variations[0].value == "formal"
        assert "formal expert" in variations[0].prompt

    def test_parse_multiple_variations(self):
        text = ""
        for dim, val in [("tone", "casual"), ("audience", "expert")]:
            text += (
                f"{VARIATION_START}\n"
                f"dimension: {dim}\n"
                f"value: {val}\n"
                f"---\n"
                f"Prompt for {dim}={val}\n"
                f"{VARIATION_END}\n\n"
            )
        variations = parse_variations(text)
        assert len(variations) == 2
        assert variations[0].dimension == "tone"
        assert variations[1].dimension == "audience"

    def test_parse_no_variations(self):
        assert parse_variations("Just some plain text.") == []

    def test_parse_strips_prompt_whitespace(self):
        text = (
            f"{VARIATION_START}\n"
            f"dimension: style\n"
            f"value: concise\n"
            f"---\n"
            f"  Clean prompt.  \n"
            f"{VARIATION_END}"
        )
        variations = parse_variations(text)
        assert variations[0].prompt == "Clean prompt."


# ── Variation dataclass ─────────────────────────────────────────────────────


class TestVariation:
    def test_to_dict(self):
        v = Variation(dimension="tone", value="formal", prompt="test", parent_id=2)
        d = v.to_dict()
        assert d["dimension"] == "tone"
        assert d["parent_id"] == 2

    def test_from_dict(self):
        v = Variation.from_dict({"dimension": "audience", "value": "expert", "prompt": "p"})
        assert v.dimension == "audience"
        assert v.parent_id is None

    def test_roundtrip(self):
        original = Variation(dimension="format", value="bullets", prompt="# Role\nExpert")
        restored = Variation.from_dict(original.to_dict())
        assert restored.dimension == original.dimension
        assert restored.prompt == original.prompt


# ── Dimensions catalog ──────────────────────────────────────────────────────


class TestDimensions:
    def test_all_dimensions_present(self):
        expected = {"tone", "audience", "format", "specificity", "style"}
        assert set(DIMENSIONS.keys()) == expected

    def test_dimensions_have_values(self):
        for dim, values in DIMENSIONS.items():
            assert len(values) >= 3, f"Dimension {dim} has too few values"


# ── VibeEngine (offline / fallback) ─────────────────────────────────────────


class TestVibeEngine:
    def test_fallback_variations(self):
        engine = VibeEngine(idea="build an API", target="code")
        variations = engine._fallback_variations(count=3)
        assert len(variations) == 3
        for v in variations:
            assert v.prompt
            assert v.dimension in DIMENSIONS
            assert v.value

    def test_fallback_with_specific_dimensions(self):
        engine = VibeEngine(idea="write a poem", target="creative")
        variations = engine._fallback_variations(count=2, dimensions=["tone", "style"])
        assert len(variations) == 2
        dims = {v.dimension for v in variations}
        assert dims <= {"tone", "style"}

    def test_compare(self):
        engine = VibeEngine(idea="test")
        engine.variations = [
            Variation(dimension="tone", value="formal", prompt="A" * 200),
            Variation(dimension="audience", value="expert", prompt="B" * 50),
        ]
        comparison = engine.compare()
        assert len(comparison) == 2
        assert comparison[0]["length"] == 200
        assert comparison[1]["length"] == 50
        assert "..." in comparison[0]["preview"]

    def test_compare_subset(self):
        engine = VibeEngine(idea="test")
        engine.variations = [
            Variation(dimension="tone", value="a", prompt="x"),
            Variation(dimension="tone", value="b", prompt="y"),
            Variation(dimension="tone", value="c", prompt="z"),
        ]
        comparison = engine.compare(indices=[0, 2])
        assert len(comparison) == 2
        assert comparison[0]["index"] == 0
        assert comparison[1]["index"] == 2

    def test_serialization_roundtrip(self):
        engine = VibeEngine(idea="test idea", target="code")
        engine.variations = [
            Variation(dimension="tone", value="formal", prompt="prompt 1"),
            Variation(dimension="style", value="concise", prompt="prompt 2", parent_id=0),
        ]
        data = engine.to_dict()
        restored = VibeEngine.from_dict(data)
        assert restored.idea == "test idea"
        assert restored.target == "code"
        assert len(restored.variations) == 2
        assert restored.variations[1].parent_id == 0

    def test_mutate_index_error(self):
        engine = VibeEngine(idea="test")
        with pytest.raises(IndexError):
            engine.mutate(99, "tone", "formal")


# ── Dimension application (template fallback) ──────────────────────────────


class TestApplyDimension:
    def test_apply_tone(self):
        prompt = "# Role\nExpert\n\n# Task\nDo stuff"
        result = _apply_dimension(prompt, "tone", "formal")
        # Deep transform rewrites Role, not just inserts a constraint
        assert "distinguished" in result.lower() or "precision" in result.lower()
        assert "# Role" in result

    def test_apply_audience(self):
        prompt = "# Role\nExpert\n\n# Task\nDo stuff"
        result = _apply_dimension(prompt, "audience", "beginner")
        assert "beginner" in result.lower()

    def test_apply_to_prompt_without_task(self):
        prompt = "Just a plain prompt."
        result = _apply_dimension(prompt, "style", "concise")
        # Deep transform rewrites Role and Requirements
        assert "concise" in result.lower() or "precise" in result.lower()
        assert "# Role" in result or "# Requirements" in result


# ── CLI integration ─────────────────────────────────────────────────────────


class TestVibeCLI:
    def test_vibe_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["vibe", "--help"])
        assert result.exit_code == 0
        assert "variation" in result.output.lower()

    def test_vibe_no_api(self):
        runner = CliRunner()
        result = runner.invoke(main, ["vibe", "build an api", "-t", "code", "--no-api", "-n", "3"])
        assert result.exit_code == 0
        assert "Variation 1" in result.output
        assert "Variation 2" in result.output
        assert "Variation 3" in result.output

    def test_vibe_specific_dimensions(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["vibe", "write a poem", "--no-api", "-d", "tone,style", "-n", "2"]
        )
        assert result.exit_code == 0
        assert "Variation" in result.output

    def test_vibe_invalid_dimension(self):
        runner = CliRunner()
        result = runner.invoke(main, ["vibe", "test", "--no-api", "-d", "bogus"])
        assert result.exit_code != 0

    def test_vibe_output_to_file(self, tmp_path):
        outfile = tmp_path / "vibes.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["vibe", "build an api", "--no-api", "-n", "2", "-o", str(outfile)],
        )
        assert result.exit_code == 0
        assert outfile.exists()
        content = outfile.read_text()
        assert "Variation 1" in content
        assert "Variation 2" in content

    def test_vibe_empty_idea_rejected(self):
        runner = CliRunner()
        result = runner.invoke(main, ["vibe", "  ", "--no-api"])
        assert result.exit_code != 0

    def test_vibe_default_count_is_4(self):
        runner = CliRunner()
        result = runner.invoke(main, ["vibe", "test idea for vibes", "--no-api"])
        assert result.exit_code == 0
        assert "Variation 4" in result.output
