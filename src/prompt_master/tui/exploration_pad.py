"""ExplorationPad — 2D latent space for continuous prompt steering.

A rectangular area where mouse position maps to two vibe dimensions.
As the cursor glides across the pad, the prompt section morphs in
real-time. X axis = one dimension, Y axis = another. The cursor
position is continuous — values snap to the nearest zone but the
movement feels fluid.

This is the "synthesizer XY pad for prompts" interaction.
"""

from __future__ import annotations

from typing import Optional

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from prompt_master.vibe import DIMENSIONS


# Axis pairs the user can cycle through
AXIS_PAIRS = [
    ("tone", "specificity"),
    ("tone", "audience"),
    ("style", "specificity"),
    ("audience", "format"),
    ("style", "audience"),
]

# Pad dimensions
PAD_WIDTH = 50
PAD_HEIGHT = 12


class ExplorationPad(Widget):
    """2D exploration surface. Mouse position → prompt transformation.

    Mouse move within the pad maps X to one dimension, Y to another.
    The prompt section updates on every zone crossing.
    Posts MorphRequest when the position changes zones.
    """

    DEFAULT_CSS = """
    ExplorationPad {
        display: none;
        width: 1fr;
        height: 18;
        margin: 0 2;
        border: heavy $accent;
        background: $surface;
        padding: 0;
    }
    ExplorationPad.visible {
        display: block;
    }
    ExplorationPad .pad-canvas {
        width: 1fr;
        height: 13;
        padding: 0 1;
    }
    ExplorationPad .pad-footer {
        width: 1fr;
        height: 2;
        color: $text-muted;
        text-style: dim;
        padding: 0 2;
    }
    """

    # ── Messages ──────────────────────────────────────────────────────

    class MorphRequest(Message):
        """Posted when the cursor crosses into a new zone."""
        def __init__(
            self,
            section_name: str,
            x_dim: str, x_val: str,
            y_dim: str, y_val: str,
            x_pct: float, y_pct: float,
        ) -> None:
            super().__init__()
            self.section_name = section_name
            self.x_dim = x_dim
            self.x_val = x_val
            self.y_dim = y_dim
            self.y_val = y_val
            self.x_pct = x_pct  # 0.0 to 1.0
            self.y_pct = y_pct

    class PadClosed(Message):
        def __init__(self, section_name: str) -> None:
            super().__init__()
            self.section_name = section_name

    # ── State ─────────────────────────────────────────────────────────

    axis_pair_index: reactive[int] = reactive(0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._section_name: str = ""
        self._cursor_x: float = 0.5  # normalized 0-1
        self._cursor_y: float = 0.5
        self._last_x_val: str = ""
        self._last_y_val: str = ""

    @property
    def x_dim(self) -> str:
        return AXIS_PAIRS[self.axis_pair_index][0]

    @property
    def y_dim(self) -> str:
        return AXIS_PAIRS[self.axis_pair_index][1]

    @property
    def x_values(self) -> list[str]:
        return DIMENSIONS[self.x_dim]

    @property
    def y_values(self) -> list[str]:
        return DIMENSIONS[self.y_dim]

    # ── Public API ────────────────────────────────────────────────────

    def open_for_section(self, section_name: str) -> None:
        self._section_name = section_name
        self._cursor_x = 0.5
        self._cursor_y = 0.5
        self._last_x_val = ""
        self._last_y_val = ""
        self._render_pad()
        self.add_class("visible")
        self.focus()
        # Emit initial position
        self._emit_morph()

    def close(self) -> None:
        self.remove_class("visible")
        self.post_message(self.PadClosed(self._section_name))

    # ── Compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("", classes="pad-canvas", id="pad-canvas")
        yield Static("", classes="pad-footer", id="pad-footer")

    # ── Rendering ─────────────────────────────────────────────────────

    def _render_pad(self) -> None:
        """Render the 2D pad with axis labels and cursor."""
        x_vals = self.x_values
        y_vals = self.y_values

        # Map cursor to current values
        x_idx = int(self._cursor_x * (len(x_vals) - 1) + 0.5)
        x_idx = max(0, min(x_idx, len(x_vals) - 1))
        y_idx = int(self._cursor_y * (len(y_vals) - 1) + 0.5)
        y_idx = max(0, min(y_idx, len(y_vals) - 1))

        cur_x_val = x_vals[x_idx]
        cur_y_val = y_vals[y_idx]

        # Build the pad
        lines = []

        # X axis label
        x_left = x_vals[0]
        x_right = x_vals[-1]
        x_label = f"  {x_left}" + " " * (PAD_WIDTH - len(x_left) - len(x_right) - 4) + f"{x_right}  "
        lines.append(f"[bold]{self.x_dim}:[/] {x_label}")

        # Grid rows
        cursor_col = int(self._cursor_x * (PAD_WIDTH - 1))
        cursor_row = int(self._cursor_y * (PAD_HEIGHT - 1))

        for row in range(PAD_HEIGHT):
            # Y axis label on left
            if row == 0:
                y_label = y_vals[0][:3]
            elif row == PAD_HEIGHT - 1:
                y_label = y_vals[-1][:3]
            elif len(y_vals) > 2 and row == PAD_HEIGHT // 2:
                mid = len(y_vals) // 2
                y_label = y_vals[mid][:3]
            else:
                y_label = "   "

            # Build row characters
            chars = []
            for col in range(PAD_WIDTH):
                if row == cursor_row and col == cursor_col:
                    chars.append("[bold cyan]@[/]")
                elif row == cursor_row or col == cursor_col:
                    chars.append("[dim]·[/]")
                else:
                    chars.append(" ")

            line = f"{y_label:>3} {''.join(chars)}"
            lines.append(line)

        # Current position indicator
        lines.append(f"  [bold cyan]@ {self.x_dim}={cur_x_val}, {self.y_dim}={cur_y_val}[/]")

        try:
            canvas = self.query_one("#pad-canvas", Static)
            canvas.update("\n".join(lines))
        except Exception:
            pass

        # Footer
        try:
            footer = self.query_one("#pad-footer", Static)
            footer.update(
                f"  Move mouse to explore | "
                f"Ctrl+←/→ change axes ({self.x_dim} x {self.y_dim}) | "
                f"Enter: apply | Esc: cancel"
            )
        except Exception:
            pass

    def _pos_to_values(self) -> tuple[str, str]:
        """Map cursor position to the nearest dimension values."""
        x_vals = self.x_values
        y_vals = self.y_values
        x_idx = int(self._cursor_x * (len(x_vals) - 1) + 0.5)
        x_idx = max(0, min(x_idx, len(x_vals) - 1))
        y_idx = int(self._cursor_y * (len(y_vals) - 1) + 0.5)
        y_idx = max(0, min(y_idx, len(y_vals) - 1))
        return x_vals[x_idx], y_vals[y_idx]

    def _emit_morph(self) -> None:
        """Emit a MorphRequest if the zone changed."""
        x_val, y_val = self._pos_to_values()
        if x_val != self._last_x_val or y_val != self._last_y_val:
            self._last_x_val = x_val
            self._last_y_val = y_val
            self.post_message(self.MorphRequest(
                section_name=self._section_name,
                x_dim=self.x_dim, x_val=x_val,
                y_dim=self.y_dim, y_val=y_val,
                x_pct=self._cursor_x, y_pct=self._cursor_y,
            ))

    # ── Event handling ────────────────────────────────────────────────

    def on_mouse_move(self, event: events.MouseMove) -> None:
        """Track mouse position within the pad."""
        if not self.has_class("visible"):
            return

        # Map screen coordinates to 0-1 range within the pad
        # Account for padding/borders
        region = self.content_region
        if region.width <= 0 or region.height <= 0:
            return

        x = max(0.0, min(1.0, event.x / max(region.width, 1)))
        y = max(0.0, min(1.0, event.y / max(region.height, 1)))

        self._cursor_x = x
        self._cursor_y = y
        self._render_pad()
        self._emit_morph()

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

        # Arrow keys for fine control
        step = 0.08
        if event.key == "left":
            self._cursor_x = max(0.0, self._cursor_x - step)
            self._render_pad()
            self._emit_morph()
            event.stop()
        elif event.key == "right":
            self._cursor_x = min(1.0, self._cursor_x + step)
            self._render_pad()
            self._emit_morph()
            event.stop()
        elif event.key == "up":
            self._cursor_y = max(0.0, self._cursor_y - step)
            self._render_pad()
            self._emit_morph()
            event.stop()
        elif event.key == "down":
            self._cursor_y = min(1.0, self._cursor_y + step)
            self._render_pad()
            self._emit_morph()
            event.stop()

        # Cycle axis pairs
        if event.key == "ctrl+right" or event.key == "ctrl+left":
            if event.key == "ctrl+right":
                self.axis_pair_index = (self.axis_pair_index + 1) % len(AXIS_PAIRS)
            else:
                self.axis_pair_index = (self.axis_pair_index - 1) % len(AXIS_PAIRS)
            self._last_x_val = ""
            self._last_y_val = ""
            self._render_pad()
            self._emit_morph()
            event.stop()

    def on_click(self, event: events.Click) -> None:
        """Click to set cursor position."""
        if not self.has_class("visible"):
            return
        region = self.content_region
        if region.width > 0 and region.height > 0:
            self._cursor_x = max(0.0, min(1.0, event.x / max(region.width, 1)))
            self._cursor_y = max(0.0, min(1.0, event.y / max(region.height, 1)))
            self._render_pad()
            self._emit_morph()

    def watch_axis_pair_index(self, _new: int) -> None:
        if self.has_class("visible"):
            self._render_pad()
