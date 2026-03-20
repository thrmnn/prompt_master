"""Tests for the benchmarking system."""

import json

import pytest

from benchmarks.runner import load_cases, generate_prompts, run_benchmark
from benchmarks.scorer import ScoreBreakdown, score_prompt, score_batch
from benchmarks.judge import _parse_judge_response, JudgeResult
from benchmarks.report import format_report, format_comparison, _progress_bar


# ── Case loading ────────────────────────────────────────────────────────────


class TestCaseLoading:
    def test_load_all_cases(self):
        cases = load_cases()
        assert len(cases) > 0
        assert all("id" in c for c in cases)
        assert all("idea" in c for c in cases)

    def test_load_cases_by_domain(self):
        for domain in ("general", "code", "creative", "analysis"):
            cases = load_cases(domain)
            assert len(cases) > 0
            assert all(c["domain"] == domain for c in cases)

    def test_load_nonexistent_domain(self):
        cases = load_cases("nonexistent")
        assert cases == []

    def test_cases_have_required_fields(self):
        cases = load_cases()
        for case in cases:
            assert "id" in case, f"Case missing id: {case}"
            assert "idea" in case, f"Case missing idea: {case}"
            assert "name" in case, f"Case missing name: {case}"

    def test_case_ids_are_unique(self):
        cases = load_cases()
        ids = [c["id"] for c in cases]
        assert len(ids) == len(set(ids)), f"Duplicate case IDs: {ids}"


# ── Structural scorer ──────────────────────────────────────────────────────


class TestScorer:
    def test_score_perfect_prompt(self):
        prompt = (
            "# Role\nYou are an expert assistant.\n\n"
            "# Task\nHelp the user write better content.\n\n"
            "# Output Format\n- Use bullet points\n- Be concise"
        )
        case = {
            "id": "test-01",
            "name": "test",
            "expect_sections": ["Role", "Task"],
            "expect_keywords": ["write", "better"],
            "min_length": 50,
        }
        sb = score_prompt(prompt, case)
        assert sb.pct > 80.0

    def test_score_empty_prompt(self):
        sb = score_prompt("", {"id": "t", "name": "t", "min_length": 100})
        assert sb.pct < 50.0

    def test_score_missing_sections(self):
        prompt = "Just do the thing please."
        case = {
            "id": "t",
            "name": "t",
            "expect_sections": ["Role", "Task", "Output Format"],
        }
        sb = score_prompt(prompt, case)
        section_checks = [c for c in sb.checks if c["name"].startswith("section:")]
        assert all(not c["passed"] for c in section_checks)

    def test_score_vague_phrases_penalized(self):
        prompt = "# Role\nHelper\n# Task\nDo whatever. Make it good. As needed."
        case = {"id": "t", "name": "t"}
        sb = score_prompt(prompt, case)
        specificity = [c for c in sb.checks if c["name"] == "specificity"]
        assert len(specificity) == 1
        assert not specificity[0]["passed"]

    def test_score_breakdown_to_dict(self):
        sb = ScoreBreakdown(case_id="t", case_name="test")
        sb.add("check1", True, weight=2.0)
        sb.add("check2", False, weight=1.0)
        d = sb.to_dict()
        assert d["score"] == 2.0
        assert d["max_score"] == 3.0
        assert d["pct"] == pytest.approx(66.7, abs=0.1)

    def test_score_batch(self):
        prompts = {
            "a": "# Role\nExpert\n# Task\nDo stuff\n- list",
            "b": "",
        }
        cases = [
            {"id": "a", "name": "a", "min_length": 10},
            {"id": "b", "name": "b", "min_length": 10},
        ]
        results = score_batch(prompts, cases)
        assert len(results) == 2
        assert results[0].pct > results[1].pct

    def test_keywords_case_insensitive(self):
        prompt = "# Role\nExpert\n# Task\nBuild a REST API with Flask\n- endpoints"
        case = {
            "id": "t",
            "name": "t",
            "expect_keywords": ["flask", "api"],
        }
        sb = score_prompt(prompt, case)
        kw_checks = [c for c in sb.checks if c["name"].startswith("keyword:")]
        assert all(c["passed"] for c in kw_checks)

    def test_any_of_keywords(self):
        prompt = "# Role\n\n# Task\nOptimize for performance and reduce latency\n- steps"
        case = {
            "id": "t",
            "name": "t",
            "expect_keywords_any": ["performance", "speed", "throughput"],
        }
        sb = score_prompt(prompt, case)
        any_check = [c for c in sb.checks if c["name"] == "keyword_any"]
        assert len(any_check) == 1
        assert any_check[0]["passed"]


