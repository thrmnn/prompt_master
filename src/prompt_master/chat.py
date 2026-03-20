"""Main chat loop orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from prompt_master.client import ClaudeClient, NoAPIKeyError
from prompt_master.conversation import ConversationEngine, Phase
from prompt_master.display import (
    flush_stream,
    show_banner,
    show_draft,
    show_error,
    show_final_prompt,
    show_help,
    show_saved,
    write_stream_token,
)
from prompt_master.session import (
    generate_session_id,
    load_session,
    save_session,
)

# Slash commands that exit the input prompt
_QUIT_COMMANDS = {"/quit", "/exit"}
_DONE_COMMANDS = {"/done", "/finish"}


def run_chat(
    idea: Optional[str] = None,
    target: str = "general",
    resume: Optional[str] = None,
    output: Optional[str] = None,
    model: Optional[str] = None,
):
    """Run the interactive chat loop."""
    # ── Initialize or resume session ────────────────────────────────────
    if resume:
        try:
            session_id, engine = load_session(resume)
            click.echo(click.style(f"\n  Resumed session {session_id[:8]}", dim=True))
        except FileNotFoundError as e:
            show_error(str(e))
            return
    else:
        session_id = generate_session_id()
        engine = ConversationEngine(target=target)

    # ── API client ──────────────────────────────────────────────────────
    try:
        client = ClaudeClient(model=model)
    except NoAPIKeyError:
        show_error(
            "No API key found. Set ANTHROPIC_API_KEY to use chat mode."
        )
        return

    show_banner(engine.target, session_id)

    # ── Seed with initial idea if provided ──────────────────────────────
    if idea and not resume:
        click.echo(click.style("  You: ", fg="blue", bold=True) + idea)
        click.echo()
        engine.add_user_message(idea)
        _stream_response(client, engine)

    # ── Main loop ───────────────────────────────────────────────────────
    while engine.phase != Phase.FINALIZED:
        try:
            user_input = click.prompt(
                click.style("  You", fg="blue", bold=True),
                prompt_suffix=": ",
            )
        except (EOFError, KeyboardInterrupt):
            click.echo()
            _save_and_exit(session_id, engine)
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        # ── Slash commands ──────────────────────────────────────────────
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd in _DONE_COMMANDS:
                engine.request_finalization()
                _stream_response(client, engine)
                break

            if cmd in _QUIT_COMMANDS:
                _save_and_exit(session_id, engine)
                return

            if cmd == "/save":
                save_session(session_id, engine)
                show_saved(session_id)
                continue

            if cmd == "/draft":
                show_draft(engine.current_draft)
                continue

            if cmd == "/help":
                show_help()
                continue

            # Unknown command — treat as regular input
            click.echo(click.style(f"  Unknown command: {cmd}", dim=True))
            continue

        # ── Regular message ─────────────────────────────────────────────
        engine.add_user_message(user_input)
        _stream_response(client, engine)

    # ── Finalization ────────────────────────────────────────────────────
    final = engine.final_prompt or engine.current_draft
    if final:
        show_final_prompt(final)

        if output:
            Path(output).write_text(final)
            click.echo(
                click.style(f"  Prompt saved to {output}", dim=True)
            )

        # Auto-save session
        save_session(session_id, engine)
    else:
        click.echo(click.style("  No prompt was generated.", dim=True))


def _stream_response(client: ClaudeClient, engine: ConversationEngine):
    """Stream an assistant response, filtering markers in real-time."""
    sf = engine.create_stream_filter()
    sf.on_text = write_stream_token

    raw_parts: list[str] = []

    click.echo(click.style("  Claude: ", fg="green", bold=True), nl=False)

    try:
        for chunk in client.converse_stream(
            system_prompt=engine.get_system_prompt(),
            messages=engine.get_api_messages(),
        ):
            raw_parts.append(chunk)
            sf.feed(chunk)
    except Exception as e:
        flush_stream()
        show_error(f"API error: {e}")
        return

    sf.flush()
    flush_stream()

    raw_text = "".join(raw_parts)
    engine.update_from_filter(sf, raw_text)


def _save_and_exit(session_id: str, engine: ConversationEngine):
    """Save session and exit."""
    save_session(session_id, engine)
    show_saved(session_id)
