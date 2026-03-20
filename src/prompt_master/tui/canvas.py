"""Canvas — the main container holding the prompt editor."""

from __future__ import annotations

from typing import Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Input, LoadingIndicator, Static

from prompt_master.tui.section_block import SectionBlock
from prompt_master.tui.status_line import StatusLine
from prompt_master.tui.dimension_nav import DimensionNavigator
from prompt_master.tui.variation_drawer import VariationDrawer, VariationSelected
from prompt_master.tui.whisper import WhisperOverlay, WhisperData


class Canvas(Vertical):
    """Primary container: prompt sections, variation drawer, whisper, floor input."""

    DEFAULT_CSS = """
    Canvas {
        width: 1fr;
        height: 1fr;
    }

    #conversation-zone {
        display: none;
        width: 1fr;
        height: auto;
        max-height: 6;
        margin: 0 2;
        padding: 0 1;
        border: round $primary-muted;
        color: $text-muted;
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

    class UserSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class ExploreSection(Message):
        """User pressed Tab on a section — request variations."""
        def __init__(self, section_name: str) -> None:
            super().__init__()
            self.section_name = section_name

    class PopulateSections(Message):
        def __init__(self, sections: Dict[str, str]) -> None:
            super().__init__()
            self.sections = sections

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="sections-container"):
            pass
        yield VariationDrawer(section_name="", id="variation-drawer")
        yield DimensionNavigator(id="dimension-nav")
        yield WhisperOverlay(id="whisper")
        yield Static("", id="conversation-zone")
        yield LoadingIndicator(id="loading-bar")
        yield Input(
            placeholder="type here to refine, or edit above... | Tab: explore | Ctrl+C: copy",
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
        for block in self.query(SectionBlock):
            if block.section_name == name:
                block.set_content(content)
                if highlight:
                    block.highlight = True
                return
        container = self.query_one("#sections-container", ScrollableContainer)
        block = SectionBlock(section_name=name, content=content)
        container.mount(block)
        if highlight:
            block.highlight = True

    def get_focused_section(self) -> Optional[str]:
        """Return the name of the currently focused section, if any."""
        for block in self.query(SectionBlock):
            try:
                editor = block.query_one("#section-editor")
                if editor.has_focus:
                    return block.section_name
            except Exception:
                pass
        return None

    @property
    def status_line(self) -> StatusLine:
        return self.query_one("#status-line", StatusLine)

    @property
    def whisper(self) -> WhisperOverlay:
        return self.query_one("#whisper", WhisperOverlay)

    @property
    def drawer(self) -> VariationDrawer:
        return self.query_one("#variation-drawer", VariationDrawer)

    @property
    def dimension_nav(self) -> DimensionNavigator:
        return self.query_one("#dimension-nav", DimensionNavigator)

    # ── Loading ───────────────────────────────────────────────────────

    def show_loading(self, message: str = "") -> None:
        self.query_one("#loading-bar", LoadingIndicator).add_class("visible")
        self.status_line.update(f"thinking... {message}")

    def hide_loading(self) -> None:
        self.query_one("#loading-bar", LoadingIndicator).remove_class("visible")
        self.status_line._refresh_display()

    # ── Whisper ───────────────────────────────────────────────────────

    def show_whisper(self, text: str, section: str, priority: int = 0, ttl: float = 6.0) -> None:
        self.whisper.show_whisper(WhisperData(text=text, section=section, priority=priority, ttl=ttl))

    def dismiss_whisper(self) -> None:
        self.whisper.dismiss()

    # ── Variation drawer ──────────────────────────────────────────────

    def show_variations(self, section_name: str, variations: List[dict]) -> None:
        drawer = self.drawer
        drawer._section_name = section_name
        drawer.show_variations(variations)

    def show_variations_loading(self, section_name: str) -> None:
        drawer = self.drawer
        drawer._section_name = section_name
        drawer.show_loading()

    def hide_variations(self) -> None:
        self.drawer.hide()

    # ── Conversation zone ─────────────────────────────────────────────

    def show_exchange(self, user_msg: str, assistant_msg: str) -> None:
        zone = self.query_one("#conversation-zone", Static)
        zone.update(f"[bold blue]You:[/] {user_msg}\n[bold green]Claude:[/] {assistant_msg}")
        zone.add_class("visible")
        self.set_timer(8.0, self._dismiss_conversation)

    def _dismiss_conversation(self) -> None:
        try:
            self.query_one("#conversation-zone", Static).remove_class("visible")
        except Exception:
            pass

    # ── Event handlers ────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            event.input.value = ""
            self.post_message(self.UserSubmitted(text))

    def on_variation_selected(self, message: VariationSelected) -> None:
        """User picked a variation — apply it to the section."""
        self.update_section(message.section_name, message.variation_text, highlight=True)
        self.hide_variations()

    def on_dimension_navigator_dimension_changed(self, message: DimensionNavigator.DimensionChanged) -> None:
        """Dimension value changed — bubble up for the app to morph the section."""
        pass  # Handled by CanvasApp

    def on_canvas_populate_sections(self, message: PopulateSections) -> None:
        self.populate_sections(message.sections)

    def on_section_block_section_changed(self, message: SectionBlock.SectionChanged) -> None:
        token_est = len(self.get_prompt_text()) // 4
        self.status_line.update_tokens(token_est, 50_000)
