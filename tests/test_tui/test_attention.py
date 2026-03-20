"""Tests for AttentionTracker — dwell timing, bounce detection, and reset."""

import time

import pytest

from prompt_master.tui.attention import (
    AttentionTracker,
    BounceEvent,
    BOUNCE_MIN_SWITCHES,
    DeepDwellEvent,
    DEEP_DWELL_THRESHOLD,
    DwellEvent,
    DWELL_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers — simulate the passage of time via monkeypatch
# ---------------------------------------------------------------------------


class FakeClock:
    """Deterministic clock for testing time-dependent logic."""

    def __init__(self, start: float = 1000.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def clock(monkeypatch):
    """Patch time.monotonic with a controllable fake clock."""
    fake = FakeClock()
    monkeypatch.setattr(time, "monotonic", fake)
    return fake


@pytest.fixture
def tracker(clock):
    """Return a fresh AttentionTracker with deterministic time."""
    return AttentionTracker()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_no_current_section(self, tracker):
        assert tracker.current_section is None

    def test_no_history(self, tracker):
        assert tracker.section_history == []


class TestSectionFocus:
    def test_focus_emits_no_events_immediately(self, tracker):
        events = tracker.on_section_focus("Role")
        assert events == []

    def test_focus_sets_current_section(self, tracker):
        tracker.on_section_focus("Role")
        assert tracker.current_section == "Role"

    def test_focus_same_section_is_noop(self, tracker):
        tracker.on_section_focus("Role")
        events = tracker.on_section_focus("Role")
        assert events == []


class TestDwellEvent:
    def test_dwell_event_after_threshold(self, tracker, clock):
        tracker.on_section_focus("Role")
        # Advance past dwell threshold
        clock.advance(DWELL_THRESHOLD + 0.1)
        events = tracker.tick()
        assert len(events) == 1
        assert isinstance(events[0], DwellEvent)
        assert events[0].section == "Role"

    def test_no_dwell_before_threshold(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(DWELL_THRESHOLD - 0.1)
        events = tracker.tick()
        assert events == []


class TestDeepDwellEvent:
    def test_deep_dwell_after_threshold(self, tracker, clock):
        tracker.on_section_focus("Task")
        # Advance past deep dwell threshold
        clock.advance(DEEP_DWELL_THRESHOLD + 0.1)
        events = tracker.tick()
        # Both dwell and deep dwell should fire if neither has been emitted yet
        # Verify dwell events are also present (not asserted, just confirming both types fire)
        assert any(isinstance(e, DwellEvent) and not isinstance(e, DeepDwellEvent) for e in events)
        deep_events = [e for e in events if isinstance(e, DeepDwellEvent)]
        assert len(deep_events) == 1
        assert deep_events[0].section == "Task"

    def test_deep_dwell_is_separate_from_dwell(self, tracker, clock):
        """DwellEvent fires first at 800ms, DeepDwellEvent fires later at 2500ms."""
        tracker.on_section_focus("Task")

        clock.advance(DWELL_THRESHOLD + 0.1)
        events_1 = tracker.tick()
        assert any(isinstance(e, DwellEvent) for e in events_1)
        assert not any(isinstance(e, DeepDwellEvent) for e in events_1)

        clock.advance(DEEP_DWELL_THRESHOLD - DWELL_THRESHOLD + 0.1)
        events_2 = tracker.tick()
        assert any(isinstance(e, DeepDwellEvent) for e in events_2)


class TestDwellNotReEmitted:
    def test_dwell_fires_only_once(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(DWELL_THRESHOLD + 0.1)
        events_1 = tracker.tick()
        assert len([e for e in events_1 if isinstance(e, DwellEvent)]) == 1

        # Subsequent ticks should NOT re-emit DwellEvent
        clock.advance(0.2)
        events_2 = tracker.tick()
        dwell_events = [
            e for e in events_2 if isinstance(e, DwellEvent) and not isinstance(e, DeepDwellEvent)
        ]
        assert dwell_events == []

    def test_deep_dwell_fires_only_once(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(DEEP_DWELL_THRESHOLD + 0.1)
        tracker.tick()  # consumes both

        clock.advance(1.0)
        events = tracker.tick()
        assert events == []


class TestSectionChangeResetsDwell:
    def test_moving_to_new_section_resets_timers(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(DWELL_THRESHOLD - 0.1)  # almost at dwell
        tracker.tick()  # no events yet

        # Switch section — dwell timer resets
        tracker.on_section_focus("Task")
        clock.advance(0.2)  # only 200ms into the new section
        events = tracker.tick()
        assert events == []

    def test_dwell_fires_for_new_section_independently(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(DWELL_THRESHOLD + 0.1)
        events = tracker.tick()
        assert any(isinstance(e, DwellEvent) for e in events)

        # Switch to new section
        clock.advance(0.01)
        tracker.on_section_focus("Task")
        clock.advance(DWELL_THRESHOLD + 0.1)
        events = tracker.tick()
        assert any(isinstance(e, DwellEvent) and e.section == "Task" for e in events)


class TestBounceDetection:
    def test_rapid_switching_emits_bounce(self, tracker, clock):
        """A->B->A->B within BOUNCE_WINDOW triggers BounceEvent."""
        sections = ["A", "B"] * ((BOUNCE_MIN_SWITCHES // 2) + 1)
        all_events = []
        for section in sections:
            clock.advance(0.1)  # rapid switches
            events = tracker.on_section_focus(section)
            all_events.extend(events)
        bounce_events = [e for e in all_events if isinstance(e, BounceEvent)]
        assert len(bounce_events) >= 1
        # The bounce event should reference the current and other section
        assert bounce_events[0].section in ("A", "B")
        assert bounce_events[0].other_section in ("A", "B")

    def test_slow_switching_no_bounce(self, tracker, clock):
        """Switching sections with long gaps should not trigger bounce."""
        all_events = []
        for section in ["A", "B", "A", "B"]:
            clock.advance(5.0)  # well beyond BOUNCE_WINDOW
            events = tracker.on_section_focus(section)
            all_events.extend(events)
        bounce_events = [e for e in all_events if isinstance(e, BounceEvent)]
        assert bounce_events == []


class TestReset:
    def test_reset_clears_current_section(self, tracker):
        tracker.on_section_focus("Role")
        tracker.reset()
        assert tracker.current_section is None

    def test_reset_clears_history(self, tracker, clock):
        tracker.on_section_focus("Role")
        clock.advance(0.1)
        tracker.on_section_focus("Task")
        tracker.reset()
        assert tracker.section_history == []

    def test_reset_clears_dwell_state(self, tracker, clock):
        """After reset, tick should emit nothing (no current section)."""
        tracker.on_section_focus("Role")
        clock.advance(DWELL_THRESHOLD + 0.1)
        tracker.reset()
        events = tracker.tick()
        assert events == []

    def test_tick_with_no_section_returns_empty(self, tracker):
        events = tracker.tick()
        assert events == []
