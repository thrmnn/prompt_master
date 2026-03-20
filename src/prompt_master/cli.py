"""CLI entry point for Prompt Master."""

import sys
from pathlib import Path

import click

from prompt_master.interactive import run_interactive
from prompt_master.optimizer import optimize_prompt
from prompt_master.templates import (
    TemplateNotFoundError,
    list_templates,
    save_template,
    show_template,
)


@click.group(invoke_without_command=True)
@click.version_option(package_name="prompt-master")
@click.pass_context
def main(ctx):
    """Prompt Master — turn vague ideas into optimized prompts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


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
    type=click.Choice(["general", "code", "creative", "analysis"]),
    default="general",
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
def optimize(idea, mode, target, output, no_api):
    """Transform a vague idea into an optimized prompt."""
    clarifications = None

    if mode == "interactive":
        clarifications = run_interactive(idea, target)

    result = optimize_prompt(
        idea=idea,
        target=target,
        use_api=not no_api,
        clarifications=clarifications,
    )

    if not result.used_api and not no_api:
        click.echo(
            "Note: No API key found. Using template-based optimization.\n"
            "Set ANTHROPIC_API_KEY for AI-powered optimization.\n",
            err=True,
        )

    if output:
        Path(output).write_text(result.optimized_prompt)
        click.echo(f"Prompt saved to {output}", err=True)
    else:
        click.echo(result.optimized_prompt)


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
