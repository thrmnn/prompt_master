"""Canvas screen — the single screen containing the prompt editor."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Input

from prompt_master.tui.section_block import SectionBlock
from prompt_master.tui.status_line import StatusLine


class Canvas(Screen):
    """Primary screen: scrollable section blocks, floor input, and status line.

    Layout (top to bottom):
        - ScrollableContainer of SectionBlock widgets
        - ConversationZone placeholder (hidden by default)
        - Floor Input (docked bottom, above status line)
        - StatusLine (docked bottom)
    """

    CSS_PATH = Path(__file__).parent / "css" / "canvas.tcss"

    # ── Messages ──────────────────────────────────────────────────────

    class PopulateSections(Message):
        """Request to fill the canvas with the given sections dict."""

        def __init__(self, sections: Dict[str, str]) -> None:
            super().__init__()
            self.sections = sections

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield StatusLine(id="status-line")
        yield Input(
            placeholder="type here to refine, or edit above...",
            id="floor-input",
        )
        with Container(id="conversation-zone"):
            pass
        with ScrollableContainer(id="sections-container"):
            pass

    # ── Section management ────────────────────────────────────────────

    def populate_sections(self, sections: Dict[str, str]) -> None:
        """Replace all SectionBlocks with the given sections dict.

        Args:
            sections: Mapping of ``section_name -> content``.  Entries with
                the key ``"_preamble"`` are skipped (internal to the parser).
        """
        container = self.query_one("#sections-container", ScrollableContainer)
        container.remove_children()
        for name, content in sections.items():
            if name == "_preamble":
                continue
            block = SectionBlock(section_name=name, content=content)
            container.mount(block)

    def get_prompt_text(self) -> str:
        """Assemble the current prompt from all SectionBlocks.

        Returns the prompt in ``# Header\\ncontent`` markdown format,
        matching the output of ``_render_sections`` in ``vibe.py``.
        """
        parts: list[str] = []
        for block in self.query(SectionBlock):
            text = block.get_content()
            parts.append(f"# {block.section_name}\n{text}")
        return "\n\n".join(parts)

    @property
    def status_line(self) -> StatusLine:
        """Convenience accessor for the status line widget."""
        return self.query_one("#status-line", StatusLine)

    # ── Event handlers ────────────────────────────────────────────────

    def on_canvas_populate_sections(self, message: PopulateSections) -> None:
        """Handle the PopulateSections message."""
        self.populate_sections(message.sections)

    def on_section_block_section_focused(
        self, message: SectionBlock.SectionFocused
    ) -> None:
        """Bubble section focus to the app (for attention tracking, etc.)."""
        # The message will continue to bubble to the App.
        pass

    def on_section_block_section_changed(
        self, message: SectionBlock.SectionChanged
    ) -> None:
        """Bubble content changes to the app."""
        # Re-count tokens for the status line
        prompt_text = self.get_prompt_text()
        # Rough token estimate: ~4 chars per token
        token_est = len(prompt_text) // 4
        self.status_line.update_tokens(token_est, 50_000)
