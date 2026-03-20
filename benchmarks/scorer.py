"""Automated structural scoring for optimized prompts.

Evaluates prompts against objective, measurable criteria without requiring
an API call. This is the fast, deterministic layer of the benchmark suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ScoreBreakdown:
    """Detailed scoring results for a single benchmark case."""

    case_id: str
    case_name: str
    total_score: float = 0.0
    max_score: float = 0.0
    checks: List[Dict] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.total_score / self.max_score * 100) if self.max_score else 0.0

    def add(self, name: str, passed: bool, weight: float = 1.0, detail: str = ""):
        self.checks.append({
            "name": name,
            "passed": passed,
            "weight": weight,
            "detail": detail,
        })
        self.max_score += weight
        if passed:
            self.total_score += weight

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "score": self.total_score,
            "max_score": self.max_score,
            "pct": round(self.pct, 1),
            "checks": self.checks,
        }


def score_prompt(prompt: str, case: dict) -> ScoreBreakdown:
    """Score an optimized prompt against a benchmark case definition.

    Checks performed (weights):
      - Section presence (2.0 each)   — expected markdown headers exist
      - Minimum length (1.0)          — prompt meets min character count
      - Required keywords (1.5 each)  — exact keywords present (case-insensitive)
      - Any-of keywords (1.0)         — at least one keyword from a set present
      - Specificity (2.0)             — vague filler words are minimized
      - Structure quality (2.0)       — uses markdown formatting (headers, lists, etc.)
    """
    sb = ScoreBreakdown(
        case_id=case.get("id", "unknown"),
        case_name=case.get("name", "unknown"),
    )

    prompt_lower = prompt.lower()

    # ── Section presence ────────────────────────────────────────────────
    for section in case.get("expect_sections", []):
        pattern = rf"^#{{1,3}}\s+{re.escape(section)}"
        found = bool(re.search(pattern, prompt, re.IGNORECASE | re.MULTILINE))
        sb.add(
            f"section:{section}",
            found,
            weight=2.0,
            detail=f"Header '# {section}' {'found' if found else 'missing'}",
        )

    # ── Minimum length ──────────────────────────────────────────────────
    min_len = case.get("min_length", 0)
    if min_len:
        sb.add(
            "min_length",
            len(prompt) >= min_len,
            weight=1.0,
            detail=f"Length {len(prompt)} vs minimum {min_len}",
        )

    # ── Required keywords (all must appear) ─────────────────────────────
    for kw in case.get("expect_keywords", []):
        found = kw.lower() in prompt_lower
        sb.add(
            f"keyword:{kw}",
            found,
            weight=1.5,
            detail=f"Keyword '{kw}' {'found' if found else 'missing'}",
        )

    # ── Any-of keywords (at least one must appear) ──────────────────────
    any_kws = case.get("expect_keywords_any", [])
    if any_kws:
        found_any = any(kw.lower() in prompt_lower for kw in any_kws)
        matched = [kw for kw in any_kws if kw.lower() in prompt_lower]
        sb.add(
            "keyword_any",
            found_any,
            weight=1.0,
            detail=f"Matched: {matched or 'none'} from {any_kws}",
        )

    # ── Specificity check ───────────────────────────────────────────────
    vague_phrases = [
        "do the thing", "make it good", "be helpful", "as needed",
        "do whatever", "just do it", "some kind of", "figure it out",
    ]
    vague_count = sum(1 for v in vague_phrases if v in prompt_lower)
    sb.add(
        "specificity",
        vague_count == 0,
        weight=2.0,
        detail=f"Vague phrases found: {vague_count}",
    )

    # ── Structure quality ───────────────────────────────────────────────
    has_headers = bool(re.search(r"^#{1,3}\s+\w", prompt, re.MULTILINE))
    has_formatting = bool(
        re.search(r"(\*\*|^\s*[-*]\s|\d+\.)", prompt, re.MULTILINE)
    )
    structure_ok = has_headers and has_formatting
    sb.add(
        "structure",
        structure_ok,
        weight=2.0,
        detail=f"Headers: {has_headers}, formatting: {has_formatting}",
    )

    return sb


def score_batch(prompts: Dict[str, str], cases: List[dict]) -> List[ScoreBreakdown]:
    """Score a batch of prompts against their cases.

    Args:
        prompts: Mapping of case_id → optimized prompt text.
        cases: List of case definitions.

    Returns:
        List of ScoreBreakdown results.
    """
    results = []
    for case in cases:
        cid = case.get("id", "")
        prompt = prompts.get(cid, "")
        if not prompt:
            sb = ScoreBreakdown(case_id=cid, case_name=case.get("name", ""))
            sb.add("prompt_generated", False, weight=5.0, detail="No prompt was generated")
            results.append(sb)
        else:
            results.append(score_prompt(prompt, case))
    return results
