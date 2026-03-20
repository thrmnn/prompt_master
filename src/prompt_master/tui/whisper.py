"""WhisperOverlay — floating contextual hint widget.

Displays dim, non-intrusive hints near the cursor area. Supports
priority-based queuing and deduplication so the user sees only
the most relevant whisper at any moment.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from textual.timer import Timer
from textual.widgets import Static


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class WhisperData:
    """A single contextual hint to display."""

    text: str
    section: str
    priority: int  # 0 = low, 1 = medium, 2 = high
    ttl: float = 8.0  # auto-dismiss after this many seconds


# ---------------------------------------------------------------------------
# WhisperOverlay widget
# ---------------------------------------------------------------------------


class WhisperOverlay(Static):
    """Floating contextual hint near the cursor. Dim, non-intrusive."""

    DEFAULT_CSS = """
    WhisperOverlay {
        dock: right;
        width: 36;
        max-height: 4;
        margin: 1;
        padding: 0 1;
        color: $text-muted;
        background: $surface;
        border: round $primary-muted;
        display: none;
    }
    WhisperOverlay.visible {
        display: block;
    }
    """

    _dismiss_timer: Optional[Timer] = None
    _current_whisper: Optional[WhisperData] = None

    def show_whisper(self, whisper: WhisperData) -> None:
        """Show a whisper. Auto-dismisses after *whisper.ttl* seconds."""
        # Cancel any pending dismiss timer from a previous whisper.
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None

        self._current_whisper = whisper
        self.update(whisper.text)
        self.add_class("visible")

        # Schedule auto-dismiss.
        if whisper.ttl > 0:
            self._dismiss_timer = self.set_timer(whisper.ttl, self.dismiss)

    def dismiss(self) -> None:
        """Immediately hide the whisper."""
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None

        self._current_whisper = None
        self.remove_class("visible")
        self.update("")

    @property
    def current_section(self) -> Optional[str]:
        """Return the section name of the currently displayed whisper."""
        if self._current_whisper is not None:
            return self._current_whisper.section
        return None


# ---------------------------------------------------------------------------
# WhisperQueue — priority queue with deduplication
# ---------------------------------------------------------------------------


class WhisperQueue:
    """Manages whisper priority and deduplication.

    Maintains a bounded deque of recently-shown whisper texts so that
    the same hint is not repeated annoyingly.  Pending whispers are
    stored in a list sorted by descending priority; ties are broken
    by insertion order (FIFO).
    """

    def __init__(self, max_recent: int = 20) -> None:
        self._pending: list[WhisperData] = []
        self._recent: deque[str] = deque(maxlen=max_recent)

    # -- public API ---------------------------------------------------------

    def push(self, whisper: WhisperData) -> bool:
        """Add a whisper to the queue.

        Returns ``False`` if the whisper was suppressed (duplicate of a
        recently-shown hint at the same or lower priority).
        """
        # Suppress exact-text duplicates that were shown recently, unless
        # the new whisper has high priority.
        if whisper.text in self._recent and whisper.priority < 2:
            return False

        self._pending.append(whisper)
        # Keep highest priority at the end so ``pop()`` is O(1).
        self._pending.sort(key=lambda w: w.priority)
        return True

    def pop(self) -> Optional[WhisperData]:
        """Return the highest-priority pending whisper, or ``None``."""
        if not self._pending:
            return None
        whisper = self._pending.pop()  # highest priority (sorted last)
        self._recent.append(whisper.text)
        return whisper

    def clear_for_section(self, section: str) -> None:
        """Remove pending whispers whose *section* matches.

        Useful when the user navigates away from a section — stale
        whispers for that section should not appear later.
        """
        self._pending = [w for w in self._pending if w.section != section]

    def __len__(self) -> int:
        return len(self._pending)

    def __bool__(self) -> bool:
        return bool(self._pending)
