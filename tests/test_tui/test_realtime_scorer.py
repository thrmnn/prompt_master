"""Tests for realtime section scoring — pure-logic scoring without TUI framework."""

from prompt_master.tui.realtime_scorer import (
    compute_overall_score,
    detect_decomposition,
    get_weakness_feedback,
    score_sections,
)


# ---------------------------------------------------------------------------
# Section scoring — Role
# ---------------------------------------------------------------------------


class TestScoreGoodRole:
    def test_expert_role_scores_high(self):
        sections = {
            "Role": "You are an expert data scientist with 10 years of experience in machine learning and statistical modeling.",
        }
        scores = score_sections(sections, target="general")
        assert scores["Role"].score > 7

    def test_detailed_role_scores_high(self):
        sections = {
            "Role": "You are a senior software architect specializing in distributed systems with deep knowledge of cloud infrastructure.",
        }
        scores = score_sections(sections, target="code")
        assert scores["Role"].score > 7


class TestScoreGenericRole:
    def test_helpful_assistant_scores_low(self):
        sections = {
            "Role": "You are a helpful assistant.",
        }
        scores = score_sections(sections, target="general")
        # "helpful assistant" triggers the generic role penalty -- scored below
        # a well-defined expert role (which would be >7)
        assert scores["Role"].score < 7
        assert "generic" in scores["Role"].feedback.lower()

    def test_generic_ai_role_scores_low(self):
        sections = {
            "Role": "You are an AI assistant.",
        }
        scores = score_sections(sections, target="general")
        # "ai assistant" triggers generic role check -- should score lower than expert
        assert scores["Role"].score < 7
        assert "generic" in scores["Role"].feedback.lower()


class TestScoreEmptyRole:
    def test_empty_string_scores_very_low(self):
        sections = {"Role": ""}
        scores = score_sections(sections, target="general")
        # Empty role still gets some base points for non-generic (vacuously true),
        # but should score much lower than a good role
        assert scores["Role"].score < 5
        assert (
            "empty" in scores["Role"].feedback.lower()
            or "missing" in scores["Role"].feedback.lower()
        )

    def test_whitespace_only_scores_very_low(self):
        sections = {"Role": "   "}
        scores = score_sections(sections, target="general")
        # Whitespace-only is nearly as bad as empty
        assert scores["Role"].score < 5


# ---------------------------------------------------------------------------
# Section scoring — Task
# ---------------------------------------------------------------------------


class TestScoreGoodTask:
    def test_specific_task_scores_high(self):
        sections = {
            "Task": "Analyze the provided CSV dataset of customer transactions. Identify the top 5 purchasing patterns, calculate month-over-month growth rates, and generate a summary report with actionable recommendations.",
        }
        scores = score_sections(sections, target="analysis")
        assert scores["Task"].score > 7

    def test_action_verbs_boost_score(self):
        sections = {
            "Task": "Design, implement, and test a REST API endpoint that validates user input, queries the database, and returns paginated results in JSON format.",
        }
        scores = score_sections(sections, target="code")
        assert scores["Task"].score > 7


class TestScoreVagueTask:
    def test_vague_task_scores_low(self):
        sections = {
            "Task": "do the thing",
        }
        scores = score_sections(sections, target="general")
        assert scores["Task"].score < 5

    def test_minimal_task_scores_low(self):
        sections = {
            "Task": "help me",
        }
        scores = score_sections(sections, target="general")
        assert scores["Task"].score < 5


# ---------------------------------------------------------------------------
# Section scoring — Output Format
# ---------------------------------------------------------------------------


class TestScoreMissingFormat:
    def test_no_output_format_scores_zero(self):
        """When Output Format section is provided but empty, its score is 0."""
        sections = {
            "Role": "You are an expert.",
            "Task": "Do the analysis.",
            "Output Format": "",
        }
        scores = score_sections(sections, target="general")
        assert scores["Output Format"].score == 0

    def test_absent_output_format_not_in_scores(self):
        """When Output Format section is not in input at all, it is absent from scores."""
        sections = {
            "Role": "You are an expert.",
            "Task": "Do the analysis.",
        }
        scores = score_sections(sections, target="general")
        # score_sections only scores sections present in the input dict
        assert "Output Format" not in scores


