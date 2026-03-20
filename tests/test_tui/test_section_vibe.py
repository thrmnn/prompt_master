"""Tests for section-level variation generation (fallback / offline path)."""

from prompt_master.tui.section_vibe import (
    _fallback_section_variations,
)


# ---------------------------------------------------------------------------
# Fallback produces the right number of variations
# ---------------------------------------------------------------------------


class TestFallbackProducesVariations:
    def test_returns_correct_count(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are a helpful assistant.",
            target="general",
            count=4,
            dimensions=None,
        )
        assert len(results) == 4

    def test_returns_one(self):
        results = _fallback_section_variations(
            section_name="Task",
            section_content="Analyze data.",
            target="analysis",
            count=1,
            dimensions=None,
        )
        assert len(results) == 1

    def test_returns_many(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are an expert.",
            target="code",
            count=8,
            dimensions=None,
        )
        assert len(results) == 8


# ---------------------------------------------------------------------------
# Required fields present
# ---------------------------------------------------------------------------


class TestFallbackHasRequiredFields:
    def test_each_dict_has_dimension(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="Expert.",
            target="general",
            count=3,
            dimensions=None,
        )
        for r in results:
            assert "dimension" in r
            assert isinstance(r["dimension"], str)
            assert len(r["dimension"]) > 0

    def test_each_dict_has_value(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="Expert.",
            target="general",
            count=3,
            dimensions=None,
        )
        for r in results:
            assert "value" in r
            assert isinstance(r["value"], str)
            assert len(r["value"]) > 0

    def test_each_dict_has_content(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="Expert.",
            target="general",
            count=3,
            dimensions=None,
        )
        for r in results:
            assert "content" in r
            assert isinstance(r["content"], str)


# ---------------------------------------------------------------------------
# Diverse dimensions
# ---------------------------------------------------------------------------


class TestFallbackDifferentDimensions:
    def test_variations_use_multiple_dimensions(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are an expert.",
            target="general",
            count=5,
            dimensions=None,
        )
        dims = {r["dimension"] for r in results}
        # With 5 variations and no restriction, should use more than 1 dimension
        assert len(dims) > 1

    def test_not_all_same_dimension(self):
        results = _fallback_section_variations(
            section_name="Task",
            section_content="Build a REST API.",
            target="code",
            count=4,
            dimensions=None,
        )
        dims = [r["dimension"] for r in results]
        # Not all the same
        assert len(set(dims)) > 1


# ---------------------------------------------------------------------------
# Non-empty content
# ---------------------------------------------------------------------------


class TestContentIsNonempty:
    def test_all_content_nonempty(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are an expert.",
            target="general",
            count=4,
            dimensions=None,
        )
        for r in results:
            assert r["content"].strip() != ""

    def test_content_differs_from_original(self):
        """At least some variations should differ from the original content."""
        original = "You are a helpful assistant."
        results = _fallback_section_variations(
            section_name="Role",
            section_content=original,
            target="general",
            count=4,
            dimensions=None,
        )
        contents = [r["content"] for r in results]
        # At least one variation should be different from the original
        assert any(c != original for c in contents)


# ---------------------------------------------------------------------------
# Specific dimensions parameter
# ---------------------------------------------------------------------------


class TestSpecificDimensions:
    def test_restricts_dimensions(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are an expert.",
            target="general",
            count=4,
            dimensions=["tone", "style"],
        )
        dims = {r["dimension"] for r in results}
        assert dims <= {"tone", "style"}

    def test_single_dimension(self):
        results = _fallback_section_variations(
            section_name="Role",
            section_content="You are an expert.",
            target="general",
            count=3,
            dimensions=["audience"],
        )
        dims = {r["dimension"] for r in results}
        assert dims == {"audience"}

    def test_count_respected_with_dimensions(self):
        results = _fallback_section_variations(
            section_name="Task",
            section_content="Analyze data.",
            target="analysis",
            count=2,
            dimensions=["format", "specificity"],
        )
        assert len(results) == 2
