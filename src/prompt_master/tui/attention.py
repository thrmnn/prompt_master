"""Attention tracking state machine for cursor position and dwell events.

Tracks which prompt section the user is focused on, measures dwell time,
and emits events that drive the intelligence layer. Pure logic -- no TUI
framework imports required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional


# ── Thresholds (seconds) ─────────────────────────────────────────────────────

DWELL_THRESHOLD = 0.8       # 800ms  -> DwellEvent
DEEP_DWELL_THRESHOLD = 2.5  # 2500ms -> DeepDwellEvent
BOUNCE_WINDOW = 3.0         # Look back N seconds for bounce detection
BOUNCE_MIN_SWITCHES = 3     # Minimum section switches within window to count as bounce


# ── Events ───────────────────────────────────────────────────────────────────

@dataclass
class AttentionEvent:
    """Base class for all attention events."""
    section: str
    timestamp: float


@dataclass
class DwellEvent(AttentionEvent):
    """Cursor has been on this section for >800ms."""
    pass


@dataclass
class DeepDwellEvent(AttentionEvent):
    """Cursor has been on this section for >2500ms."""
    pass


@dataclass
class BounceEvent(AttentionEvent):
    """User is bouncing between sections (uncertainty signal).

    Fired when the user switches focus between sections rapidly,
    indicating they may be uncertain about how to proceed.
    """
    other_section: str = ""


# ── Section transition record ────────────────────────────────────────────────

@dataclass
class _SectionVisit:
    """Internal record of a single section visit."""
    section: str
    entered_at: float


# ── Tracker ──────────────────────────────────────────────────────────────────

@dataclass
class AttentionTracker:
    """State machine that tracks cursor position and emits attention events.

    Intended usage:
        tracker = AttentionTracker()
        # When cursor enters a section:
        events = tracker.on_section_focus("Role")
        # On a periodic timer (every ~200ms):
        events = tracker.tick()
    """

    current_section: Optional[str] = None
    focus_start: float = 0.0
    section_history: List[_SectionVisit] = field(default_factory=list)
    _dwell_emitted: bool = False
    _deep_dwell_emitted: bool = False

    # ── Public API ───────────────────────────────────────────────────────

    def on_section_focus(self, section: str) -> List[AttentionEvent]:
        """Called when the cursor enters a section. Returns any triggered events.

        Handles:
        - Recording the section transition
        - Resetting dwell timers for the new section
        - Detecting bounce patterns (rapid back-and-forth switching)

        Args:
            section: Name of the section that now has focus (e.g. "Role", "Task").

        Returns:
            List of events triggered by this focus change.
        """
        now = time.monotonic()
        events: List[AttentionEvent] = []

        if section == self.current_section:
            # No actual transition -- ignore.
            return events

        previous_section = self.current_section

        # Record the visit we're leaving
        if previous_section is not None:
            self.section_history.append(
                _SectionVisit(section=previous_section, entered_at=self.focus_start)
            )

        # Switch to the new section
        self.current_section = section
        self.focus_start = now
        self._dwell_emitted = False
        self._deep_dwell_emitted = False

        # Check for bounce pattern
        if previous_section is not None:
            bounce = self._detect_bounce(now)
            if bounce is not None:
                events.append(bounce)

        return events

    def tick(self) -> List[AttentionEvent]:
        """Called on a periodic timer (~200ms). Returns dwell events if thresholds crossed.

        Should be called regularly while the user is interacting with the UI.

        Returns:
            List of dwell events (at most one DwellEvent and/or one DeepDwellEvent).
        """
        if self.current_section is None:
            return []

        now = time.monotonic()
        elapsed = now - self.focus_start
        events: List[AttentionEvent] = []

        if not self._dwell_emitted and elapsed >= DWELL_THRESHOLD:
            events.append(DwellEvent(section=self.current_section, timestamp=now))
            self._dwell_emitted = True

        if not self._deep_dwell_emitted and elapsed >= DEEP_DWELL_THRESHOLD:
            events.append(DeepDwellEvent(section=self.current_section, timestamp=now))
            self._deep_dwell_emitted = True

        return events

    def reset(self) -> None:
        """Reset all tracking state."""
        self.current_section = None
        self.focus_start = 0.0
        self.section_history.clear()
        self._dwell_emitted = False
        self._deep_dwell_emitted = False

    # ── Internal ─────────────────────────────────────────────────────────

    def _detect_bounce(self, now: float) -> Optional[BounceEvent]:
        """Detect if the user is bouncing between sections.

        Looks at recent section transitions within ``BOUNCE_WINDOW`` and fires
        a ``BounceEvent`` if the number of switches meets ``BOUNCE_MIN_SWITCHES``.

        Returns:
            A BounceEvent if bouncing is detected, otherwise None.
        """
        cutoff = now - BOUNCE_WINDOW
        recent = [v for v in self.section_history if v.entered_at >= cutoff]

        if len(recent) < BOUNCE_MIN_SWITCHES:
            return None

        # Determine the "other" section: the most recent different section
        other = ""
        for visit in reversed(recent):
            if visit.section != self.current_section:
                other = visit.section
                break

        return BounceEvent(
            section=self.current_section,
            timestamp=now,
            other_section=other,
        )
