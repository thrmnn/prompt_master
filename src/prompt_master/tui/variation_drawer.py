"""VariationDrawer — inline variation picker widget.

Slides open below a prompt section to show alternative phrasings.
Number keys 1-9 to pick, Esc to dismiss, click to select.
"""

from __future__ import annotations

from textual.containers import Container
from textual.message import Message
from textual.widgets import Static
from textual import events


class VariationSelected(Message):
    """Posted when the user picks a variation."""

    def __init__(self, section_name: str, variation_text: str) -> None:
        self.section_name = section_name
        self.variation_text = variation_text
        super().__init__()


class _VariationRow(Static):
    """A single variation row. Stores its 1-based index as an attribute."""

    DEFAULT_CSS = """
    _VariationRow {
        width: 1fr;
        padding: 0 1;
        height: auto;
        min-height: 1;
        color: $text;
    }
    _VariationRow:hover {
        background: $boost;
    }
    """

    def __init__(self, content: str, row_index: int) -> None:
        # No id= parameter — avoids DuplicateIds entirely
        super().__init__(content)
        self.row_index = row_index


class VariationDrawer(Container):
    """Inline variation picker."""

    DEFAULT_CSS = """
    VariationDrawer {
        display: none;
        width: 1fr;
        height: auto;
        max-height: 16;
        border: tall $secondary;
        margin: 0 2 1 2;
        padding: 1 1;
        background: $surface;
    }
    VariationDrawer.visible {
        display: block;
    }
    VariationDrawer .drawer-header {
        width: 1fr;
        height: 1;
        color: $secondary;
        text-style: bold;
        margin: 0 0 1 0;
    }
    VariationDrawer .drawer-hint {
        width: 1fr;
        height: 1;
        color: $text-muted;
        text-style: dim;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, section_name: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._section_name = section_name
        self._variations: list[dict] = []

    @property
    def section_name(self) -> str:
        return self._section_name

    @section_name.setter
    def section_name(self, value: str) -> None:
        self._section_name = value

    def show_variations(self, variations: list[dict]) -> None:
        """Populate and reveal the drawer."""
        self._clear()
        self._variations = list(variations)
        self._mount_rows()
        self.add_class("visible")
        self.focus()

    def show_loading(self) -> None:
        """Show loading state."""
        self._clear()
        self.mount(
            Static(
                f"[bold]{self._section_name}[/] — generating variations...",
                classes="drawer-header",
            )
        )
        self.mount(Static("[dim italic]Please wait...[/]"))
        self.add_class("visible")

    def hide(self) -> None:
        """Close the drawer and clean up all children."""
        self.remove_class("visible")
        self._clear()

    def _clear(self) -> None:
        """Remove all child widgets safely."""
        self._variations = []
        children = list(self.children)
        for child in children:
            child.remove()

    def _mount_rows(self) -> None:
        """Mount variation rows from current _variations list."""
        n = len(self._variations)
        self.mount(
            Static(
                f"[bold]{self._section_name}[/] — {n} variation{'s' if n != 1 else ''}",
                classes="drawer-header",
            )
        )

        for idx, var in enumerate(self._variations, start=1):
            dim = var.get("dimension", "?")
            val = var.get("value", "?")
            content = var.get("content", "")
            lines = content.strip().splitlines()
            preview = lines[0][:80] if lines else ""
            if len(lines) > 1:
                preview += f" [dim]...+{len(lines) - 1} lines[/]"

            self.mount(
                _VariationRow(
                    f"  [bold cyan][{idx}][/]  [yellow]{dim}={val}[/]  {preview}",
                    row_index=idx,
                )
            )

        self.mount(Static("[dim]1-9: pick  |  Esc: close[/]", classes="drawer-hint"))

    def _select(self, index: int) -> None:
        """Select variation at 1-based index."""
        if 1 <= index <= len(self._variations):
            var = self._variations[index - 1]
            self.post_message(
                VariationSelected(
                    section_name=self._section_name,
                    variation_text=var.get("content", ""),
                )
            )
            self.hide()

    def on_key(self, event: events.Key) -> None:
        if not self.has_class("visible"):
            return

        if event.key == "escape":
            self.hide()
            event.stop()
            return

        if event.character and event.character.isdigit():
            num = int(event.character)
            if 1 <= num <= len(self._variations):
                self._select(num)
                event.stop()

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        while widget is not None and widget is not self:
            if isinstance(widget, _VariationRow):
                self._select(widget.row_index)
                return
            widget = widget.parent
