"""Tests for keybinding definitions and help text generation."""

from prompt_master.tui.keybindings import (
    CONVERSATION_BINDINGS,
    DRAWER_BINDINGS,
    get_help_text,
    GLOBAL_BINDINGS,
    SECTION_BINDINGS,
)


# ---------------------------------------------------------------------------
# Global bindings present
# ---------------------------------------------------------------------------


class TestGlobalBindingsPresent:
    def test_is_nonempty_list(self):
        assert isinstance(GLOBAL_BINDINGS, list)
        assert len(GLOBAL_BINDINGS) > 0

    def test_elements_are_tuples(self):
        for binding in GLOBAL_BINDINGS:
            assert isinstance(binding, tuple)


# ---------------------------------------------------------------------------
# Help text contains all sections
# ---------------------------------------------------------------------------


class TestHelpTextContainsAllSections:
    def test_mentions_global(self):
        text = get_help_text()
        assert "Global" in text

    def test_mentions_editing(self):
        text = get_help_text()
        assert "Editing" in text

    def test_mentions_variations(self):
        text = get_help_text()
        assert "Variations" in text

    def test_mentions_conversation(self):
        text = get_help_text()
        assert "Conversation" in text

    def test_help_text_is_string(self):
        text = get_help_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_help_text_includes_keybindings(self):
        """Help text should contain actual key names from the binding lists."""
        text = get_help_text()
        # Check that at least one key from each binding group appears
        for bindings in [GLOBAL_BINDINGS, SECTION_BINDINGS, DRAWER_BINDINGS, CONVERSATION_BINDINGS]:
            if bindings:
                key = bindings[0][0]
                assert key in text


# ---------------------------------------------------------------------------
# Binding format
# ---------------------------------------------------------------------------


class TestBindingFormat:
    def test_global_binding_is_3_tuple(self):
        for binding in GLOBAL_BINDINGS:
            assert len(binding) == 3, f"Expected 3-tuple, got {len(binding)}-tuple: {binding}"

    def test_section_binding_is_3_tuple(self):
        for binding in SECTION_BINDINGS:
            assert len(binding) == 3

    def test_drawer_binding_is_3_tuple(self):
        for binding in DRAWER_BINDINGS:
            assert len(binding) == 3

    def test_conversation_binding_is_3_tuple(self):
        for binding in CONVERSATION_BINDINGS:
            assert len(binding) == 3

    def test_binding_fields_are_strings(self):
        """Each element in a binding tuple should be a string: (key, action, description)."""
        all_bindings = GLOBAL_BINDINGS + SECTION_BINDINGS + DRAWER_BINDINGS + CONVERSATION_BINDINGS
        for key, action, description in all_bindings:
            assert isinstance(key, str), f"Key should be str: {key}"
            assert isinstance(action, str), f"Action should be str: {action}"
            assert isinstance(description, str), f"Description should be str: {description}"

    def test_binding_fields_nonempty(self):
        all_bindings = GLOBAL_BINDINGS + SECTION_BINDINGS + DRAWER_BINDINGS + CONVERSATION_BINDINGS
        for key, action, description in all_bindings:
            assert len(key) > 0
            assert len(action) > 0
            assert len(description) > 0
