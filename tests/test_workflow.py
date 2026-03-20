"""Tests for the workflow target domain and parallelization awareness."""

import pytest
from click.testing import CliRunner

from prompt_master.cli import main
from prompt_master.fallback import fallback_optimize, TARGET_ROLES, TARGET_TASK_PREFIX, TARGET_DEFAULT_FORMAT
from prompt_master.optimizer import META_SYSTEM_PROMPT, TARGET_INSTRUCTIONS
from prompt_master.prompts import TARGET_HINTS, build_system_prompt


class TestWorkflowTarget:
    """Verify the workflow target is wired through all layers."""

    def test_target_instructions_has_workflow(self):
        assert "workflow" in TARGET_INSTRUCTIONS
        assert "agent" in TARGET_INSTRUCTIONS["workflow"].lower()
        assert "parallel" in TARGET_INSTRUCTIONS["workflow"].lower()

    def test_target_roles_has_workflow(self):
        assert "workflow" in TARGET_ROLES
        assert "agent" in TARGET_ROLES["workflow"].lower()

    def test_target_task_prefix_has_workflow(self):
        assert "workflow" in TARGET_TASK_PREFIX
        assert "workflow" in TARGET_TASK_PREFIX["workflow"].lower()

    def test_target_default_format_has_workflow(self):
        assert "workflow" in TARGET_DEFAULT_FORMAT
        fmt = TARGET_DEFAULT_FORMAT["workflow"]
        assert "agent" in fmt.lower()
        assert "dependency" in fmt.lower()
        assert "orchestration" in fmt.lower()
        assert "error" in fmt.lower()

    def test_target_hints_has_workflow(self):
        assert "workflow" in TARGET_HINTS
        assert "parallel" in TARGET_HINTS["workflow"].lower()

    def test_build_system_prompt_workflow(self):
        prompt = build_system_prompt("workflow")
        assert "workflow" in prompt.lower()
        assert "agent" in prompt.lower()


class TestParallelizationAwareness:
    """Verify parallelization is baked into the meta-prompt."""

    def test_meta_prompt_has_parallelization_principle(self):
        assert "parallelization" in META_SYSTEM_PROMPT.lower()

    def test_meta_prompt_mentions_agents(self):
        assert "agent" in META_SYSTEM_PROMPT.lower()

    def test_meta_prompt_mentions_orchestration(self):
        assert "orchestrat" in META_SYSTEM_PROMPT.lower()

    def test_meta_prompt_mentions_dependency(self):
        assert "dependenc" in META_SYSTEM_PROMPT.lower()

    def test_chat_system_prompt_has_parallelization(self):
        prompt = build_system_prompt("general")
        assert "parallelization" in prompt.lower()


class TestWorkflowFallback:
    """Test template-based optimization for workflow target."""

    def test_fallback_workflow_basic(self):
        result = fallback_optimize("build a data pipeline", target="workflow")
        assert "# Role" in result
        assert "# Task" in result
        assert "workflow" in result.lower() or "agent" in result.lower()

    def test_fallback_workflow_includes_idea(self):
        result = fallback_optimize("automated testing pipeline", target="workflow")
        assert "testing pipeline" in result.lower()

    def test_fallback_workflow_with_agent_clarifications(self):
        result = fallback_optimize(
            "data processing system",
            target="workflow",
            clarifications={
                "agents": "Fetcher, Transformer, Loader",
                "orchestration": "pipeline",
                "tools": "requests, pandas, sqlalchemy",
            },
        )
        assert "Fetcher" in result
        assert "pipeline" in result.lower()
        assert "pandas" in result.lower()

    def test_fallback_workflow_has_format_section(self):
        result = fallback_optimize("code review system", target="workflow")
        assert "# Output Format" in result
        # Should mention agents and dependency graph
        fmt_section = result.split("# Output Format")[1]
        assert "agent" in fmt_section.lower()


class TestWorkflowCLI:
    """CLI integration for workflow target."""

    def test_optimize_workflow_target(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["optimize", "build a CI pipeline", "-t", "workflow", "--no-api"]
        )
        assert result.exit_code == 0
        assert "# Role" in result.output
        assert "workflow" in result.output.lower() or "agent" in result.output.lower()

    def test_chat_accepts_workflow_target(self):
        runner = CliRunner()
        result = runner.invoke(main, ["chat", "--help"])
        assert "workflow" in result.output

    def test_benchmark_accepts_workflow_domain(self):
        runner = CliRunner()
        result = runner.invoke(main, ["benchmark", "-d", "workflow", "--no-api"])
        assert result.exit_code == 0
        assert "wf-" in result.output


class TestWorkflowBenchmarkCases:
    """Verify workflow benchmark cases load and score."""

    def test_workflow_cases_load(self):
        from benchmarks.runner import load_cases
        cases = load_cases("workflow")
        assert len(cases) == 5
        assert all(c["domain"] == "workflow" for c in cases)

    def test_workflow_benchmark_runs(self):
        from benchmarks.runner import run_benchmark
        report = run_benchmark(domain="workflow", use_api=False, use_judge=False)
        assert report["summary"]["total_cases"] == 5
        assert report["summary"]["avg_structural_pct"] > 0

    def test_workflow_cases_have_agent_keywords(self):
        from benchmarks.runner import load_cases
        cases = load_cases("workflow")
        for case in cases:
            assert "agent" in case.get("expect_keywords", []) or \
                   any("agent" in kw.lower() for kw in case.get("expect_keywords_any", []))
