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
    """Prompt Master TUI — The Canvas."""

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
        self._conversation_history: list[dict] = []

    # ── Layout ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Canvas(id="canvas")

    def on_mount(self) -> None:
        if self._resume:
            self._load_session()
        elif self._idea:
            self._generate_initial()
        else:
            self._show_scaffold()

    @property
    def canvas(self) -> Canvas:
        return self.query_one("#canvas", Canvas)

    # ── Initial population ─────────────────────────────────────────────

    def _show_scaffold(self) -> None:
        self.canvas.populate_sections(SCAFFOLD_SECTIONS)

    def _generate_initial(self) -> None:
        from prompt_master.session import generate_session_id

        self._session_id = generate_session_id()
        self.canvas.status_line.update_session(self._session_id)
        self.canvas.show_loading("generating initial prompt...")

        self.run_worker(self._run_optimization, name="optimize", thread=True)

    def _run_optimization(self) -> None:
        from prompt_master.optimizer import optimize_prompt
        from prompt_master.vibe import _parse_sections

        result = optimize_prompt(
            idea=self._idea,
            target=self._target,
            use_api=not self._no_api,
            model=self._model,
        )
        sections = _parse_sections(result.optimized_prompt)
        self.call_from_thread(self._apply_optimization, sections, result)

    def _apply_optimization(self, sections: dict, result) -> None:
        self.canvas.hide_loading()
        self.canvas.populate_sections(sections)

        status = self.canvas.status_line
        status.update_session(self._session_id)
        token_est = len(result.optimized_prompt) // 4
        status.update_tokens(token_est, 50_000)

        usage_summary = result.metadata.get("usage_summary", "")
        if usage_summary:
            for part in usage_summary.split("|"):
                part = part.strip()
                if part.startswith("Cost:"):
                    status.update_cost(part.replace("Cost:", "").strip())
                    break

    # ── Floor input: conversation ──────────────────────────────────────

    def on_canvas_user_submitted(self, message: Canvas.UserSubmitted) -> None:
        """User typed something in the floor input — send to AI for refinement."""
        user_text = message.text

        if self._no_api:
            self.notify("Offline mode — edit sections directly above", timeout=3)
            return

        # Build the refinement prompt from current sections + user message
        current_prompt = self.canvas.get_prompt_text()

        self._conversation_history.append({"role": "user", "content": user_text})
        self.canvas.show_loading("refining with AI...")

        self.run_worker(
            lambda: self._run_refinement(current_prompt, user_text),
            name="refine",
            thread=True,
        )

    def _run_refinement(self, current_prompt: str, user_message: str) -> None:
        """Worker thread: send current prompt + user request to AI.

        Uses haiku by default for fast interactive refinement, unless the
        user explicitly chose a different model.
        """
        from prompt_master.client import ClaudeClient, NoAPIKeyError
        from prompt_master.vibe import _parse_sections

        system = (
            "You are a prompt refinement assistant. The user has a prompt they want to improve. "
            "They will tell you what to change. Apply their feedback and return the COMPLETE "
            "updated prompt with ALL sections (# Role, # Task, etc.). "
            "Output ONLY the updated prompt in markdown format — no commentary, no explanation."
        )

        user_content = (
            f"Here is the current prompt:\n\n{current_prompt}\n\n"
            f"---\n\nUser request: {user_message}\n\n"
            f"Apply this change and return the complete updated prompt."
        )

        # Use haiku for refinement (fast) unless user specified otherwise
        refine_model = self._model if self._model else "haiku"

        try:
            client = ClaudeClient(model=refine_model)
            response = client.generate(system, user_content)

            sections = _parse_sections(response)
            # Filter out empty preamble
            sections = {k: v for k, v in sections.items() if k != "_preamble" or v.strip()}

            self._conversation_history.append({"role": "assistant", "content": response})

            self.call_from_thread(
                self._apply_refinement, sections, user_message, client
            )

        except (NoAPIKeyError, Exception) as e:
            self.call_from_thread(self._refinement_error, str(e))

    def _apply_refinement(self, sections: dict, user_msg: str, client) -> None:
        """Apply AI refinement to the canvas."""
        self.canvas.hide_loading()

        # Update each section with highlights
        for name, content in sections.items():
            if name == "_preamble":
                continue
            self.canvas.update_section(name, content)

        # Show the exchange
        updated = [n for n in sections if n != "_preamble"]
        summary = f"Updated: {', '.join(updated)}" if updated else "No changes"
        self.canvas.show_exchange(user_msg, summary)

        # Update usage stats
        status = self.canvas.status_line
        usage = client.usage.summary()
        for part in usage.split("|"):
            part = part.strip()
            if part.startswith("Cost:"):
                status.update_cost(part.replace("Cost:", "").strip())

        token_est = len(self.canvas.get_prompt_text()) // 4
        status.update_tokens(token_est, 50_000)

    def _refinement_error(self, error_msg: str) -> None:
        self.canvas.hide_loading()
        self.notify(f"Error: {error_msg}", severity="error", timeout=5)

    # ── Session management ────────────────────────────────────────────

    def _load_session(self) -> None:
        from prompt_master.session import load_session
        from prompt_master.vibe import _parse_sections

        try:
            session_id, engine = load_session(self._resume)
            self._session_id = session_id

            if engine.current_draft:
                sections = _parse_sections(engine.current_draft)
            elif engine.final_prompt:
                sections = _parse_sections(engine.final_prompt)
            else:
                sections = SCAFFOLD_SECTIONS

            self.canvas.populate_sections(sections)
            status = self.canvas.status_line
            status.update_session(self._session_id)

        except FileNotFoundError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            self._show_scaffold()

    # ── Actions ───────────────────────────────────────────────────────

    def action_save(self) -> None:
        prompt_text = self.canvas.get_prompt_text()
        if self._output:
            path = Path(self._output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(prompt_text)
            self.notify(f"Saved to {path}", timeout=3)
        else:
            self.notify("No output file specified (use --output)", timeout=3)

    def action_help(self) -> None:
        self.notify(
            "Ctrl+S save | Ctrl+Q quit | Edit sections above | "
            "Type below to refine with AI | ? help",
            timeout=5,
        )