# ---------------------------------------------------------------------------
# Overall score
# ---------------------------------------------------------------------------


class TestOverallScore:
    def test_weighted_average_in_range(self):
        """Overall score (computed from compute_overall_score) is between 0 and 100."""
        sections = {
            "Role": "You are an expert data scientist with deep ML knowledge.",
            "Task": "Analyze customer churn data and build a predictive model using gradient boosting. Evaluate using AUC-ROC.",
            "Output Format": "Return a structured report with:\n- methodology\n- feature importance table\n- model metrics\n- recommendations",
        }
        scores = score_sections(sections, target="analysis")
        overall = compute_overall_score(scores)
        assert 0 <= overall <= 100

    def test_all_empty_sections_overall_very_low(self):
        sections = {"Role": "", "Task": "", "Output Format": ""}
        scores = score_sections(sections, target="general")
        overall = compute_overall_score(scores)
        # All empty sections should produce a very low overall score
        assert overall < 30


# ---------------------------------------------------------------------------
# Weakness feedback
# ---------------------------------------------------------------------------


class TestWeaknessFeedback:
    def test_returns_suggestions_for_weak_sections(self):
        """Sections scoring below 7 should generate feedback."""
        sections = {
            "Role": "You are a helpful assistant.",  # weak: generic
            "Task": "Implement a binary search algorithm in Python with full error handling, type hints, and unit tests.",  # strong
        }
        scores = score_sections(sections, target="code")
        feedback = get_weakness_feedback(scores)
        assert isinstance(feedback, list)
        assert len(feedback) >= 1
        # Should mention the weak section
        combined = " ".join(feedback).lower()
        assert "role" in combined

    def test_no_feedback_when_all_strong(self):
        """When all sections score >= 7, feedback should be empty (no missing-section hints)."""
        sections = {
            "Role": "You are an expert systems architect with 15 years of distributed systems experience.",
            "Task": "Design a fault-tolerant message queue system with exactly-once delivery semantics, supporting 100k messages per second.",
            "Output Format": "Provide a detailed technical specification with:\n- architecture diagrams described in ASCII\n- API contracts in JSON format\n- failure mode analysis with table of scenarios",
            "Requirements": "1. Must handle 100k messages/second\n2. Exactly-once delivery\n3. Sub-100ms latency at p99\n4. Horizontal scalability",
            "Context": "- **Audience:** Senior backend engineers\n- **Platform:** Kubernetes on AWS\n- **Language:** Go or Rust\n- **Constraints:** Must integrate with existing Kafka infrastructure",
        }
        scores = score_sections(sections, target="code")
        feedback = get_weakness_feedback(scores)
        assert isinstance(feedback, list)
        # All sections are strong and all core sections present, so no feedback
        assert len(feedback) == 0


# ---------------------------------------------------------------------------
# Decomposition detection
# ---------------------------------------------------------------------------


class TestDetectDecomposition:
    def test_pipeline_task_detected(self):
        """A task with multiple decomposition signals triggers detection."""
        result = detect_decomposition(
            "build a pipeline that ingests data, then transforms it, followed by loading into a warehouse"
        )
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_workflow_task_detected(self):
        result = detect_decomposition(
            "create a workflow with multiple stages: first, validate input; then process orders; finally, ship items"
        )
        assert result is not None

    def test_multi_step_detected(self):
        result = detect_decomposition(
            "build a multi-agent system that scrapes websites in parallel, then aggregates results sequentially"
        )
        assert result is not None


class TestNoDecomposition:
    def test_simple_task_not_detected(self):
        result = detect_decomposition("write a poem")
        assert result is None

    def test_single_action_not_detected(self):
        result = detect_decomposition("sort a list of numbers")
        assert result is None

    def test_short_task_not_detected(self):
        result = detect_decomposition("hello world")
        assert result is None
