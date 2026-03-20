"""SectionBlock widget — an editable prompt section with header and score."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, TextArea


class SectionEditor(TextArea):
    """TextArea subclass that posts a Focused message when it gains focus."""

    class Focused(Message):
        """Posted when this editor gains focus."""

        def __init__(self, section_name: str) -> None:
            super().__init__()
            self.section_name = section_name

    def __init__(self, section_name: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._section_name = section_name

    def watch_has_focus(self, has_focus: bool) -> None:
        if has_focus:
            self.post_message(self.Focused(self._section_name))


class SectionBlock(Widget):
    """An editable prompt section rendered as a header + TextArea.

    The header line shows ``# {section_name}`` on the left and an optional
    score indicator on the right.  The TextArea below holds the editable
    section content.
    """

    DEFAULT_CSS = """
    SectionBlock {
        width: 1fr;
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    SectionBlock .section-row {
        width: 1fr;
        height: 1;
    }

    SectionBlock .section-header {
        width: 1fr;
        height: 1;
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }

    SectionBlock .section-score {
        width: 8;
        height: 1;
        color: $text-muted;
        text-style: dim;
        content-align: right middle;
    }

    SectionBlock TextArea {
        width: 1fr;
        height: auto;
        min-height: 3;
        border: none;
        background: $surface;
        padding: 0 1;
    }

    SectionBlock TextArea:focus {
        border: none;
        background: $boost;
    }
    """

    # ── Messages ──────────────────────────────────────────────────────

    class SectionFocused(Message):
        """Posted when the TextArea in this section receives focus."""

        def __init__(self, section_name: str) -> None:
            super().__init__()
            self.section_name = section_name

    class SectionChanged(Message):
        """Posted when the content of this section is edited."""

        def __init__(self, section_name: str, content: str) -> None:
            super().__init__()
            self.section_name = section_name
            self.content = content

    # ── Reactive properties ───────────────────────────────────────────

    content: reactive[str] = reactive("", layout=True)
    score: reactive[float] = reactive(0.0)
    highlight: reactive[bool] = reactive(False)

    def __init__(
        self,
        section_name: str,
        content: str = "",
        score: float = 0.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.section_name = section_name
        self.content = content
        self.score = score

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(classes="section-row"):
            yield Static(f"# {self.section_name}", classes="section-header")
            yield Static(self._format_score(), classes="section-score", id="score-label")
        yield SectionEditor(
            section_name=self.section_name,
            text=self.content,
            soft_wrap=True,
            show_line_numbers=False,
            id="section-editor",
        )

    # ── Event handling ────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Propagate content changes upward."""
        new_text = event.text_area.text
        # Update the reactive without triggering watch (avoid loop)
        self.set_reactive(SectionBlock.content, new_text)
        self.post_message(self.SectionChanged(self.section_name, new_text))

    def on_section_editor_focused(self, event: SectionEditor.Focused) -> None:
        """Handle focus from the editor and re-post as SectionFocused."""
        self.post_message(self.SectionFocused(event.section_name))

    # ── Watchers ──────────────────────────────────────────────────────

    def watch_score(self, new_score: float) -> None:
        """Update the score label when the reactive changes."""
        try:
            label = self.query_one("#score-label", Static)
            label.update(self._format_score(new_score))
        except Exception:
            pass

    def watch_highlight(self, is_highlighted: bool) -> None:
        """Toggle the AI-highlight visual class."""
        self.remove_class("ai-highlight", "ai-highlight-fade")
        if is_highlighted:
            self.add_class("ai-highlight")
            # Schedule the fade-out
            self.set_timer(1.5, self._fade_highlight)

    # ── Public helpers ────────────────────────────────────────────────

    def set_content(self, text: str) -> None:
        """Programmatically replace the section content."""
        self.content = text
        try:
            editor = self.query_one("#section-editor", TextArea)
            editor.clear()
            editor.insert(text)
        except Exception:
            pass

    def get_content(self) -> str:
        """Return the current content of the TextArea."""
        try:
            editor = self.query_one("#section-editor", TextArea)
            return editor.text
        except Exception:
            return self.content

    # ── Internal ──────────────────────────────────────────────────────

    def _format_score(self, value: float | None = None) -> str:
        """Format the score for display (e.g. '7.2')."""
        val = value if value is not None else self.score
        if val <= 0:
            return ""
        return f"{val:.1f}"

    def _fade_highlight(self) -> None:
        """Transition from highlight to faded, then remove."""
        self.remove_class("ai-highlight")
        self.add_class("ai-highlight-fade")
        self.set_timer(1.0, self._clear_highlight)

    def _clear_highlight(self) -> None:
        """Remove all highlight classes."""
        self.remove_class("ai-highlight-fade")
        self.highlight = False
