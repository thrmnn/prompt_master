"""CanvasApp — root Textual application for Prompt Master."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding

from prompt_master.tui.canvas import Canvas


# Scaffold sections shown when no idea is provided.
SCAFFOLD_SECTIONS: Dict[str, str] = {
    "Role": "[describe who the AI should be...]",
    "Task": "[what should it do?]",
    "Context": "[relevant background, constraints, audience...]",
    "Output Format": "[how should the response be structured?]",
    "Requirements": "[any hard rules or boundaries?]",
}


class CanvasApp(App):
    """Prompt Master TUI — The Canvas.

    Accepts an optional ``idea`` to generate an optimized prompt on launch,
    or starts with scaffold sections for manual editing.
    """

    TITLE = "Prompt Master"
    CSS_PATH = Path(__file__).parent / "css" / "canvas.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("question_mark", "help", "Help", show=False),
    ]

    def __init__(
        self,
        idea: Optional[str] = None,
        target: Optional[str] = None,
        resume: Optional[str] = None,
        output: Optional[str] = None,
        model: Optional[str] = None,
        no_api: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._idea = idea
        self._target = target or "general"
        self._resume = resume
        self._output = output
        self._model = model
        self._no_api = no_api
        self._session_id: str = ""

    # ── Layout ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """The Canvas screen is composed directly as the app's root content."""
        yield Canvas(id="canvas")

    def on_mount(self) -> None:
        """Populate initial content once the widget tree is ready."""
        if self._resume:
            self._load_session()
        elif self._idea:
            self._generate_initial()
        else:
            self._show_scaffold()

    # ── Canvas accessor ───────────────────────────────────────────────

    @property
    def canvas(self) -> Canvas:
        return self.query_one("#canvas", Canvas)

    # ── Initial population strategies ─────────────────────────────────

    def _show_scaffold(self) -> None:
        """Show empty scaffold sections for manual editing."""
        self.canvas.populate_sections(SCAFFOLD_SECTIONS)

    def _generate_initial(self) -> None:
        """Run optimize_prompt in a worker thread, then populate the canvas."""
        from prompt_master.session import generate_session_id

        self._session_id = generate_session_id()

        # Update status line with session info
        status = self.canvas.status_line
        status.update_session(self._session_id)
        status.update(f"session: {self._session_id[:8]} | generating...")

        self.run_worker(
            self._run_optimization,
            name="optimize",
            thread=True,
        )

    def _run_optimization(self) -> None:
        """Worker thread: call optimize_prompt and populate the canvas."""
        from prompt_master.optimizer import optimize_prompt
        from prompt_master.vibe import _parse_sections

        result = optimize_prompt(
            idea=self._idea,
            target=self._target,
            use_api=not self._no_api,
            model=self._model,
        )

        sections = _parse_sections(result.optimized_prompt)

        # Schedule UI update on the main thread
        self.call_from_thread(self._apply_optimization, sections, result)

    def _apply_optimization(self, sections: dict, result) -> None:
        """Apply optimization results to the canvas (runs on main thread)."""
        self.canvas.populate_sections(sections)

        # Update status
        status = self.canvas.status_line
        status.update_session(self._session_id)

        # Token estimate
        token_est = len(result.optimized_prompt) // 4
        status.update_tokens(token_est, 50_000)

        # Cost from metadata
        usage_summary = result.metadata.get("usage_summary", "")
        if usage_summary:
            # Extract cost from "Tokens: X in / Y out | Cost: $0.0123 | Calls: 1"
            for part in usage_summary.split("|"):
                part = part.strip()
                if part.startswith("Cost:"):
                    status.update_cost(part.replace("Cost:", "").strip())
                    break

    def _load_session(self) -> None:
        """Resume from a saved session."""
        from prompt_master.session import load_session
        from prompt_master.vibe import _parse_sections

        try:
            session_id, engine = load_session(self._resume)
            self._session_id = session_id

            # If the engine has a current draft, parse it into sections
            if engine.current_draft:
                sections = _parse_sections(engine.current_draft)
            elif engine.final_prompt:
                sections = _parse_sections(engine.final_prompt)
            else:
                sections = SCAFFOLD_SECTIONS

            self.canvas.populate_sections(sections)

            status = self.canvas.status_line
            status.update_session(self._session_id)
            token_est = len(engine.current_draft or engine.final_prompt or "") // 4
            if token_est > 0:
                status.update_tokens(token_est, 50_000)

        except FileNotFoundError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            self._show_scaffold()

    # ── Actions ───────────────────────────────────────────────────────

    def action_save(self) -> None:
        """Save the current prompt to the output file or session."""
        prompt_text = self.canvas.get_prompt_text()

        if self._output:
            from pathlib import Path

            path = Path(self._output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prompt_text)
            self.notify(f"Saved to {path}", timeout=3)
        else:
            self.notify("No output file specified (use --output)", timeout=3)

    def action_help(self) -> None:
        """Show a help overlay."""
        self.notify(
            "Ctrl+S save | Ctrl+Q quit | Edit sections above | "
            "Type in the bar below to refine",
            timeout=5,
        )
