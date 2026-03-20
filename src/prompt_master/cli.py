"""CLI entry point for Prompt Master."""

import json
import sys
from pathlib import Path

import click

from prompt_master.chat import run_chat
from prompt_master.config import get as config_get
from prompt_master.interactive import run_interactive
from prompt_master.optimizer import optimize_prompt
from prompt_master.templates import (
    TemplateNotFoundError,
    list_templates,
    save_template,
    show_template,
)
from prompt_master.validation import ValidationError, validate_idea

ALL_TARGETS = ["general", "code", "creative", "analysis", "workflow"]


@click.group(invoke_without_command=True)
@click.version_option(package_name="prompt-master")
@click.pass_context
def main(ctx):
    """Prompt Master — turn vague ideas into optimized prompts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── optimize ────────────────────────────────────────────────────────────────


@main.command()
@click.argument("idea")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["quick", "interactive"]),
    default="quick",
    help="Quick generates immediately; interactive asks clarifying questions first.",
)
@click.option(
    "--target",
    "-t",
    type=click.Choice(ALL_TARGETS),
    default=None,
    help="Target domain for the prompt.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write result to a file instead of stdout.",
)
@click.option(
    "--no-api",
    is_flag=True,
    default=False,
    help="Force template-based mode (no API call).",
)
@click.option(
    "--model",
    type=click.Choice(["sonnet", "haiku", "opus"]),
    default=None,
    help="Claude model to use (default: from config or sonnet).",
)
@click.option(
    "--max-tokens",
    type=int,
    default=None,
    help="Maximum output tokens (default: 4096).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "plain"]),
    default=None,
    help="Output format.",
)
def optimize(idea, mode, target, output, no_api, model, max_tokens, output_format):
    """Transform a vague idea into an optimized prompt."""
    target = target or config_get("target", "general")
    model = model or config_get("model", "sonnet")
    max_tokens = max_tokens or config_get("max_tokens", 4096)
    output_format = output_format or config_get("format", "markdown")

    try:
        idea = validate_idea(idea)
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    clarifications = None
    if mode == "interactive":
        clarifications = run_interactive(idea, target)

    result = optimize_prompt(
        idea=idea,
        target=target,
        use_api=not no_api,
        clarifications=clarifications,
        model=model,
        max_tokens=max_tokens,
    )

    if not result.used_api and not no_api:
        click.echo(
            "Note: No API key found. Using template-based optimization.\n"
            "Set ANTHROPIC_API_KEY for AI-powered optimization.\n",
            err=True,
        )

    # Format output
    formatted = _format_output(result, output_format)

    if output:
        Path(output).write_text(formatted)
        click.echo(f"Prompt saved to {output}", err=True)
    else:
        click.echo(formatted)

    # Record to history
    from prompt_master.history import record

    record(
        idea=result.original_idea,
        optimized_prompt=result.optimized_prompt,
        target=result.target,
        used_api=result.used_api,
        model=model if result.used_api else None,
    )

    # Show usage stats if API was used
    if result.used_api and result.metadata.get("usage_summary"):
        click.echo(
            click.style(f"\n  {result.metadata['usage_summary']}", dim=True),
            err=True,
        )


def _format_output(result, fmt: str) -> str:
    """Format an OptimizationResult for the given output format."""
    if fmt == "json":
        return json.dumps(
            {
                "original_idea": result.original_idea,
                "optimized_prompt": result.optimized_prompt,
                "target": result.target,
                "used_api": result.used_api,
            },
            indent=2,
        )
    elif fmt == "plain":
        # Strip markdown formatting
        lines = []
        for line in result.optimized_prompt.splitlines():
            if line.startswith("#"):
                line = line.lstrip("#").strip().upper()
            lines.append(line)
        return "\n".join(lines)
    else:
        return result.optimized_prompt


# ── chat ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("idea", default="")
@click.option(
    "--target",
    "-t",
    type=click.Choice(ALL_TARGETS),
    default=None,
    help="Target domain for the prompt.",
)
@click.option(
    "--resume",
    "-r",
    default=None,
    help="Resume a previous session by ID (full or prefix).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Save the final prompt to a file.",
)
@click.option(
    "--model",
    type=click.Choice(["sonnet", "haiku", "opus"]),
    default=None,
    help="Claude model to use.",
)
def chat(idea, target, resume, output, model):
    """Start an interactive chat session to build a prompt collaboratively."""
    target = target or config_get("target", "general")
    model = model or config_get("model", "sonnet")
    run_chat(
        idea=idea or None,
        target=target,
        resume=resume,
        output=output,
        model=model,
    )


# ── vibe ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("idea")
@click.option(
    "--target",
    "-t",
    type=click.Choice(ALL_TARGETS),
    default=None,
    help="Target domain.",
)
@click.option(
    "--count",
    "-n",
    type=int,
    default=4,
    help="Number of variations to generate (default: 4).",
)
@click.option(
    "--dimensions",
    "-d",
    default=None,
    help="Comma-separated dimensions to vary (tone,audience,format,specificity,style).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Save all variations to a file.",
)
@click.option(
    "--no-api",
    is_flag=True,
    default=False,
    help="Use template-based variations (no API).",
)
def vibe(idea, target, count, dimensions, output, no_api):
    """Generate prompt variations along different dimensions (Vibe Mode)."""
    from prompt_master.vibe import VibeEngine, DIMENSIONS

    target = target or config_get("target", "general")

    try:
        idea = validate_idea(idea)
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    dim_list = None
    if dimensions:
        dim_list = [d.strip() for d in dimensions.split(",")]
        invalid = [d for d in dim_list if d not in DIMENSIONS]
        if invalid:
            click.echo(
                f"Error: Unknown dimensions: {', '.join(invalid)}. "
                f"Valid: {', '.join(DIMENSIONS.keys())}",
                err=True,
            )
            sys.exit(1)

    click.echo(click.style("\n  Vibe Mode", fg="magenta", bold=True))
    click.echo(click.style(f"  Idea: {idea}", dim=True))
    click.echo(click.style(f"  Target: {target}  |  Variations: {count}", dim=True))
    click.echo(click.style("  " + "─" * 50, dim=True))
    click.echo()

    engine = VibeEngine(idea=idea, target=target)

    if no_api:
        engine._client = None  # Force fallback
        variations = engine._fallback_variations(count, dim_list)
        engine.variations.extend(variations)
    else:
        try:
            variations = engine.generate_variations(count=count, dimensions=dim_list)
        except Exception as e:
            click.echo(f"  Error generating variations: {e}", err=True)
            # Fall back
            variations = engine._fallback_variations(count, dim_list)
            engine.variations = variations

    if not variations:
        click.echo("  No variations generated.", err=True)
        sys.exit(1)

    # Display variations
    output_lines = []
    for i, v in enumerate(variations):
        header = click.style(
            f"  ── Variation {i + 1}: {v.dimension} = {v.value} ──",
            fg="magenta",
        )
        click.echo(header)
        click.echo()
        for line in v.prompt.splitlines():
            click.echo(f"  {line}")
        click.echo()

        output_lines.append(f"## Variation {i + 1}: {v.dimension} = {v.value}\n")
        output_lines.append(v.prompt)
        output_lines.append("\n---\n")

    # Summary
    dims_used = {v.dimension for v in variations}
    click.echo(
        click.style(
            f"  Generated {len(variations)} variations across: {', '.join(sorted(dims_used))}",
            dim=True,
        )
    )
    click.echo()

    if output:
        Path(output).write_text("\n".join(output_lines))
        click.echo(click.style(f"  Variations saved to {output}", dim=True))


# ── tui ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("idea", default="")
@click.option(
    "--target",
    "-t",
    type=click.Choice(ALL_TARGETS),
    default=None,
    help="Target domain.",
)
@click.option(
    "--resume",
    "-r",
    default=None,
    help="Resume a previous session.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Save final prompt to file on exit.",
)
@click.option(
    "--model",
    type=click.Choice(["sonnet", "haiku", "opus"]),
    default=None,
    help="Claude model to use.",
)
@click.option(
    "--no-api",
    is_flag=True,
    default=False,
    help="Offline mode (template-based only).",
)
def tui(idea, target, resume, output, model, no_api):
    """Open the interactive canvas for visual prompt crafting."""
    target = target or config_get("target", "general")
    model = model or config_get("model", "sonnet")
    from prompt_master.tui import launch_tui
    launch_tui(
        idea=idea or None,
        target=target,
        resume=resume,
        output=output,
        model=model,
        no_api=no_api,
    )


# ── benchmark ───────────────────────────────────────────────────────────────


@main.command()
@click.option(
    "--domain",
    "-d",
    type=click.Choice(ALL_TARGETS),
    default=None,
    help="Run benchmarks for a specific domain only.",
)
@click.option(
    "--no-api",
    is_flag=True,
    default=False,
    help="Benchmark template-based mode only (no API calls).",
)
@click.option(
    "--judge",
    is_flag=True,
    default=False,
    help="Include LLM-as-judge evaluation (slower, requires API).",
)
@click.option(
    "--save",
    "save_results",
    is_flag=True,
    default=False,
    help="Save results to benchmarks/results/ as JSON.",
)
@click.option(
    "--tag",
    default=None,
    help="Tag for the saved results file.",
)
def benchmark(domain, no_api, judge, save_results, tag):
    """Run the benchmark suite to evaluate prompt quality."""
    from benchmarks.report import format_report
    from benchmarks.runner import run_benchmark, save_report

    click.echo("\n  Running benchmarks...\n")
    report = run_benchmark(
        domain=domain,
        use_api=not no_api,
        use_judge=judge,
    )

    if "error" in report:
        click.echo(f"  Error: {report['error']}", err=True)
        sys.exit(1)

    click.echo(format_report(report))

    if save_results:
        path = save_report(report, tag=tag)
        click.echo(f"  Results saved to {path}\n")


# ── history ─────────────────────────────────────────────────────────────────


@main.group()
def history():
    """Browse prompt generation history."""
    pass


@history.command("list")
@click.option("--limit", "-n", default=20, help="Number of entries to show.")
def history_list(limit):
    """List recent prompt generations."""
    from prompt_master.history import load_history

    entries = load_history(limit=limit)
    if not entries:
        click.echo("  No history yet.")
        return

    for entry in reversed(entries):
        ts = entry.get("timestamp", "")[:19]
        target = entry.get("target", "")
        api_tag = "API" if entry.get("used_api") else "TPL"
        idea = entry.get("idea", "")[:60]
        click.echo(f"  {ts}  [{api_tag}] [{target}]  {idea}")


@history.command("show")
@click.argument("index", type=int, default=0)
def history_show(index):
    """Show a specific history entry (0 = most recent)."""
    from prompt_master.history import load_history

    entries = load_history(limit=100)
    if not entries:
        click.echo("  No history yet.")
        return

    entries = list(reversed(entries))
    if index >= len(entries):
        click.echo(f"  Index {index} out of range (max {len(entries) - 1}).", err=True)
        return

    entry = entries[index]
    click.echo(f"\n  Idea: {entry.get('idea', '')}")
    click.echo(f"  Target: {entry.get('target', '')}  |  API: {entry.get('used_api', False)}")
    click.echo(f"  Time: {entry.get('timestamp', '')[:19]}")
    click.echo(f"\n{entry.get('prompt', '')}\n")


@history.command("clear")
def history_clear():
    """Clear all history."""
    from prompt_master.history import clear_history

    count = clear_history()
    click.echo(f"  Cleared {count} history entries.")


# ── sessions ────────────────────────────────────────────────────────────────


@main.group()
def sessions():
    """Manage chat sessions."""
    pass


@sessions.command("list")
def sessions_list():
    """List all saved sessions."""
    from prompt_master.session import list_sessions

    session_list = list_sessions()
    if not session_list:
        click.echo("  No saved sessions.")
        return

    for s in session_list:
        sid = s["session_id"][:8]
        ts = s.get("created_at", "")[:19]
        target = s.get("target", "")
        phase = s.get("phase", "")
        msgs = s.get("message_count", 0)
        preview = s.get("preview", "")[:50]
        click.echo(f"  {sid}  {ts}  [{target}] {phase}  ({msgs} msgs)  {preview}")


@sessions.command("prune")
@click.option(
    "--older-than",
    type=int,
    default=30,
    help="Delete sessions older than N days (default: 30).",
)
def sessions_prune(older_than):
    """Delete old sessions."""
    from prompt_master.session import prune_sessions

    count = prune_sessions(older_than_days=older_than)
    click.echo(f"  Pruned {count} sessions older than {older_than} days.")


@sessions.command("delete")
@click.argument("session_id")
def sessions_delete(session_id):
    """Delete a specific session."""
    from prompt_master.session import delete_session

    if delete_session(session_id):
        click.echo(f"  Session {session_id[:8]} deleted.")
    else:
        click.echo(f"  No session found matching '{session_id}'.", err=True)


# ── templates ───────────────────────────────────────────────────────────────


@main.group()
def templates():
    """Manage prompt templates."""
    pass


@templates.command("list")
def templates_list():
    """List all available templates."""
    tmpl_list = list_templates()
    if not tmpl_list:
        click.echo("No templates found.")
        return

    for t in tmpl_list:
        source_tag = f" [{t['source']}]" if t["source"] == "user" else ""
        desc = f" — {t['description']}" if t["description"] else ""
        click.echo(f"  {t['name']}{source_tag}{desc}")


@templates.command("show")
@click.argument("name")
def templates_show(name):
    """Show the contents of a template."""
    try:
        content = show_template(name)
        click.echo(content)
    except TemplateNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@templates.command("save")
@click.argument("name")
@click.option("--from", "from_path", required=True, type=click.Path(exists=True))
def templates_save(name, from_path):
    """Save a custom template."""
    try:
        dest = save_template(name, from_path)
        click.echo(f"Template '{name}' saved to {dest}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
