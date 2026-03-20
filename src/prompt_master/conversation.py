"""Multi-turn conversation engine with stream marker filtering."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Generator, List, Optional

from prompt_master.prompts import build_system_prompt


# ── Marker definitions ──────────────────────────────────────────────────────

PROMPT_START = "===PROMPT_START==="
PROMPT_END = "===PROMPT_END==="
FINAL_PROMPT = "===FINAL_PROMPT==="

_ALL_MARKERS = (PROMPT_START, PROMPT_END, FINAL_PROMPT)

# Longest marker length (for buffer sizing)
_MAX_MARKER_LEN = max(len(m) for m in _ALL_MARKERS)


# ── Conversation phases ─────────────────────────────────────────────────────

class Phase(enum.Enum):
    """Conversation phase tracking."""
    EXPLORING = "exploring"      # Free-form back-and-forth
    DRAFTING = "drafting"        # A draft has been proposed
    REFINING = "refining"        # User is refining a draft
    FINALIZED = "finalized"      # Final prompt extracted


# ── Stream filter state machine ─────────────────────────────────────────────

class FilterState(enum.Enum):
    """States for the streaming marker filter."""
    PASSTHROUGH = "passthrough"  # Normal text — emit immediately
    BUFFERING = "buffering"      # Potential marker — accumulate
    IN_DRAFT = "in_draft"        # Inside PROMPT_START..PROMPT_END
    IN_FINAL = "in_final"        # Inside FINAL_PROMPT..FINAL_PROMPT


@dataclass
class StreamFilter:
    """Filters marker tokens from a character-by-character stream.

    Accumulates characters that could be the start of a marker. Once a full
    marker is recognized it is consumed (not emitted). If the buffer doesn't
    match any marker prefix, the buffered text is flushed as regular output.

    Draft content between PROMPT_START / PROMPT_END is captured and also
    emitted for display. Final prompt content is captured but NOT emitted
    (displayed separately by the caller).
    """

    state: FilterState = FilterState.PASSTHROUGH
    buffer: str = ""
    draft_content: str = ""
    final_content: str = ""

    # Callback receives filtered display text
    on_text: Optional[Callable[[str], None]] = None

    def _emit(self, text: str):
        if self.on_text and text:
            self.on_text(text)

    def feed(self, token: str):
        """Feed a chunk of streamed text through the filter."""
        for ch in token:
            self._feed_char(ch)

    def _feed_char(self, ch: str):
        if self.state == FilterState.PASSTHROUGH:
            self._handle_passthrough(ch)
        elif self.state == FilterState.BUFFERING:
            self._handle_buffering(ch)
        elif self.state == FilterState.IN_DRAFT:
            self._handle_in_draft(ch)
        elif self.state == FilterState.IN_FINAL:
            self._handle_in_final(ch)

    def _handle_passthrough(self, ch: str):
        if ch == "=":
            self.buffer = ch
            self.state = FilterState.BUFFERING
        else:
            self._emit(ch)

    def _handle_buffering(self, ch: str):
        self.buffer += ch

        # Check if buffer matches any complete marker
        for marker in _ALL_MARKERS:
            if self.buffer == marker:
                self._resolve_marker(marker)
                return

        # Check if buffer is still a valid prefix of any marker
        is_prefix = any(m.startswith(self.buffer) for m in _ALL_MARKERS)
        if not is_prefix:
            # Not a marker — flush buffer as regular text
            text = self.buffer
            self.buffer = ""
            self.state = FilterState.PASSTHROUGH
            self._emit(text)

    def _resolve_marker(self, marker: str):
        self.buffer = ""
        if marker == PROMPT_START:
            self.state = FilterState.IN_DRAFT
            self.draft_content = ""
        elif marker == PROMPT_END:
            self.state = FilterState.PASSTHROUGH
            # Strip leading/trailing whitespace from draft
            self.draft_content = self.draft_content.strip()
        elif marker == FINAL_PROMPT:
            if self.state == FilterState.BUFFERING:
                # Opening FINAL_PROMPT marker
                self.state = FilterState.IN_FINAL
                self.final_content = ""

    def _handle_in_draft(self, ch: str):
        if self.buffer or ch == "=":
            self.buffer += ch
            # Check for complete end marker
            if self.buffer == PROMPT_END:
                self.buffer = ""
                self.draft_content = self.draft_content.strip()
                self.state = FilterState.PASSTHROUGH
                return
            # Still a valid prefix of the end marker — keep buffering
            if PROMPT_END.startswith(self.buffer):
                return
            # Not a marker — flush buffer as draft content
            content = self.buffer
            self.buffer = ""
            self.draft_content += content
            self._emit(content)
        else:
            self.draft_content += ch
            self._emit(ch)

    def _handle_in_final(self, ch: str):
        if self.buffer or ch == "=":
            self.buffer += ch
            if self.buffer == FINAL_PROMPT:
                self.buffer = ""
                self.final_content = self.final_content.strip()
                self.state = FilterState.PASSTHROUGH
                return
            if FINAL_PROMPT.startswith(self.buffer):
                return
            content = self.buffer
            self.buffer = ""
            self.final_content += content
            # Don't emit final content — shown separately
        else:
            self.final_content += ch
            # Don't emit final content

    def flush(self):
        """Flush any remaining buffer at end of stream."""
        if self.buffer:
            if self.state == FilterState.IN_DRAFT:
                self.draft_content += self.buffer
                self._emit(self.buffer)
            elif self.state == FilterState.IN_FINAL:
                self.final_content += self.buffer
            else:
                self._emit(self.buffer)
            self.buffer = ""


# ── Conversation engine ─────────────────────────────────────────────────────

@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class ConversationEngine:
    """Manages multi-turn conversation state."""

    target: str = "general"
    phase: Phase = Phase.EXPLORING
    messages: List[Message] = field(default_factory=list)
    current_draft: str = ""
    final_prompt: str = ""

    def get_system_prompt(self) -> str:
        return build_system_prompt(self.target)

    def add_user_message(self, text: str):
        self.messages.append(Message(role="user", content=text))

    def add_assistant_message(self, text: str):
        self.messages.append(Message(role="assistant", content=text))

    def get_api_messages(self) -> list:
        """Format messages for the Anthropic API."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def process_assistant_response(self, raw_text: str) -> str:
        """Process a complete assistant response: extract markers, update state.

        Returns the display text (markers stripped).
        """
        sf = StreamFilter()
        display_parts: list[str] = []
        sf.on_text = lambda t: display_parts.append(t)

        sf.feed(raw_text)
        sf.flush()

        # Update state based on extracted content
        if sf.final_content:
            self.final_prompt = sf.final_content
            self.current_draft = sf.final_content
            self.phase = Phase.FINALIZED
        elif sf.draft_content:
            self.current_draft = sf.draft_content
            if self.phase == Phase.EXPLORING:
                self.phase = Phase.DRAFTING
            else:
                self.phase = Phase.REFINING

        display_text = "".join(display_parts)
        self.add_assistant_message(raw_text)
        return display_text

    def create_stream_filter(self) -> StreamFilter:
        """Create a StreamFilter for processing streaming responses.

        After streaming completes, caller should call
        update_from_filter(filter) to sync state.
        """
        return StreamFilter()

    def update_from_filter(self, sf: StreamFilter, raw_text: str):
        """Update conversation state from a completed stream filter."""
        sf.flush()
        if sf.final_content:
            self.final_prompt = sf.final_content
            self.current_draft = sf.final_content
            self.phase = Phase.FINALIZED
        elif sf.draft_content:
            self.current_draft = sf.draft_content
            if self.phase == Phase.EXPLORING:
                self.phase = Phase.DRAFTING
            else:
                self.phase = Phase.REFINING

        self.add_assistant_message(raw_text)

    def request_finalization(self):
        """Add a user message requesting finalization."""
        self.add_user_message(
            "I'm done. Please output the final version of the prompt."
        )

    def to_dict(self) -> dict:
        """Serialize for session persistence."""
        return {
            "target": self.target,
            "phase": self.phase.value,
            "messages": [{"role": m.role, "content": m.content} for m in self.messages],
            "current_draft": self.current_draft,
            "final_prompt": self.final_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationEngine":
        """Deserialize from session data."""
        engine = cls(
            target=data["target"],
            phase=Phase(data["phase"]),
            current_draft=data.get("current_draft", ""),
            final_prompt=data.get("final_prompt", ""),
        )
        engine.messages = [
            Message(role=m["role"], content=m["content"])
            for m in data.get("messages", [])
        ]
        return engine
