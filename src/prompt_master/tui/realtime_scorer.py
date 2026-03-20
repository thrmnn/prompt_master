"""Fast, local scoring of prompt sections -- pure heuristics, no API calls.

Every function in this module must complete in <5ms. The scoring is intentionally
opinionated: it encodes the same structural best practices used by the optimizer
and benchmark scorer, but applied at the per-section level for real-time feedback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


# ── Score dataclass ──────────────────────────────────────────────────────────

@dataclass
class SectionScore:
    """Scoring result for a single prompt section."""
    section: str
    score: float   # 0-10
    feedback: str   # one-line explanation

    def __repr__(self) -> str:
        return f"SectionScore({self.section!r}, {self.score}/10, {self.feedback!r})"


# ── Vague / generic patterns ────────────────────────────────────────────────

_VAGUE_PHRASES = [
    "do the thing", "make it good", "be helpful", "as needed",
    "do whatever", "just do it", "some kind of", "figure it out",
    "be nice", "do your best", "whatever works",
]

_GENERIC_ROLES = [
    "helpful assistant", "helpful ai", "ai assistant",
    "language model", "chatbot",
]

_ACTION_VERBS = [
    "analyze", "build", "calculate", "classify", "compare", "compose",
    "convert", "create", "debug", "define", "deploy", "describe", "design",
    "develop", "diagnose", "edit", "evaluate", "explain", "extract",
    "format", "generate", "identify", "implement", "integrate", "list",
    "migrate", "optimize", "outline", "parse", "plan", "prioritize",
    "provide", "rank", "recommend", "refactor", "review", "rewrite",
    "search", "simplify", "solve", "structure", "suggest", "summarize",
    "test", "trace", "transform", "translate", "troubleshoot", "validate",
    "verify", "visualize", "write",
]

_FORMAT_KEYWORDS = [
    "bullet", "numbered", "heading", "section", "table", "code block",
    "fenced", "json", "yaml", "xml", "markdown", "list", "paragraph",
    "step-by-step", "step by step", "report", "outline", "diagram",
    "csv", "checklist",
]

_DECOMPOSITION_SIGNALS = [
    "pipeline", "workflow", "step 1", "step 2", "step 3",
    "then", "after that", "followed by", "next,", "finally,",
    "multiple stages", "stages", "agents", "multi-agent",
    "first,", "second,", "third,",
    "phase 1", "phase 2", "sequentially", "in parallel",
]


# ── Section scorers ─────────────────────────────────────────────────────────

def _score_role(content: str) -> SectionScore:
    """Score the Role section."""
    lower = content.lower()
    score = 0.0
    issues: List[str] = []

    # Has persona marker ("you are")
    if "you are" in lower or "you're" in lower:
        score += 3.0
    else:
        issues.append("missing persona ('you are ...')")

    # Adequate length
    if len(content) > 20:
        score += 2.0
    elif len(content) > 0:
        score += 1.0
        issues.append("very short role definition")
    else:
        issues.append("empty role section")

    # Specificity -- penalize generic roles
    is_generic = any(g in lower for g in _GENERIC_ROLES)
    if is_generic:
        issues.append("generic role (avoid 'helpful assistant')")
    else:
        score += 3.0

    # Bonus: domain/expertise keywords
    expertise_words = ["expert", "specialist", "senior", "skilled", "experienced",
                       "professional", "architect", "engineer", "analyst", "researcher"]
    if any(w in lower for w in expertise_words):
        score += 2.0
    else:
        score += 0.5

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "strong role definition"
    return SectionScore(section="Role", score=score, feedback=feedback)


def _score_task(content: str) -> SectionScore:
    """Score the Task section."""
    lower = content.lower()
    score = 0.0
    issues: List[str] = []

    # Adequate length
    if len(content) > 50:
        score += 3.0
    elif len(content) > 20:
        score += 1.5
        issues.append("task description is short")
    else:
        score += 0.5
        issues.append("task description is very short")

    # No vague phrases
    vague_count = sum(1 for v in _VAGUE_PHRASES if v in lower)
    if vague_count == 0:
        score += 2.0
    else:
        issues.append(f"{vague_count} vague phrase(s) found")

    # Contains action verbs
    has_action = any(v in lower for v in _ACTION_VERBS)
    if has_action:
        score += 3.0
    else:
        issues.append("no clear action verbs found")

    # Subject specificity: at least one word >6 chars that isn't a common verb
    words = re.findall(r"[a-z]+", lower)
    specific_words = [w for w in words if len(w) > 6 and w not in _ACTION_VERBS]
    if specific_words:
        score += 2.0
    else:
        score += 0.5
        issues.append("consider mentioning specific subject matter")

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "well-defined task"
    return SectionScore(section="Task", score=score, feedback=feedback)


def _score_output_format(content: str) -> SectionScore:
    """Score the Output Format section."""
    lower = content.lower()
    score = 0.0
    issues: List[str] = []

    if not content.strip():
        return SectionScore(section="Output Format", score=0.0, feedback="missing output format section")

    # Present
    score += 2.0

    # Adequate length
    if len(content) > 20:
        score += 2.0
    else:
        score += 1.0
        issues.append("output format description is short")

    # Mentions specific formats
    format_hits = sum(1 for f in _FORMAT_KEYWORDS if f in lower)
    if format_hits >= 2:
        score += 4.0
    elif format_hits == 1:
        score += 2.0
        issues.append("consider specifying more format details")
    else:
        issues.append("no specific format keywords found (e.g. bullets, code blocks, sections)")

    # Has structural markers (bullets, numbers, etc.)
    has_structure = bool(re.search(r"(^\s*[-*]\s|\d+\.)", content, re.MULTILINE))
    if has_structure:
        score += 2.0
    else:
        score += 0.5

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "clear output format specification"
    return SectionScore(section="Output Format", score=score, feedback=feedback)


def _score_requirements(content: str) -> SectionScore:
    """Score the Requirements section."""
    lower = content.lower()
    score = 0.0
    issues: List[str] = []

    if not content.strip():
        return SectionScore(section="Requirements", score=0.0, feedback="missing requirements section")

    # Present
    score += 2.0

    # Has concrete constraints (not just "be good")
    vague_only = all(
        v in lower for v in ["good", "nice", "best"]
    ) and len(content) < 30
    if not vague_only:
        score += 2.0
    else:
        issues.append("requirements are too vague")

    # Actionable items (bullets or numbered list)
    items = re.findall(r"(^\s*[-*]\s|^\s*\d+\.)", content, re.MULTILINE)
    if len(items) >= 2:
        score += 3.0
    elif len(items) == 1:
        score += 1.5
        issues.append("consider adding more specific requirements")
    else:
        score += 0.5
        issues.append("use a list to make requirements scannable")

    # Length
    if len(content) > 40:
        score += 2.0
    elif len(content) > 15:
        score += 1.0
    else:
        issues.append("requirements section is very short")

    # Bonus: contains quantifiable constraints
    quantifiable = bool(re.search(r"\d+", content))
    if quantifiable:
        score += 1.0

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "strong, actionable requirements"
    return SectionScore(section="Requirements", score=score, feedback=feedback)


def _score_context(content: str) -> SectionScore:
    """Score the Context section."""
    if not content.strip():
        return SectionScore(section="Context", score=0.0, feedback="missing context section")

    score = 3.0  # Base score for being present
    issues: List[str] = []

    # Length indicates substance
    if len(content) > 80:
        score += 4.0
    elif len(content) > 30:
        score += 2.0
        issues.append("context could use more detail")
    else:
        score += 1.0
        issues.append("context section is very short")

    # Has structure (lists, bold, etc.)
    has_structure = bool(re.search(r"(^\s*[-*]\s|\*\*|\d+\.)", content, re.MULTILINE))
    if has_structure:
        score += 2.0
    else:
        score += 0.5

    # Mentions audience, constraints, or domain
    lower = content.lower()
    context_signals = ["audience", "user", "reader", "customer", "domain",
                       "constraint", "requirement", "scope", "background",
                       "environment", "platform", "framework", "language"]
    signal_hits = sum(1 for s in context_signals if s in lower)
    if signal_hits >= 2:
        score += 1.0
    elif signal_hits == 1:
        score += 0.5

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "relevant context provided"
    return SectionScore(section="Context", score=score, feedback=feedback)


def _score_example(content: str) -> SectionScore:
    """Score the Example section (bonus section)."""
    if not content.strip():
        return SectionScore(section="Example", score=0.0, feedback="no example provided (optional but helpful)")

    score = 5.0  # Generous base for including an example at all
    issues: List[str] = []

    # Length -- examples should be substantial
    if len(content) > 100:
        score += 3.0
    elif len(content) > 30:
        score += 1.5
        issues.append("example could be more detailed")
    else:
        score += 0.5
        issues.append("example is very short")

    # Has code block or structured formatting
    has_code = "```" in content or "    " in content
    has_structure = bool(re.search(r"(^\s*[-*]\s|\d+\.)", content, re.MULTILINE))
    if has_code or has_structure:
        score += 2.0
    else:
        score += 0.5

    score = min(score, 10.0)
    feedback = "; ".join(issues) if issues else "good example included"
    return SectionScore(section="Example", score=score, feedback=feedback)


# ── Section scorer dispatch ──────────────────────────────────────────────────

_SECTION_SCORERS = {
    "Role": _score_role,
    "Task": _score_task,
    "Output Format": _score_output_format,
    "Requirements": _score_requirements,
    "Context": _score_context,
    "Example": _score_example,
}

# Weights for overall score computation (must sum to 1.0 for present sections)
_SECTION_WEIGHTS = {
    "Role": 0.20,
    "Task": 0.30,
    "Output Format": 0.20,
    "Requirements": 0.15,
    "Context": 0.10,
    "Example": 0.05,
}


# ── Public API ───────────────────────────────────────────────────────────────

def score_sections(sections: Dict[str, str], target: str = "general") -> Dict[str, SectionScore]:
    """Score individual sections of a prompt.

    This is the primary entry point. Runs pure heuristic scoring on each
    recognized section and returns a map of section name to score.

    Args:
        sections: Mapping of section name to content (e.g. ``{"Role": "You are ...", ...}``).
        target: Optimization target (currently used for future target-aware scoring).

    Returns:
        Dict mapping section name to ``SectionScore``.
    """
    results: Dict[str, SectionScore] = {}

    for section_name, content in sections.items():
        scorer = _SECTION_SCORERS.get(section_name)
        if scorer is not None:
            results[section_name] = scorer(content)
        # Unknown sections are silently ignored (e.g. "_preamble").

    return results


def compute_overall_score(section_scores: Dict[str, SectionScore]) -> float:
    """Compute a weighted overall prompt score from individual section scores.

    Args:
        section_scores: Output of ``score_sections()``.

    Returns:
        Overall score as a percentage (0.0 -- 100.0).
    """
    if not section_scores:
        return 0.0

    weighted_sum = 0.0
    weight_sum = 0.0

    for name, ss in section_scores.items():
        w = _SECTION_WEIGHTS.get(name, 0.05)
        weighted_sum += (ss.score / 10.0) * w
        weight_sum += w

    if weight_sum == 0.0:
        return 0.0

    return round((weighted_sum / weight_sum) * 100.0, 1)


def get_weakness_feedback(scores: Dict[str, SectionScore]) -> List[str]:
    """Return improvement suggestions for weak sections (score < 7).

    Args:
        scores: Output of ``score_sections()``.

    Returns:
        List of human-readable improvement suggestions, ordered by severity.
    """
    suggestions: List[str] = []

    # Sort by score ascending so worst sections come first
    weak = sorted(
        ((name, ss) for name, ss in scores.items() if ss.score < 7.0),
        key=lambda pair: pair[1].score,
    )

    for name, ss in weak:
        if ss.score == 0.0:
            suggestions.append(f"[{name}] Missing entirely -- add a '# {name}' section.")
        elif ss.score < 4.0:
            suggestions.append(f"[{name}] Needs significant work: {ss.feedback}")
        else:
            suggestions.append(f"[{name}] Could be improved: {ss.feedback}")

    # Suggest missing sections that weren't even in the input
    known = {"Role", "Task", "Output Format", "Requirements", "Context"}
    present = set(scores.keys())
    for missing in sorted(known - present):
        suggestions.append(f"[{missing}] Not present -- consider adding a '# {missing}' section.")

    return suggestions


def detect_decomposition(task_content: str) -> Optional[str]:
    """Detect if a task contains pipeline/workflow language.

    Scans the task content for signals that the user is describing a multi-step
    process, and returns a suggestion to decompose into a workflow if detected.

    Args:
        task_content: The raw text content of the Task section.

    Returns:
        A suggestion string if decomposition is recommended, otherwise None.
    """
    if not task_content:
        return None

    lower = task_content.lower()
    hits = [signal for signal in _DECOMPOSITION_SIGNALS if signal in lower]

    if len(hits) >= 2:
        matched = ", ".join(f"'{h}'" for h in hits[:4])
        return (
            f"This task may describe a multi-step workflow (detected: {matched}). "
            f"Consider using target='workflow' or decomposing into separate agents/stages "
            f"for better results."
        )

    return None
