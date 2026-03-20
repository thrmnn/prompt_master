"""VariationDrawer — inline variation picker widget.

Slides open below a prompt section to show alternative phrasings.
The user picks a variation with a number key (1-9) or presses Esc
to dismiss. On selection the widget posts a ``VariationSelected``
message for the parent screen to handle.
"""

from __future__ import annotations

from textual.containers import Container
from textual.message import Message
from textual.widgets import Static, ListView, ListItem
from textual import events


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class VariationSelected(Message):
    """Posted when the user picks a variation."""

    def __init__(self, section_name: str, variation_text: str) -> None:
        self.section_name = section_name
        self.variation_text = variation_text
        super().__init__()


# ---------------------------------------------------------------------------
# Internal helper widgets
# ---------------------------------------------------------------------------

class _VariationItem(Static):
    """A single variation row inside the drawer."""

    DEFAULT_CSS = """
    _VariationItem {
        padding: 0 1;
        height: auto;
        color: $text;
    }
    _VariationItem:hover {
        background: $boost;
    }
    """


class _LoadingIndicator(Static):
    """Shimmer/loading placeholder shown while variations generate."""

    DEFAULT_CSS = """
    _LoadingIndicator {
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self) -> None:
        super().__init__("Generating variations...")


# ---------------------------------------------------------------------------
# VariationDrawer
# ---------------------------------------------------------------------------

class VariationDrawer(Container):
    """Inline variation picker that slides below a section.

    Compose this widget beneath a section display.  Call
    ``show_variations()`` to populate it with choices or
    ``show_loading()`` to display a shimmer state while the
    back-end generates alternatives.
    """

    DEFAULT_CSS = """
    VariationDrawer {
        display: none;
        height: auto;
        max-height: 12;
        border: round $secondary;
        margin: 0 2;
        padding: 0 1;
    }
    VariationDrawer.visible {
        display: block;
    }
    """

    def __init__(self, section_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._section_name = section_name
        self._variations: list[dict] = []

    @property
    def section_name(self) -> str:
        return self._section_name

    # -- public API ---------------------------------------------------------

    def show_variations(self, variations: list[dict]) -> None:
        """Populate and reveal the drawer.

        Each *variation* dict must contain at least:
        - ``dimension`` (str)
        - ``value`` (str)
        - ``content`` (str) — the rewritten section text

        Variations are displayed as a numbered list::

            [1] tone=formal   First 60 chars of preview...
        """
        self._variations = list(variations)
        self._rebuild_children()
        self.add_class("visible")

    def show_loading(self) -> None:
        """Show shimmer/loading state while variations generate."""
        self._variations = []
        self.remove_children()
        self.mount(_LoadingIndicator())
        self.add_class("visible")

    def hide(self) -> None:
        """Close the drawer."""
        self.remove_class("visible")
        self._variations = []

    # -- internals ----------------------------------------------------------

    def _rebuild_children(self) -> None:
        """Re-mount child widgets to reflect ``self._variations``."""
        self.remove_children()
        for idx, var in enumerate(self._variations, start=1):
            dim = var.get("dimension", "?")
            val = var.get("value", "?")
            content = var.get("content", "")
            preview = content.replace("\n", " ")[:60]
            if len(content) > 60:
                preview += "..."
            label = f"[{idx}] {dim}={val}  {preview}"
            self.mount(_VariationItem(label, id=f"var-{idx}"))

    def _select_index(self, index: int) -> None:
        """Select the variation at *index* (1-based) and post a message."""
        if 1 <= index <= len(self._variations):
            var = self._variations[index - 1]
            content = var.get("content", "")
            self.post_message(
                VariationSelected(
                    section_name=self._section_name,
                    variation_text=content,
                )
            )
            self.hide()

    # -- event handlers -----------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Handle number keys for selection, Esc for dismiss."""
        if not self.has_class("visible"):
            return

        if event.key == "escape":
            self.hide()
            event.stop()
            return

        # Number keys 1-9.
        if event.character and event.character.isdigit():
            num = int(event.character)
            if 1 <= num <= len(self._variations):
                self._select_index(num)
                event.stop()

    def on_click(self, event: events.Click) -> None:
        """Allow clicking a variation item to select it."""
        # Walk up from the click target to find a _VariationItem.
        widget = event.widget
        while widget is not None and widget is not self:
            if isinstance(widget, _VariationItem) and widget.id:
                # id is "var-N"
                try:
                    num = int(widget.id.split("-")[1])
                    self._select_index(num)
                except (IndexError, ValueError):
                    pass
                return
            widget = widget.parent
