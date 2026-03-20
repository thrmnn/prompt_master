"""Tests for conversation engine: phase transitions, marker extraction, stream filtering."""

from prompt_master.conversation import (
    FINAL_PROMPT,
    PROMPT_END,
    PROMPT_START,
    ConversationEngine,
    Phase,
    StreamFilter,
)


# ── StreamFilter tests ──────────────────────────────────────────────────────


class TestStreamFilter:
    """Tests for the streaming marker filter state machine."""

    def test_passthrough_plain_text(self):
        """Plain text with no markers passes through unchanged."""
        sf = StreamFilter()
        output = []
        sf.on_text = output.append

        sf.feed("Hello, this is plain text.")
        sf.flush()

        assert "".join(output) == "Hello, this is plain text."

    def test_filters_prompt_start_end_markers(self):
        """PROMPT_START and PROMPT_END markers are stripped from output."""
        sf = StreamFilter()
        output = []
        sf.on_text = output.append

        sf.feed(
            f"Here is a draft:\n{PROMPT_START}\nDo the thing.\n{PROMPT_END}\nWhat do you think?"
        )
        sf.flush()

        result = "".join(output)
        assert PROMPT_START not in result
        assert PROMPT_END not in result
        assert "Here is a draft:" in result
        assert "Do the thing." in result
        assert "What do you think?" in result

    def test_captures_draft_content(self):
        """Content between PROMPT_START and PROMPT_END is captured."""
        sf = StreamFilter()
        sf.on_text = lambda t: None  # discard output

        sf.feed(f"Intro\n{PROMPT_START}\nMy draft content here.\n{PROMPT_END}\nOutro")
        sf.flush()

        assert sf.draft_content == "My draft content here."

    def test_captures_final_content(self):
        """Content between FINAL_PROMPT markers is captured."""
        sf = StreamFilter()
        output = []
        sf.on_text = output.append

        sf.feed(f"Here is the final:\n{FINAL_PROMPT}\nFinal prompt text.\n{FINAL_PROMPT}\nDone!")
        sf.flush()

        assert sf.final_content == "Final prompt text."
        # Final content should NOT appear in output
        result = "".join(output)
        assert "Final prompt text." not in result
        assert "Done!" in result

    def test_character_by_character_streaming(self):
        """Markers are detected even when fed character by character."""
        sf = StreamFilter()
        output = []
        sf.on_text = output.append

        text = f"A{PROMPT_START}draft{PROMPT_END}B"
        for ch in text:
            sf.feed(ch)
        sf.flush()

        assert sf.draft_content == "draft"
        result = "".join(output)
        assert "A" in result
        assert "B" in result
        assert "draft" in result
        assert "===" not in result

    def test_partial_equals_not_marker(self):
        """A run of '=' that doesn't form a marker is flushed as text."""
        sf = StreamFilter()
        output = []
        sf.on_text = output.append

        sf.feed("price == 10")
        sf.flush()

        assert "".join(output) == "price == 10"

    def test_empty_draft(self):
        """Empty content between markers produces empty draft."""
        sf = StreamFilter()
        sf.on_text = lambda t: None

        sf.feed(f"{PROMPT_START}{PROMPT_END}")
        sf.flush()

        assert sf.draft_content == ""

    def test_multiple_drafts_keeps_latest(self):
        """When multiple drafts appear, draft_content holds the latest."""
        sf = StreamFilter()
        sf.on_text = lambda t: None

        sf.feed(
            f"{PROMPT_START}First draft{PROMPT_END} some text {PROMPT_START}Second draft{PROMPT_END}"
        )
        sf.flush()

        assert sf.draft_content == "Second draft"

    def test_no_callback_does_not_crash(self):
        """StreamFilter works without an on_text callback."""
        sf = StreamFilter()
        sf.feed(f"text {PROMPT_START}draft{PROMPT_END} more")
        sf.flush()

        assert sf.draft_content == "draft"


