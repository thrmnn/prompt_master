"""Benchmark runner — orchestrates case loading, prompt generation, and scoring."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from prompt_master.optimizer import optimize_prompt

from prompt_master.benchmarks.judge import JudgeResult, judge_prompt
from prompt_master.benchmarks.scorer import ScoreBreakdown, score_batch

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"


def load_cases(domain: Optional[str] = None) -> List[dict]:
    """Load benchmark cases from TOML files.

    Args:
        domain: If set, load only this domain's cases. Otherwise load all.
    """
    cases = []
    if domain:
        files = [CASES_DIR / f"{domain}.toml"]
    else:
        files = sorted(CASES_DIR.glob("*.toml"))

    for path in files:
        if not path.exists():
            continue
        data = tomllib.loads(path.read_text())
        file_domain = data.get("meta", {}).get("domain", path.stem)
        for case in data.get("cases", []):
            case["domain"] = file_domain
            cases.append(case)
    return cases


def generate_prompts(
    cases: List[dict],
    use_api: bool = True,
) -> Dict[str, dict]:
    """Run prompt optimization for each case.

    Returns:
        Dict mapping case_id → {prompt, used_api, elapsed_ms}.
    """
    results = {}
    for case in cases:
        cid = case["id"]
        domain = case.get("domain", "general")
        idea = case["idea"]

        start = time.monotonic()
        result = optimize_prompt(
            idea=idea,
            target=domain,
            use_api=use_api,
        )
        elapsed = (time.monotonic() - start) * 1000

        results[cid] = {
            "prompt": result.optimized_prompt,
            "used_api": result.used_api,
            "elapsed_ms": round(elapsed, 1),
        }
    return results


def run_benchmark(
    domain: Optional[str] = None,
    use_api: bool = True,
    use_judge: bool = False,
) -> dict:
    """Run the full benchmark pipeline.

    Steps:
        1. Load cases (all domains or one)
        2. Generate optimized prompts for each case
        3. Score structurally (always)
        4. Score with LLM judge (if use_judge=True and API available)
        5. Return aggregated results

    Returns:
        Full benchmark report dict.
    """
    cases = load_cases(domain)
    if not cases:
        return {"error": "No benchmark cases found", "cases": []}

    # Generate prompts
    gen_results = generate_prompts(cases, use_api=use_api)

    # Structural scoring
    prompts_map = {cid: r["prompt"] for cid, r in gen_results.items()}
    structural_scores = score_batch(prompts_map, cases)

    # LLM judge scoring (optional)
    judge_results: Dict[str, JudgeResult] = {}
    if use_judge:
        for case in cases:
            cid = case["id"]
            gen = gen_results.get(cid, {})
            if gen.get("prompt"):
                jr = judge_prompt(
                    case_id=cid,
                    idea=case["idea"],
                    target=case.get("domain", "general"),
                    optimized_prompt=gen["prompt"],
                )
                judge_results[cid] = jr

    # Assemble report
    report = _build_report(cases, gen_results, structural_scores, judge_results)
    return report


def _build_report(
    cases: List[dict],
    gen_results: Dict[str, dict],
    structural_scores: List[ScoreBreakdown],
    judge_results: Dict[str, JudgeResult],
) -> dict:
    """Assemble the final benchmark report."""
    score_map = {s.case_id: s for s in structural_scores}

    case_reports = []
    total_structural_pct = 0.0
    total_judge_avg = 0.0
    judge_count = 0

    for case in cases:
        cid = case["id"]
        gen = gen_results.get(cid, {})
        ss = score_map.get(cid)
        jr = judge_results.get(cid)

        entry = {
            "case_id": cid,
            "case_name": case.get("name", ""),
            "domain": case.get("domain", "general"),
            "difficulty": case.get("difficulty", "unknown"),
            "idea": case["idea"],
            "used_api": gen.get("used_api", False),
            "elapsed_ms": gen.get("elapsed_ms", 0),
            "structural": ss.to_dict() if ss else None,
        }

        if ss:
            total_structural_pct += ss.pct

        if jr:
            entry["judge"] = jr.to_dict()
            if jr.avg_score > 0:
                total_judge_avg += jr.avg_score
                judge_count += 1

        case_reports.append(entry)

    n = len(cases)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": n,
        "domains": list({c.get("domain", "general") for c in cases}),
        "avg_structural_pct": round(total_structural_pct / n, 1) if n else 0,
    }
    if judge_count:
        summary["avg_judge_score"] = round(total_judge_avg / judge_count, 2)

    return {"summary": summary, "cases": case_reports}


def save_report(report: dict, tag: Optional[str] = None) -> Path:
    """Save a benchmark report to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"bench_{tag}_{ts}.json" if tag else f"bench_{ts}.json"
    path = RESULTS_DIR / name
    path.write_text(json.dumps(report, indent=2))
    return path
