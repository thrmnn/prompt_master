"""Terminal UX: colors, streaming output, banners."""

import click


# ANSI style helpers (Click handles Windows via colorama if installed)
STYLE_BANNER = {"fg": "cyan", "bold": True}
STYLE_ASSISTANT = {"fg": "green"}
STYLE_PROMPT_DRAFT = {"fg": "yellow"}
STYLE_FINAL = {"fg": "green", "bold": True}
STYLE_COMMAND = {"fg": "magenta"}
STYLE_DIM = {"dim": True}
STYLE_ERROR = {"fg": "red", "bold": True}


def show_banner(target: str, session_id: str):
    """Display the chat session banner."""
    click.echo()
    click.echo(click.style("  Prompt Master — Chat Mode", **STYLE_BANNER))
    click.echo(click.style(f"  Target: {target}  |  Session: {session_id[:8]}", **STYLE_DIM))
    click.echo(click.style("  Type /help for commands, /done to finalize", **STYLE_DIM))
    click.echo(click.style("  " + "─" * 50, **STYLE_DIM))
    click.echo()


def show_help():
    """Display available slash commands."""
    commands = [
        ("/done", "Finalize and extract the prompt"),
        ("/draft", "Show the current prompt draft"),
        ("/save", "Save session for later"),
        ("/quit", "Save and exit"),
        ("/help", "Show this help"),
    ]
    click.echo()
    click.echo(click.style("  Commands:", bold=True))
    for cmd, desc in commands:
        click.echo(f"  {click.style(cmd, **STYLE_COMMAND)}  {desc}")
    click.echo()


def show_draft(draft: str):
    """Display the current prompt draft."""
    if not draft:
        click.echo(click.style("  No draft yet — keep chatting!", **STYLE_DIM))
        return
    click.echo()
    click.echo(click.style("  ── Current Draft ──", **STYLE_PROMPT_DRAFT))
    click.echo()
    for line in draft.splitlines():
        click.echo(f"  {line}")
    click.echo()
    click.echo(click.style("  ── End Draft ──", **STYLE_PROMPT_DRAFT))
    click.echo()


def show_final_prompt(prompt: str):
    """Display the finalized prompt."""
    click.echo()
    click.echo(click.style("  ══ Final Prompt ══", **STYLE_FINAL))
    click.echo()
    for line in prompt.splitlines():
        click.echo(f"  {line}")
    click.echo()
    click.echo(click.style("  ══ End Final Prompt ══", **STYLE_FINAL))
    click.echo()


def show_saved(session_id: str):
    """Confirm session save."""
    click.echo(
        click.style(f"\n  Session saved: {session_id[:8]}", **STYLE_DIM)
    )
    click.echo(
        click.style(
            f"  Resume with: prompt-master chat --resume {session_id[:8]}",
            **STYLE_DIM,
        )
    )
    click.echo()


def show_error(message: str):
    """Display an error message."""
    click.echo(click.style(f"  Error: {message}", **STYLE_ERROR), err=True)


def write_stream_token(token: str):
    """Write a single streaming token to stdout (no newline)."""
    click.echo(token, nl=False)


def flush_stream():
    """Flush stdout after streaming is complete, add newlines."""
    click.echo()
    click.echo()
