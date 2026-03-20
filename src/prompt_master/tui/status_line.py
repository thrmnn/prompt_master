"""Status line widget — fixed at the bottom of the canvas."""

from __future__ import annotations

from textual.widgets import Static


class StatusLine(Static):
    """Persistent status bar showing score, tokens, session, and cost."""

    DEFAULT_CSS = """
    StatusLine {
        dock: bottom;
        width: 1fr;
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        text-style: dim;
        padding: 0 2;
        content-align: left middle;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._score_pct: float = 0.0
        self._tokens_used: int = 0
        self._tokens_budget: int = 0
        self._session_id: str = ""
        self._cost: str = ""

    # ── Public API ────────────────────────────────────────────────────

    def update_score(self, pct: float) -> None:
        """Update the overall prompt score (0-100)."""
        self._score_pct = pct
        self._refresh_display()

    def update_tokens(self, used: int, budget: int) -> None:
        """Update the token usage display."""
        self._tokens_used = used
        self._tokens_budget = budget
        self._refresh_display()

    def update_session(self, session_id: str) -> None:
        """Update the session ID display (shows first 8 chars)."""
        self._session_id = session_id[:8] if session_id else ""
        self._refresh_display()

    def update_cost(self, cost_str: str) -> None:
        """Update the cost estimate display."""
        self._cost = cost_str
        self._refresh_display()

    # ── Internal ──────────────────────────────────────────────────────

    def _format_tokens(self, count: int) -> str:
        """Format a token count as human-readable (e.g. 1.2k)."""
        if count >= 1000:
            return f"{count / 1000:.1f}k"
        return str(count)

    def _refresh_display(self) -> None:
        """Recompose the status line text."""
        parts: list[str] = []

        if self._score_pct > 0:
            parts.append(f"score {self._score_pct:.0f}%")

        if self._tokens_budget > 0:
            used_str = self._format_tokens(self._tokens_used)
            budget_str = self._format_tokens(self._tokens_budget)
            parts.append(f"tokens: {used_str} / {budget_str}")
        elif self._tokens_used > 0:
            parts.append(f"tokens: {self._format_tokens(self._tokens_used)}")

        if self._session_id:
            parts.append(f"session: {self._session_id}")

        if self._cost:
            parts.append(f"cost: {self._cost}")

        self.update(" │ ".join(parts) if parts else "ready")
