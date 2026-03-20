"""Template-based prompt optimization (no API key required)."""

from typing import Dict, Optional

from prompt_master.templates import load_template, TemplateNotFoundError

TARGET_ROLES = {
    "general": "You are a knowledgeable and helpful assistant.",
    "code": "You are an expert software engineer with deep knowledge of best practices, design patterns, and clean code principles.",
    "creative": "You are a skilled creative writer with a strong command of language, narrative, and style.",
    "analysis": "You are an analytical expert skilled at breaking down complex topics, evaluating evidence, and drawing clear conclusions.",
    "workflow": (
        "You are a multi-agent systems architect specializing in workflow "
        "decomposition, task parallelization, and orchestration design. You "
        "break complex tasks into specialized agents, identify dependency "
        "graphs, and design robust handoff protocols."
    ),
}

TARGET_TASK_PREFIX = {
    "general": "",
    "code": "Write code that",
    "creative": "Create a piece of writing that",
    "analysis": "Analyze and provide insights on",
    "workflow": "Design a multi-agent workflow that",
}

TARGET_DEFAULT_FORMAT = {
    "general": "Provide a clear, well-structured response.",
    "code": "Provide the code in a fenced code block with the language specified. Include comments for complex logic.",
    "creative": "Write in polished prose with attention to voice and flow.",
    "analysis": "Structure your response with clear sections, evidence-based reasoning, and a summary of key findings.",
    "workflow": (
        "Structure the workflow as:\n"
        "1. **Agents** — List each agent with its role, tools, and responsibilities.\n"
        "2. **Dependency Graph** — Show which steps are parallel vs. sequential.\n"
        "3. **Orchestration** — Define the control flow pattern "
        "(fan-out/fan-in, pipeline, router, hierarchical).\n"
        "4. **Error Handling** — Specify fallback and retry strategies per agent.\n"
        "5. **Data Flow** — Describe what each agent receives and produces."
    ),
}


def fallback_optimize(
    idea: str, target: str = "general", clarifications: Optional[Dict] = None
) -> str:
    """Build an optimized prompt using template slot-filling."""
    clarifications = clarifications or {}

    # Try loading a template for additional defaults
    template = {}
    try:
        template = load_template(target)
    except TemplateNotFoundError:
        pass

    sections = []

    # Role
    role = template.get("role", {}).get("default", TARGET_ROLES.get(target, TARGET_ROLES["general"]))
    sections.append(f"# Role\n{role}")

    # Task
    prefix = template.get("structure", {}).get("task_prefix", TARGET_TASK_PREFIX.get(target, ""))
    if prefix and not idea.lower().startswith(prefix.lower()):
        task_text = f"{prefix} {idea}"
    else:
        task_text = idea
    sections.append(f"# Task\n{task_text}")

    # Context from clarifications
    context_parts = []
    if "audience" in clarifications:
        context_parts.append(f"- **Audience:** {clarifications['audience']}")
    if "constraints" in clarifications:
        context_parts.append(f"- **Constraints:** {clarifications['constraints']}")
    if "language" in clarifications:
        context_parts.append(f"- **Language/Framework:** {clarifications['language']}")
    if "tone" in clarifications:
        context_parts.append(f"- **Tone:** {clarifications['tone']}")
    if "evidence" in clarifications:
        context_parts.append(f"- **Data Sources:** {clarifications['evidence']}")
    if "agents" in clarifications:
        context_parts.append(f"- **Agents/Roles:** {clarifications['agents']}")
    if "orchestration" in clarifications:
        context_parts.append(f"- **Orchestration Pattern:** {clarifications['orchestration']}")
    if "tools" in clarifications:
        context_parts.append(f"- **Tools/APIs:** {clarifications['tools']}")
    if context_parts:
        sections.append("# Context\n" + "\n".join(context_parts))

    # Output format
    fmt = clarifications.get(
        "format",
        template.get("defaults", {}).get("format", TARGET_DEFAULT_FORMAT.get(target, "")),
    )
    if fmt:
        sections.append(f"# Output Format\n{fmt}")

    # Constraints from template
    default_constraints = template.get("defaults", {}).get("constraints", "")
    if default_constraints and "constraints" not in clarifications:
        sections.append(f"# Requirements\n{default_constraints}")

    # Example
    example = clarifications.get("example", "")
    if not example:
        example_data = template.get("example", {})
        if isinstance(example_data, dict):
            example = example_data.get("content", "")
        elif isinstance(example_data, str):
            example = example_data
    if example:
        sections.append(f"# Example\n{example}")

    return "\n\n".join(sections)