# ── Judge response parsing ──────────────────────────────────────────────────


class TestJudgeParsing:
    def test_parse_valid_response(self):
        text = (
            "clarity: 4\n"
            "completeness: 3\n"
            "intent_preservation: 5\n"
            "domain_fit: 4\n"
            "structure: 3\n"
            "summary: Good prompt with room for improvement."
        )
        result = _parse_judge_response(text)
        assert result["clarity"] == 4
        assert result["completeness"] == 3
        assert result["intent_preservation"] == 5
        assert result["summary"] == "Good prompt with room for improvement."

    def test_parse_clamps_values(self):
        text = "clarity: 10\ncompleteness: 0\n"
        result = _parse_judge_response(text)
        assert result["clarity"] == 5
        assert result["completeness"] == 1

    def test_parse_handles_garbage(self):
        result = _parse_judge_response("this is not valid output")
        assert result == {}

    def test_judge_result_avg_score(self):
        jr = JudgeResult(
            case_id="t",
            clarity=4, completeness=3,
            intent_preservation=5, domain_fit=4, structure=3,
        )
        assert jr.avg_score == pytest.approx(3.8)

    def test_judge_result_zero_scores(self):
        jr = JudgeResult(case_id="t")
        assert jr.avg_score == 0.0


# ── Report formatting ──────────────────────────────────────────────────────


class TestReport:
    def test_format_report(self):
        report = {
            "summary": {
                "timestamp": "2026-03-20T00:00:00",
                "total_cases": 1,
                "domains": ["general"],
                "avg_structural_pct": 75.0,
            },
            "cases": [
                {
                    "case_id": "gen-01",
                    "case_name": "test",
                    "domain": "general",
                    "difficulty": "easy",
                    "idea": "test idea",
                    "used_api": False,
                    "elapsed_ms": 5.0,
                    "structural": {
                        "case_id": "gen-01",
                        "case_name": "test",
                        "score": 6.0,
                        "max_score": 8.0,
                        "pct": 75.0,
                        "checks": [],
                    },
                }
            ],
        }
        output = format_report(report)
        assert "Benchmark Report" in output
        assert "gen-01" in output
        assert "75.0%" in output

    def test_format_comparison(self):
        report_a = {
            "cases": [
                {"case_id": "t1", "structural": {"pct": 60.0}},
            ]
        }
        report_b = {
            "cases": [
                {"case_id": "t1", "structural": {"pct": 80.0}},
            ]
        }
        output = format_comparison(report_a, report_b, "before", "after")
        assert "before" in output
        assert "after" in output
        assert "+20.0%" in output

    def test_progress_bar(self):
        assert "█" in _progress_bar(50.0)
        assert "░" in _progress_bar(50.0)
        bar_full = _progress_bar(100.0)
        assert "░" not in bar_full


# ── Integration: run_benchmark with --no-api ────────────────────────────────


class TestBenchmarkIntegration:
    def test_run_benchmark_no_api(self):
        """Full benchmark run using template mode (no API needed)."""
        report = run_benchmark(domain="general", use_api=False, use_judge=False)
        assert "error" not in report
        assert report["summary"]["total_cases"] > 0
        assert report["summary"]["avg_structural_pct"] > 0
        assert len(report["cases"]) > 0
        for case in report["cases"]:
            assert not case["used_api"]
            assert case["structural"] is not None

    def test_run_benchmark_all_domains_no_api(self):
        """Benchmark all domains in template mode."""
        report = run_benchmark(use_api=False, use_judge=False)
        domains = {c["domain"] for c in report["cases"]}
        assert domains == {"general", "code", "creative", "analysis", "workflow"}

    def test_generated_prompts_are_nonempty(self):
        """Every case produces a non-empty prompt."""
        cases = load_cases()
        gen = generate_prompts(cases, use_api=False)
        for cid, result in gen.items():
            assert result["prompt"], f"Empty prompt for case {cid}"
            assert result["elapsed_ms"] >= 0
