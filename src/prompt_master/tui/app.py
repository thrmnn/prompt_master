"""CanvasApp — root Textual application for Prompt Master."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding

from prompt_master.tui.canvas import Canvas


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

    # ── Initial generation (streaming) ─────────────────────────────────

    def _show_scaffold(self) -> None:
        self.canvas.populate_sections(SCAFFOLD_SECTIONS)

    def _generate_initial(self) -> None:
        from prompt_master.session import generate_session_id
        self._session_id = generate_session_id()
        self.canvas.status_line.update_session(self._session_id)
        self.canvas.show_loading("generating prompt...")
        self.run_worker(self._stream_initial, name="generate", thread=True)

    def _stream_initial(self) -> None:
        """Stream the initial prompt generation token by token."""
        from prompt_master.client import ClaudeClient, NoAPIKeyError
        from prompt_master.optimizer import META_SYSTEM_PROMPT, TARGET_INSTRUCTIONS

        try:
            client = ClaudeClient(model=self._model or "sonnet")
        except NoAPIKeyError:
            # Fall back to template
            from prompt_master.optimizer import optimize_prompt
            from prompt_master.vibe import _parse_sections
            result = optimize_prompt(self._idea, self._target, use_api=False)
            sections = _parse_sections(result.optimized_prompt)
            self.call_from_thread(self._finish_generation, sections, client=None)
            return

        target_inst = TARGET_INSTRUCTIONS.get(self._target, TARGET_INSTRUCTIONS["general"])
        user_msg = f"**Idea:** {self._idea}\n\n**Target:** {target_inst}"

        accumulated = ""
        try:
            for chunk in client.generate_stream(META_SYSTEM_PROMPT, user_msg):
                accumulated += chunk
                self.call_from_thread(self._stream_update, accumulated)
        except Exception as e:
            self.call_from_thread(self._generation_error, str(e))
            return

        from prompt_master.vibe import _parse_sections
        sections = _parse_sections(accumulated)
        self.call_from_thread(self._finish_generation, sections, client)

    def _stream_update(self, text_so_far: str) -> None:
        """Called on main thread during streaming — progressively update sections."""
        from prompt_master.vibe import _parse_sections
        sections = _parse_sections(text_so_far)
        # Only update sections that have content
        for name, content in sections.items():
            if name == "_preamble" or not content.strip():
                continue
            self.canvas.update_section(name, content, highlight=False)

    def _finish_generation(self, sections: dict, client) -> None:
        """Generation complete — final update and stats."""
        self.canvas.hide_loading()
        for name, content in sections.items():
            if name == "_preamble":
                continue
            self.canvas.update_section(name, content, highlight=False)

        status = self.canvas.status_line
        status.update_session(self._session_id)
        prompt_text = self.canvas.get_prompt_text()
        status.update_tokens(len(prompt_text) // 4, 50_000)

        if client:
            for part in client.usage.summary().split("|"):
                part = part.strip()
                if part.startswith("Cost:"):
                    status.update_cost(part.replace("Cost:", "").strip())

        # Score sections
        self._run_scoring()

    def _generation_error(self, error_msg: str) -> None:
        self.canvas.hide_loading()
        self.notify(f"Error: {error_msg}", severity="error", timeout=5)
        self._show_scaffold()

    # ── Floor input: streaming refinement ──────────────────────────────

    def on_canvas_user_submitted(self, message: Canvas.UserSubmitted) -> None:
        user_text = message.text
        if self._no_api:
            self.notify("Offline mode — edit sections directly above", timeout=3)
            return
        self.canvas.show_loading("refining...")
        self.run_worker(
            lambda: self._stream_refinement(user_text),
            name="refine",
            thread=True,
        )

    def _stream_refinement(self, user_message: str) -> None:
        """Stream refinement response — sections update as tokens arrive."""
        from prompt_master.client import ClaudeClient, NoAPIKeyError
        from prompt_master.vibe import _parse_sections

        current_prompt = self.call_from_thread(self.canvas.get_prompt_text)

        system = (
            "You are a prompt refinement assistant. Apply the user's feedback to "
            "the prompt and return the COMPLETE updated prompt with ALL sections "
            "(# Role, # Task, etc.). Output ONLY the prompt — no commentary."
        )
        user_content = (
            f"Current prompt:\n\n{current_prompt}\n\n---\n\n"
            f"User request: {user_message}\n\n"
            f"Return the complete updated prompt."
        )

        refine_model = self._model if self._model else "haiku"

        try:
            client = ClaudeClient(model=refine_model)
            accumulated = ""
            for chunk in client.generate_stream(system, user_content):
                accumulated += chunk
                self.call_from_thread(self._stream_update, accumulated)

            sections = _parse_sections(accumulated)
            self.call_from_thread(
                self._finish_refinement, sections, user_message, client
            )
        except (NoAPIKeyError, Exception) as e:
            self.call_from_thread(self._refinement_error, str(e))

    def _finish_refinement(self, sections: dict, user_msg: str, client) -> None:
        self.canvas.hide_loading()

        updated = []
        for name, content in sections.items():
            if name == "_preamble":
                continue
            self.canvas.update_section(name, content, highlight=True)
            updated.append(name)

        summary = f"Updated: {', '.join(updated)}" if updated else "No changes"
        self.canvas.show_exchange(user_msg, summary)

        status = self.canvas.status_line
        status.update_tokens(len(self.canvas.get_prompt_text()) // 4, 50_000)
        for part in client.usage.summary().split("|"):
            part = part.strip()
            if part.startswith("Cost:"):
                status.update_cost(part.replace("Cost:", "").strip())

        self._run_scoring()

    def _refinement_error(self, error_msg: str) -> None:
        self.canvas.hide_loading()
        self.notify(f"Error: {error_msg}", severity="error", timeout=5)

    # ── Cursor-based intelligence ──────────────────────────────────────

    def on_section_block_section_focused(self, message) -> None:
        """Section got focus — run scoring and show whisper if weak."""
        self._run_scoring()
        section_name = message.section_name
        # Check if this section is weak and show a whisper
        from prompt_master.tui.realtime_scorer import score_sections
        from prompt_master.vibe import _parse_sections

        prompt_text = self.canvas.get_prompt_text()
        sections = _parse_sections(prompt_text)
        scores = score_sections(sections, self._target)

        if section_name in scores:
            sc = scores[section_name]
            if sc.score < 7.0 and sc.feedback:
                self.notify(
                    f"[dim]{section_name}: {sc.score:.0f}/10 — {sc.feedback}[/dim]",
                    timeout=5,
                )

    def _run_scoring(self) -> None:
        """Score all sections and update the section block scores."""
        from prompt_master.tui.realtime_scorer import score_sections, compute_overall_score
        from prompt_master.vibe import _parse_sections

        prompt_text = self.canvas.get_prompt_text()
        sections = _parse_sections(prompt_text)
        scores = score_sections(sections, self._target)

        # Update each section block's score indicator
        from prompt_master.tui.section_block import SectionBlock
        for block in self.query(SectionBlock):
            if block.section_name in scores:
                block.score = scores[block.section_name].score

        overall = compute_overall_score(scores)
        self.canvas.status_line.update_score(overall)

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
            self.canvas.status_line.update_session(self._session_id)
            self._run_scoring()
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
