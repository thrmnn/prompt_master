"""Keybinding definitions for the TUI canvas."""

# Global bindings (always active)
GLOBAL_BINDINGS = [
    ("ctrl+q", "quit", "Quit"),
    ("ctrl+s", "save", "Save prompt"),
    ("question_mark", "help", "Show help"),
    ("ctrl+h", "history", "Conversation history"),
]

# Section editing bindings
SECTION_BINDINGS = [
    ("tab", "explore", "Explore variations"),
    ("ctrl+r", "recommend", "Get recommendation"),
    ("ctrl+d", "decompose", "Decompose into workflow"),
    ("ctrl+z", "undo", "Undo last change"),
]

# Variation drawer bindings
DRAWER_BINDINGS = [
    ("escape", "close", "Close"),
    ("1-9", "select", "Pick variation"),
]

# Conversation bindings
CONVERSATION_BINDINGS = [
    ("enter", "send", "Send message"),
    ("escape", "cancel", "Clear input"),
]

def get_help_text() -> str:
    """Return formatted help text for all bindings."""
    lines = []
    for label, bindings in [
        ("Global", GLOBAL_BINDINGS),
        ("Editing", SECTION_BINDINGS),
        ("Variations", DRAWER_BINDINGS),
        ("Conversation", CONVERSATION_BINDINGS),
    ]:
        lines.append(f"  {label}")
        for key, _, desc in bindings:
            lines.append(f"    {key:<16} {desc}")
        lines.append("")
    return "\n".join(lines)
