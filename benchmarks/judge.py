"""LLM-as-judge evaluation for subjective prompt quality.

Uses Claude to evaluate optimized prompts on dimensions that can't be
measured structurally: clarity, completeness, domain fit, and whether
the original intent was preserved.

This layer is optional and requires an API key. The scorer.py layer
provides the baseline without API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from prompt_master.client import ClaudeClient, NoAPIKeyError

JUDGE_SYSTEM_PROMPT = """\
You are evaluating the quality of an optimized prompt. You will be given:
1. The original vague idea
2. The target domain (general/code/creative/analysis)
3. The optimized prompt produced by a tool

Rate the optimized prompt on these dimensions (1-5 scale each):

- **clarity** — Is the prompt unambiguous? Would an AI know exactly what to do?
- **completeness** — Does it cover the key aspects needed for a good response?
- **intent_preservation** — Does it faithfully represent what the user wanted?
- **domain_fit** — Is it well-tailored to the target domain?
- **structure** — Is it well-organized with clear sections?

Respond in EXACTLY this format (no other text):
clarity: <1-5>
completeness: <1-5>
intent_preservation: <1-5>
domain_fit: <1-5>
structure: <1-5>
summary: <one sentence overall assessment>
"""


@dataclass
class JudgeResult:
    """Results from LLM judge evaluation."""

    case_id: str
    clarity: int = 0
    completeness: int = 0
    intent_preservation: int = 0
    domain_fit: int = 0
    structure: int = 0
    summary: str = ""
    error: str = ""

    @property
    def avg_score(self) -> float:
        scores = [self.clarity, self.completeness, self.intent_preservation,
                  self.domain_fit, self.structure]
        return sum(scores) / len(scores) if any(scores) else 0.0

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "clarity": self.clarity,
            "completeness": self.completeness,
            "intent_preservation": self.intent_preservation,
            "domain_fit": self.domain_fit,
            "structure": self.structure,
            "avg_score": round(self.avg_score, 2),
            "summary": self.summary,
            "error": self.error,
        }


def _parse_judge_response(text: str) -> dict:
    """Parse the structured judge response into a dict."""
    result = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key in ("clarity", "completeness", "intent_preservation",
                    "domain_fit", "structure"):
            try:
                result[key] = max(1, min(5, int(value)))
            except ValueError:
                pass
        elif key == "summary":
            result["summary"] = value
    return result


def judge_prompt(
    case_id: str,
    idea: str,
    target: str,
    optimized_prompt: str,
    client: Optional[ClaudeClient] = None,
) -> JudgeResult:
    """Use Claude to evaluate an optimized prompt's quality.

    Returns a JudgeResult with scores on each dimension. If the API call
    fails, the error field is populated and scores remain at 0.
    """
    if client is None:
        try:
            client = ClaudeClient()
        except NoAPIKeyError:
            return JudgeResult(
                case_id=case_id,
                error="No API key — skipping LLM judge evaluation",
            )

    user_message = (
        f"**Original idea:** {idea}\n"
        f"**Target domain:** {target}\n\n"
        f"**Optimized prompt to evaluate:**\n\n{optimized_prompt}"
    )

    try:
        response = client.generate(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=256,
        )
    except Exception as e:
        return JudgeResult(case_id=case_id, error=str(e))

    parsed = _parse_judge_response(response)
    return JudgeResult(
        case_id=case_id,
        clarity=parsed.get("clarity", 0),
        completeness=parsed.get("completeness", 0),
        intent_preservation=parsed.get("intent_preservation", 0),
        domain_fit=parsed.get("domain_fit", 0),
        structure=parsed.get("structure", 0),
        summary=parsed.get("summary", ""),
    )
