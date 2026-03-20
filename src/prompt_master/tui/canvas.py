"""Canvas — the main container holding the prompt editor."""

from __future__ import annotations

from typing import Dict

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Input, LoadingIndicator, Static

from prompt_master.tui.section_block import SectionBlock
from prompt_master.tui.status_line import StatusLine


class Canvas(Vertical):
    """Primary container: scrollable section blocks, floor input, and status line.

    Layout (top to bottom):
        - ScrollableContainer of SectionBlock widgets
        - ConversationZone (shows last AI exchange, hidden by default)
        - Loading indicator (hidden by default)
        - Floor Input (docked bottom, above status line)
        - StatusLine (docked bottom)
    """

    DEFAULT_CSS = """
    Canvas {
        width: 1fr;
        height: 1fr;
    }

    #conversation-zone {
        display: none;
        width: 1fr;
        height: auto;
        max-height: 8;
        margin: 0 2;
        padding: 0 1;
        border: round $primary-muted;
    }
    #conversation-zone.visible {
        display: block;
    }

    #loading-bar {
        display: none;
        width: 1fr;
        height: 1;
        margin: 0 2;
        color: $accent;
    }
    #loading-bar.visible {
        display: block;
    }
    """

    # ── Messages ──────────────────────────────────────────────────────

    class PopulateSections(Message):
        def __init__(self, sections: Dict[str, str]) -> None:
            super().__init__()
            self.sections = sections

    class UserSubmitted(Message):
        """Posted when user submits text in the floor input."""
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="sections-container"):
            pass
        yield Static("", id="conversation-zone")
        yield LoadingIndicator(id="loading-bar")
        yield Input(
            placeholder="type here to refine, or edit above...",
            id="floor-input",
        )
        yield StatusLine(id="status-line")

    # ── Section management ────────────────────────────────────────────

    def populate_sections(self, sections: Dict[str, str]) -> None:
        container = self.query_one("#sections-container", ScrollableContainer)
        container.remove_children()
        for name, content in sections.items():
            if name == "_preamble":
                continue
            block = SectionBlock(section_name=name, content=content)
            container.mount(block)

    def get_prompt_text(self) -> str:
        parts: list[str] = []
        for block in self.query(SectionBlock):
            text = block.get_content()
            parts.append(f"# {block.section_name}\n{text}")
        return "\n\n".join(parts)

    def update_section(self, name: str, content: str, highlight: bool = True) -> None:
        """Update a specific section by name, optionally with highlight."""
        for block in self.query(SectionBlock):
            if block.section_name == name:
                block.set_content(content)
                if highlight:
                    block.highlight = True
                return
        # Section doesn't exist — add it
        container = self.query_one("#sections-container", ScrollableContainer)
        block = SectionBlock(section_name=name, content=content)
        container.mount(block)
        if highlight:
            block.highlight = True

    @property
    def status_line(self) -> StatusLine:
        return self.query_one("#status-line", StatusLine)

    # ── Loading indicator ─────────────────────────────────────────────

    def show_loading(self, message: str = "") -> None:
        """Show the loading indicator."""
        loader = self.query_one("#loading-bar", LoadingIndicator)
        loader.add_class("visible")
        self.status_line.update(f"thinking... {message}")

    def hide_loading(self) -> None:
        """Hide the loading indicator."""
        loader = self.query_one("#loading-bar", LoadingIndicator)
        loader.remove_class("visible")
        self.status_line._refresh_display()

    # ── Conversation zone ─────────────────────────────────────────────

    def show_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Show the last user/assistant exchange."""
        zone = self.query_one("#conversation-zone", Static)
        zone.update(
            f"[bold blue]You:[/] {user_msg}\n"
            f"[bold green]Claude:[/] {assistant_msg}"
        )
        zone.add_class("visible")
        self.set_timer(8.0, self._dismiss_conversation)

    def _dismiss_conversation(self) -> None:
        try:
            zone = self.query_one("#conversation-zone", Static)
            zone.remove_class("visible")
        except Exception:
            pass

    # ── Event handlers ────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """User pressed Enter in the floor input."""
        text = event.value.strip()
        if text:
            event.input.value = ""
            self.post_message(self.UserSubmitted(text))

    def on_canvas_populate_sections(self, message: PopulateSections) -> None:
        self.populate_sections(message.sections)

    def on_section_block_section_changed(
        self, message: SectionBlock.SectionChanged
    ) -> None:
        prompt_text = self.get_prompt_text()
        token_est = len(prompt_text) // 4
        self.status_line.update_tokens(token_est, 50_000)
