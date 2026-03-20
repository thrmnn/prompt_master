"""Interactive clarifying-question flow."""

import click

QUESTIONS = [
    ("audience", "Who is the intended audience?", ["all"]),
    ("constraints", "Any specific constraints or requirements?", ["all"]),
    ("format", "Desired output format? (prose/bullets/JSON/code/other)", ["all"]),
    ("language", "Programming language and framework?", ["code"]),
    ("tone", "What tone and style? (formal/casual/technical/etc.)", ["creative"]),
    ("evidence", "What data sources should be referenced?", ["analysis"]),
    ("example", "Example of good output? (optional, Enter to skip)", ["all"]),
]


def run_interactive(idea: str, target: str) -> dict:
    """Prompt user with clarifying questions. Return dict of answers."""
    click.echo(f"\nLet me ask a few questions to optimize your prompt.\n")
    click.echo(f"  Your idea: {idea}\n")

    clarifications = {}
    for key, question, targets in QUESTIONS:
        if "all" in targets or target in targets:
            answer = click.prompt(f"  {question}", default="", show_default=False)
            if answer.strip():
                clarifications[key] = answer.strip()

    return clarifications