# ── ConversationEngine tests ────────────────────────────────────────────────


class TestConversationEngine:
    """Tests for the conversation state machine."""

    def test_initial_state(self):
        engine = ConversationEngine(target="code")
        assert engine.phase == Phase.EXPLORING
        assert engine.target == "code"
        assert engine.messages == []
        assert engine.current_draft == ""

    def test_add_messages(self):
        engine = ConversationEngine()
        engine.add_user_message("Hello")
        engine.add_assistant_message("Hi there")

        assert len(engine.messages) == 2
        assert engine.messages[0].role == "user"
        assert engine.messages[1].role == "assistant"

    def test_get_api_messages(self):
        engine = ConversationEngine()
        engine.add_user_message("Hello")
        engine.add_assistant_message("Hi")

        api_msgs = engine.get_api_messages()
        assert api_msgs == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

    def test_process_response_with_draft_transitions_to_drafting(self):
        engine = ConversationEngine()
        engine.add_user_message("Build a REST API")

        raw = f"Here's a draft:\n{PROMPT_START}\nYou are an API expert.\n{PROMPT_END}\nHow's this?"
        engine.process_assistant_response(raw)

        assert engine.phase == Phase.DRAFTING
        assert engine.current_draft == "You are an API expert."

    def test_process_response_with_refinement(self):
        engine = ConversationEngine()
        engine.add_user_message("Build a REST API")
        engine.process_assistant_response(f"{PROMPT_START}First draft{PROMPT_END}")
        assert engine.phase == Phase.DRAFTING

        engine.add_user_message("Make it more specific")
        engine.process_assistant_response(f"{PROMPT_START}Refined draft{PROMPT_END}")
        assert engine.phase == Phase.REFINING
        assert engine.current_draft == "Refined draft"

    def test_process_response_with_final_prompt(self):
        engine = ConversationEngine()
        engine.add_user_message("I'm done")
        raw = f"{FINAL_PROMPT}\nFinal version here.\n{FINAL_PROMPT}"
        engine.process_assistant_response(raw)

        assert engine.phase == Phase.FINALIZED
        assert engine.final_prompt == "Final version here."

    def test_request_finalization(self):
        engine = ConversationEngine()
        engine.request_finalization()

        assert len(engine.messages) == 1
        assert engine.messages[0].role == "user"
        assert "done" in engine.messages[0].content.lower()

    def test_system_prompt_includes_target(self):
        engine = ConversationEngine(target="code")
        prompt = engine.get_system_prompt()
        assert "code" in prompt.lower()

    def test_serialization_roundtrip(self):
        engine = ConversationEngine(target="creative")
        engine.add_user_message("Write a poem")
        engine.add_assistant_message("Sure!")
        engine.current_draft = "Roses are red"
        engine.phase = Phase.DRAFTING

        data = engine.to_dict()
        restored = ConversationEngine.from_dict(data)

        assert restored.target == "creative"
        assert restored.phase == Phase.DRAFTING
        assert restored.current_draft == "Roses are red"
        assert len(restored.messages) == 2
        assert restored.messages[0].content == "Write a poem"

    def test_exploring_no_markers_stays_exploring(self):
        engine = ConversationEngine()
        engine.add_user_message("Hi")
        engine.process_assistant_response("What would you like to build?")

        assert engine.phase == Phase.EXPLORING
        assert engine.current_draft == ""

    def test_update_from_filter(self):
        engine = ConversationEngine()
        engine.add_user_message("Hello")

        sf = engine.create_stream_filter()
        raw = f"Draft:\n{PROMPT_START}\nStreamd draft\n{PROMPT_END}\nThoughts?"
        sf.feed(raw)
        engine.update_from_filter(sf, raw)

        assert engine.phase == Phase.DRAFTING
        assert engine.current_draft == "Streamd draft"
        assert len(engine.messages) == 2  # user + assistant
