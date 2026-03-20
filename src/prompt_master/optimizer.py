"""Core prompt optimization pipeline."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from prompt_master.client import ClaudeClient, NoAPIKeyError
from prompt_master.fallback import fallback_optimize

META_SYSTEM_PROMPT = """\
You are an elite prompt engineer. Your job is to take a user's vague idea and transform it into a highly effective, well-structured prompt.

Apply these prompt engineering best practices:
1. **Role Definition** — Start with a clear persona/role for the AI to adopt.
2. **Specific Task Instructions** — Convert vague intent into precise, actionable instructions.
3. **Context & Constraints** — Add relevant context, scope boundaries, and constraints.
4. **Output Format** — Specify exactly how the output should be structured.
5. **Examples** — Include a brief example of expected output when it adds clarity.
6. **Chain of Thought** — When the task involves reasoning, instruct step-by-step thinking.
7. **Parallelization Awareness** — When the task involves a pipeline, system, or \
workflow, identify which subtasks are independent and can run in parallel vs. which \
have sequential dependencies. Decompose into agents or stages where beneficial, and \
specify the orchestration pattern (fan-out/fan-in, pipeline, router, etc.).

Rules:
- Output ONLY the optimized prompt. No explanations, no meta-commentary.
- Use markdown headers (# Role, # Task, etc.) to structure the prompt.
- Make the prompt self-contained — someone reading it with no context should understand exactly what to do.
- Be specific but not verbose. Every word should earn its place.
- Preserve the user's core intent — enhance, don't change what they want.
- When the idea describes a multi-step process or system, propose a multi-agent \
or parallel workflow structure with clear agent roles, handoff points, and a \
dependency graph showing what can run concurrently."""

TARGET_INSTRUCTIONS = {
    "general": "Optimize for a general-purpose LLM interaction.",
    "code": "Optimize for code generation. Include language, framework, error handling, and testing expectations.",
    "creative": "Optimize for creative writing. Include tone, style, voice, and narrative expectations.",
    "analysis": "Optimize for analytical tasks. Include data sources, methodology, and structure for findings.",
    "workflow": (
        "Optimize for multi-agent workflow definition. Decompose the task into "
        "specialized agents with clear roles. Identify parallelizable steps vs. "
        "sequential dependencies. Define the orchestration pattern (fan-out/fan-in, "
        "pipeline, router, hierarchical). Specify inter-agent communication, tool use, "
        "error handling, and fallback strategies. Output a structured workflow definition "
        "with a dependency graph."
    ),
}


@dataclass
class OptimizationResult:
    original_idea: str
    optimized_prompt: str
    target: str
    used_api: bool
    metadata: Dict = field(default_factory=dict)


def optimize_prompt(
    idea: str,
    target: str = "general",
    use_api: bool = True,
    clarifications: Optional[Dict] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> OptimizationResult:
    """Main entry point for optimization."""
    if use_api:
        try:
            return _api_optimize(idea, target, clarifications, model, max_tokens)
        except NoAPIKeyError:
            pass
        except Exception:
            pass  # API error — fall back to template mode

    # Fallback to template-based
    result = fallback_optimize(idea, target, clarifications)
    return OptimizationResult(
        original_idea=idea,
        optimized_prompt=result,
        target=target,
        used_api=False,
    )


def _api_optimize(
    idea: str,
    target: str,
    clarifications: Optional[Dict] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> OptimizationResult:
    """Optimize using the Claude API."""
    client = ClaudeClient(model=model, max_tokens=max_tokens or 4096)

    target_instruction = TARGET_INSTRUCTIONS.get(target, TARGET_INSTRUCTIONS["general"])

    user_parts = [f"**Idea:** {idea}", f"**Target:** {target_instruction}"]

    if clarifications:
        clarification_lines = []
        for key, value in clarifications.items():
            clarification_lines.append(f"- **{key.title()}:** {value}")
        user_parts.append("**Additional Context:**\n" + "\n".join(clarification_lines))

    user_message = "\n\n".join(user_parts)

    optimized = client.generate(META_SYSTEM_PROMPT, user_message)

    return OptimizationResult(
        original_idea=idea,
        optimized_prompt=optimized,
        target=target,
        used_api=True,
        metadata={"usage_summary": client.usage.summary()},
    )
