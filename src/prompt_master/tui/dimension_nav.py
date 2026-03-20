"""DimensionNavigator — cursor-driven state space exploration.

A horizontal bar showing the 5 vibe dimensions. Left/Right selects a
dimension, Up/Down cycles through its values. The focused section's
content morphs in real-time as you navigate — no confirmation needed.

This is the "move cursor to steer the prompt" interaction.
"""

from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Horizontal
from textual.app import ComposeResult
from textual import events

from prompt_master.vibe import DIMENSIONS


# Ordered dimension list for navigation
DIM_ORDER = ["tone", "audience", "format", "specificity", "style"]


class DimensionNavigator(Widget):
    """Horizontal dimension bar for continuous prompt exploration.

    Left/Right: select dimension
    Up/Down: cycle value within that dimension
    Esc: close the navigator
    Enter: confirm and close

    Posts DimensionChanged on every value change so the parent
    can morph the section content in real-time.
    """

    DEFAULT_CSS = """
    DimensionNavigator {
        display: none;
        width: 1fr;
        height: 3;
        margin: 0 2;
        padding: 0 1;
        border: tall $accent;
        background: $surface;
    }
    DimensionNavigator.visible {
        display: block;
    }
    DimensionNavigator .dim-bar {
        width: 1fr;
        height: 1;
    }
    DimensionNavigator .dim-slot {
        width: auto;
        min-width: 16;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    DimensionNavigator .dim-slot.active {
        color: $accent;
        text-style: bold;
    }
    DimensionNavigator .dim-hint {
        width: 1fr;
        height: 1;
        color: $text-muted;
        text-style: dim;
    }
    """

    # ── Messages ──────────────────────────────────────────────────────

    class DimensionChanged(Message):
        """Posted when a dimension value changes — section should morph."""
        def __init__(self, section_name: str, dimension: str, value: str) -> None:
            super().__init__()
            self.section_name = section_name
            self.dimension = dimension
            self.value = value

    class NavigatorClosed(Message):
        """Posted when the navigator is dismissed."""
        def __init__(self, section_name: str) -> None:
            super().__init__()
            self.section_name = section_name

    # ── State ─────────────────────────────────────────────────────────

    active_dim_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._section_name: str = ""
        self._dim_values: dict[str, int] = {}  # dimension → current value index
        for dim in DIM_ORDER:
            self._dim_values[dim] = 0

    # ── Public API ────────────────────────────────────────────────────

    def open_for_section(self, section_name: str) -> None:
        """Show the navigator for a specific section."""
        self._section_name = section_name
        self._render_bar()
        self.add_class("visible")
        self.focus()

    def close(self) -> None:
        """Hide the navigator."""
        self.remove_class("visible")
        self.post_message(self.NavigatorClosed(self._section_name))

    @property
    def current_dimension(self) -> str:
        return DIM_ORDER[self.active_dim_index]

    @property
    def current_value(self) -> str:
        dim = self.current_dimension
        values = DIMENSIONS[dim]
        idx = self._dim_values[dim]
        return values[idx]

    def get_all_values(self) -> dict[str, str]:
        """Return current value for each dimension."""
        result = {}
        for dim in DIM_ORDER:
            values = DIMENSIONS[dim]
            idx = self._dim_values[dim]
            result[dim] = values[idx]
        return result

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(classes="dim-bar"):
            for dim in DIM_ORDER:
                values = DIMENSIONS[dim]
                val = values[0]
                yield Static(f"{dim}: {val}", classes="dim-slot")
        yield Static("  ◄► dimension  ▲▼ value  Enter: apply  Esc: cancel", classes="dim-hint")

    # ── Rendering ─────────────────────────────────────────────────────

    def _render_bar(self) -> None:
        """Update all dimension slot displays."""
        slots = list(self.query(".dim-slot"))
        for i, dim in enumerate(DIM_ORDER):
            if i >= len(slots):
                break
            values = DIMENSIONS[dim]
            idx = self._dim_values[dim]
            val = values[idx]

            if i == self.active_dim_index:
                slots[i].update(f"[bold $accent]◄ {dim}: {val} ►[/]")
                slots[i].add_class("active")
            else:
                slots[i].update(f"  {dim}: {val}  ")
                slots[i].remove_class("active")

    def watch_active_dim_index(self, _new: int) -> None:
        self._render_bar()

    # ── Key handling ──────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if not self.has_class("visible"):
            return

        if event.key == "escape":
            self.close()
            event.stop()
            return

        if event.key == "enter":
            self.close()
            event.stop()
            return

        if event.key == "left":
            self.active_dim_index = (self.active_dim_index - 1) % len(DIM_ORDER)
            event.stop()
            return

        if event.key == "right":
            self.active_dim_index = (self.active_dim_index + 1) % len(DIM_ORDER)
            event.stop()
            return

        if event.key in ("up", "down"):
            dim = self.current_dimension
            values = DIMENSIONS[dim]
            idx = self._dim_values[dim]
            if event.key == "up":
                idx = (idx + 1) % len(values)
            else:
                idx = (idx - 1) % len(values)
            self._dim_values[dim] = idx
            self._render_bar()

            # Post change event — section morphs in real-time
            self.post_message(self.DimensionChanged(
                section_name=self._section_name,
                dimension=dim,
                value=values[idx],
            ))
            event.stop()
            return
