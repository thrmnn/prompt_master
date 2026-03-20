"""ConversationZone — ephemeral inline dialogue surface.

Appears between the prompt canvas and the floor input area to show
the latest user/assistant exchange. Auto-fades after a configurable
timeout so the prompt remains the visual focus.
"""

from __future__ import annotations

from typing import Optional

from textual.containers import Container
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class PromptUpdated(Message):
    """Posted when an AI response contains prompt section updates.

    The parent screen can listen for this to apply edits to the
    prompt canvas.
    """

    def __init__(self, sections: dict[str, str]) -> None:
        self.sections = sections  # {section_name: new_content}
        super().__init__()


# ---------------------------------------------------------------------------
# Internal sub-widgets
# ---------------------------------------------------------------------------

class _UserBubble(Static):
    """Displays the user's message in the conversation zone."""

    DEFAULT_CSS = """
    _UserBubble {
        color: $text;
        background: $primary-muted;
        padding: 0 1;
        margin: 0 0 0 4;
        height: auto;
        max-height: 2;
    }
    """


class _AssistantBubble(Static):
    """Displays the assistant's response in the conversation zone."""

    DEFAULT_CSS = """
    _AssistantBubble {
        color: $text;
        background: $surface;
        padding: 0 1;
        margin: 0 4 0 0;
        height: auto;
        max-height: 3;
    }
    """


class _UpdateSummary(Static):
    """Brief summary of which sections were modified."""

    DEFAULT_CSS = """
    _UpdateSummary {
        color: $success;
        padding: 0 1;
        height: auto;
        text-style: italic;
    }
    """


# ---------------------------------------------------------------------------
# ConversationZone
# ---------------------------------------------------------------------------

class ConversationZone(Container):
    """Ephemeral dialogue surface showing the last exchange.

    Mount this between the prompt display and the input area.
    After showing an exchange it auto-fades (removes itself from
    view) after a configurable timeout.
    """

    DEFAULT_CSS = """
    ConversationZone {
        display: none;
        max-height: 6;
        margin: 0 2;
        padding: 0 1;
        border: round $primary-muted;
    }
    ConversationZone.visible {
        display: block;
    }
    """

    AUTO_DISMISS_SECONDS: float = 5.0

    _dismiss_timer: Optional[Timer] = None
    _assistant_bubble: Optional[_AssistantBubble] = None
    _streaming: bool = False

    # -- public API ---------------------------------------------------------

    def show_exchange(self, user_msg: str, assistant_msg: str) -> None:
        """Show the latest user/assistant exchange. Auto-fades after timeout."""
        self._cancel_dismiss()
        self._streaming = False
        self.remove_children()

        # Truncate long messages for the compact zone.
        user_display = _truncate(user_msg, max_lines=1, max_chars=80)
        assistant_display = _truncate(assistant_msg, max_lines=2, max_chars=160)

        user_bubble = _UserBubble(user_display)
        self._assistant_bubble = _AssistantBubble(assistant_display)
        self.mount(user_bubble)
        self.mount(self._assistant_bubble)
        self.add_class("visible")

        self._schedule_dismiss()

    def stream_token(self, token: str) -> None:
        """Append a streaming token to the assistant response area.

        If no assistant bubble exists yet (first token), create one.
        Calling this resets the auto-dismiss timer so the zone stays
        visible during active streaming.
        """
        self._cancel_dismiss()
        self._streaming = True

        if self._assistant_bubble is None:
            self._assistant_bubble = _AssistantBubble("")
            self.mount(self._assistant_bubble)
            self.add_class("visible")

        # Append the token to the existing content.
        current = str(self._assistant_bubble.renderable)
        updated = current + token
        # Keep the bubble compact — trim to last ~160 chars when streaming.
        if len(updated) > 200:
            updated = "..." + updated[-160:]
        self._assistant_bubble.update(updated)

    def finish_streaming(self) -> None:
        """Mark the end of a streaming response and start auto-dismiss."""
        self._streaming = False
        self._schedule_dismiss()

    def show_update_summary(self, updated_sections: list[str]) -> None:
        """Show which sections were updated by the AI.

        This is appended below the existing exchange content and
        resets the dismiss timer.
        """
        if not updated_sections:
            return
        self._cancel_dismiss()

        names = ", ".join(updated_sections)
        summary = _UpdateSummary(f"Updated: {names}")
        self.mount(summary)
        self.add_class("visible")

        self._schedule_dismiss()

    def auto_dismiss(self) -> None:
        """Fade out / hide the conversation zone."""
        if self._streaming:
            # Don't dismiss while still streaming — reschedule.
            self._schedule_dismiss()
            return
        self._dismiss_timer = None
        self.remove_class("visible")

    # -- internals ----------------------------------------------------------

    def _schedule_dismiss(self) -> None:
        """Schedule an auto-dismiss after the configured timeout."""
        self._cancel_dismiss()
        self._dismiss_timer = self.set_timer(
            self.AUTO_DISMISS_SECONDS,
            self.auto_dismiss,
        )

    def _cancel_dismiss(self) -> None:
        """Cancel any pending dismiss timer."""
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_lines: int = 2, max_chars: int = 120) -> str:
    """Truncate *text* to fit in the compact conversation zone."""
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1] + "..."
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[: max_chars - 3] + "..."
    return result
