"""CanvasApp — root Textual application for Prompt Master.

Wires together: streaming generation, cursor-based intelligence (attention
tracker + dwell events + whispers + variation pre-loading), auto-copy to
clipboard, and inline variation exploration via Tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding

from prompt_master.tui.attention import AttentionTracker, DwellEvent, DeepDwellEvent
from prompt_master.tui.cache import LRUCache
from prompt_master.tui.canvas import Canvas
from prompt_master.tui.dimension_nav import DimensionNavigator
from prompt_master.tui.exploration_pad import ExplorationPad


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
        Binding("ctrl+c", "copy_prompt", "Copy", show=True),
        Binding("tab", "explore_section", "Explore", show=True, priority=True),
        Binding("space", "steer_section", "Steer", show=True, priority=True),
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
        self._attention = AttentionTracker()
        self._variation_cache = LRUCache(max_size=30)
        self._active_section: Optional[str] = None

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

        # Start the attention tick timer (200ms)
        self.set_interval(0.2, self._attention_tick)

    @property
    def canvas(self) -> Canvas:
        return self.query_one("#canvas", Canvas)

    # ── Attention system ──────────────────────────────────────────────

    def on_section_block_section_focused(self, message) -> None:
        """Section got focus — feed attention tracker, score, whisper."""
        section = message.section_name
        self._active_section = section

        # Feed the attention tracker
        events = self._attention.on_section_focus(section)
        for evt in events:
            self._handle_attention_event(evt)

        # Dismiss whisper if for a different section
        if self.canvas.whisper.current_section and self.canvas.whisper.current_section != section:
            self.canvas.dismiss_whisper()

        # Hide variation drawer if showing for different section
        drawer = self.canvas.drawer
        if drawer.has_class("visible") and drawer._section_name != section:
            self.canvas.hide_variations()

        # Score
        self._run_scoring()

    def _attention_tick(self) -> None:
        """Called every 200ms — check for dwell events."""
        events = self._attention.tick()
        for evt in events:
            self._handle_attention_event(evt)

    def _handle_attention_event(self, evt) -> None:
        """React to attention events."""
        if isinstance(evt, DeepDwellEvent):
            # Pre-generate variations in background
            self._preload_variations(evt.section)
        elif isinstance(evt, DwellEvent):
            # Show score whisper for weak sections
            self._show_section_whisper(evt.section)

    def _show_section_whisper(self, section: str) -> None:
        """Show a contextual whisper for a section based on its score."""
        from prompt_master.tui.realtime_scorer import score_sections, detect_decomposition
        from prompt_master.vibe import _parse_sections

        prompt_text = self.canvas.get_prompt_text()
        sections = _parse_sections(prompt_text)
        scores = score_sections(sections, self._target)

        if section in scores:
            sc = scores[section]
            if sc.score < 7.0 and sc.feedback:
                self.canvas.show_whisper(
                    f"{sc.score:.0f}/10 — {sc.feedback}",
                    section=section,
                    priority=1,
                    ttl=6.0,
                )
            elif sc.score >= 8.0:
                cached = self._variation_cache.get(
                    self._variation_cache.content_key(section, sections.get(section, ""))
                )
                if cached:
                    self.canvas.show_whisper(
                        f"{sc.score:.0f}/10 | Tab to explore {len(cached)} variations",
                        section=section,
                        priority=0,
                        ttl=4.0,
                    )

        # Check for workflow decomposition opportunity
        task = sections.get("Task", "")
        if task and section == "Task":
            decomp = detect_decomposition(task)
            if decomp:
                self.canvas.show_whisper(
                    decomp,
                    section="Task",
                    priority=2,
                    ttl=8.0,
                )

    # ── Variation exploration (Tab) ───────────────────────────────────

    def action_explore_section(self) -> None:
        """Tab pressed — explore variations for the focused section."""
        # Check if floor input has focus — if so, let Tab work normally
        try:
            floor = self.canvas.query_one("#floor-input")
            if floor.has_focus:
                return
        except Exception:
            pass

        section = self._active_section or self.canvas.get_focused_section()
        if not section:
            return

        # Check cache first
        from prompt_master.vibe import _parse_sections

        sections = _parse_sections(self.canvas.get_prompt_text())
        content = sections.get(section, "")
        cache_key = self._variation_cache.content_key(section, content)
        cached = self._variation_cache.get(cache_key)

        if cached:
            self.canvas.show_variations(section, cached)
        else:
            # Generate on the fly
            self.canvas.show_variations_loading(section)
            self.run_worker(
                lambda: self._generate_variations(section, content, cache_key),
                name="explore",
                thread=True,
            )

    def _preload_variations(self, section: str) -> None:
        """Pre-generate variations in background (triggered by deep dwell)."""
        from prompt_master.vibe import _parse_sections

        sections = _parse_sections(self.canvas.get_prompt_text())
        content = sections.get(section, "")
        cache_key = self._variation_cache.content_key(section, content)

        if self._variation_cache.get(cache_key):
            return  # Already cached

        self.run_worker(
            lambda: self._generate_variations(section, content, cache_key, show=False),
            name="preload",
            thread=True,
        )

    def _generate_variations(
        self, section: str, content: str, cache_key: str, show: bool = True
    ) -> None:
        """Worker thread: generate variations for a section."""
        from prompt_master.tui.section_vibe import generate_section_variations

        client = None
        if not self._no_api:
            try:
                from prompt_master.client import ClaudeClient

                client = ClaudeClient(model="haiku")
            except Exception:
                pass

        variations = generate_section_variations(
            section_name=section,
            section_content=content,
            target=self._target,
            count=4,
            client=client,
        )

        self._variation_cache.put(cache_key, variations)

        if show:
            self.call_from_thread(self.canvas.show_variations, section, variations)

    # ── Dimension steering (Space) ───────────────────────────────────

    def action_steer_section(self) -> None:
        """Space pressed — open the 2D exploration pad to steer the focused section."""
        # Don't hijack space when typing in the floor input or a TextArea
        try:
            floor = self.canvas.query_one("#floor-input")
            if floor.has_focus:
                return
        except Exception:
            pass

        from prompt_master.tui.section_block import SectionEditor

        for editor in self.query(SectionEditor):
            if editor.has_focus:
                return

        section = self._active_section or self.canvas.get_focused_section()
        if not section:
            return

        # Save original content for revert on Esc
        from prompt_master.vibe import _parse_sections

        sections = _parse_sections(self.canvas.get_prompt_text())
        self._steer_original = sections.get(section, "")
        self._steer_section = section

        # Open the exploration pad
        self.canvas.exploration_pad.open_for_section(section)

    def on_exploration_pad_morph_request(self, message: ExplorationPad.MorphRequest) -> None:
        """Mouse moved in the pad — morph the section along both axes in real-time."""
        from prompt_master.tui.section_vibe import _manual_section_variant

        section = message.section_name
        original = getattr(self, "_steer_original", "")
        if not original:
            return

        # Apply the X dimension first, then Y on top
        intermediate = _manual_section_variant(section, original, message.x_dim, message.x_val)
        final = _manual_section_variant(section, intermediate, message.y_dim, message.y_val)
        self.canvas.update_section(section, final, highlight=False)

    def on_exploration_pad_pad_closed(self, message: ExplorationPad.PadClosed) -> None:
        """Pad closed — score and copy."""
        self._run_scoring()
        self._auto_copy()

    def on_dimension_navigator_dimension_changed(
        self, message: DimensionNavigator.DimensionChanged
    ) -> None:
        """Discrete dimension navigator — also supported via the old path."""
        from prompt_master.tui.section_vibe import _manual_section_variant

        section = message.section_name
        original = getattr(self, "_steer_original", "")
        if not original:
            return
        new_content = _manual_section_variant(section, original, message.dimension, message.value)
        self.canvas.update_section(section, new_content, highlight=False)

    def on_dimension_navigator_navigator_closed(
        self, message: DimensionNavigator.NavigatorClosed
    ) -> None:
        self._run_scoring()
        self._auto_copy()

    # ── Clipboard ─────────────────────────────────────────────────────

    def action_copy_prompt(self) -> None:
        """Copy the full prompt to clipboard."""
        prompt = self.canvas.get_prompt_text()
        if not prompt.strip():
            self.notify("Nothing to copy", timeout=2)
            return
        self.copy_to_clipboard(prompt)
        self.notify("Prompt copied to clipboard", timeout=2)

    def _auto_copy(self) -> None:
        """Auto-copy after generation finishes."""
        prompt = self.canvas.get_prompt_text()
        if prompt.strip():
            self.copy_to_clipboard(prompt)

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
        from prompt_master.client import ClaudeClient
        from prompt_master.optimizer import META_SYSTEM_PROMPT, TARGET_INSTRUCTIONS

        try:
            client = ClaudeClient(model=self._model or "haiku")
        except Exception:
            from prompt_master.optimizer import optimize_prompt
            from prompt_master.vibe import _parse_sections

            result = optimize_prompt(self._idea, self._target, use_api=False)
            sections = _parse_sections(result.optimized_prompt)
            self.call_from_thread(self._finish_generation, sections, None)
            return

        target_inst = TARGET_INSTRUCTIONS.get(self._target, TARGET_INSTRUCTIONS["general"])
        user_msg = f"**Idea:** {self._idea}\n\n**Target:** {target_inst}"

        accumulated = ""
        try:
            for chunk in client.generate_stream(META_SYSTEM_PROMPT, user_msg):
                accumulated += chunk
                self.call_from_thread(self._stream_update, accumulated)
        except Exception:
            if not accumulated:
                from prompt_master.optimizer import optimize_prompt
                from prompt_master.vibe import _parse_sections

                result = optimize_prompt(self._idea, self._target, use_api=False)
                sections = _parse_sections(result.optimized_prompt)
                self.call_from_thread(self._finish_generation, sections, None)
                return

        from prompt_master.vibe import _parse_sections

        sections = _parse_sections(accumulated)
        self.call_from_thread(self._finish_generation, sections, client)

    def _stream_update(self, text_so_far: str) -> None:
        from prompt_master.vibe import _parse_sections

        sections = _parse_sections(text_so_far)
        for name, content in sections.items():
            if name == "_preamble" or not content.strip():
                continue
            self.canvas.update_section(name, content, highlight=False)

    def _finish_generation(self, sections: dict, client) -> None:
        self.canvas.hide_loading()
        for name, content in sections.items():
            if name == "_preamble":
                continue
            self.canvas.update_section(name, content, highlight=False)

        status = self.canvas.status_line
        status.update_session(self._session_id)
        status.update_tokens(len(self.canvas.get_prompt_text()) // 4, 50_000)
        if client:
            for part in client.usage.summary().split("|"):
                part = part.strip()
                if part.startswith("Cost:"):
                    status.update_cost(part.replace("Cost:", "").strip())

        self._run_scoring()
        self._auto_copy()
        self.notify("Prompt ready — copied to clipboard", timeout=3)

    def _generation_error(self, error_msg: str) -> None:
        self.canvas.hide_loading()
        self.notify(f"Error: {error_msg}", severity="error", timeout=5)
        self._show_scaffold()

    # ── Floor input: streaming refinement ──────────────────────────────

    def on_canvas_user_submitted(self, message: Canvas.UserSubmitted) -> None:
        if self._no_api:
            self.notify("Offline mode — edit sections directly", timeout=3)
            return
        self.canvas.show_loading("refining...")
        self.run_worker(
            lambda: self._stream_refinement(message.text),
            name="refine",
            thread=True,
        )

    def _stream_refinement(self, user_message: str) -> None:
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
            f"User request: {user_message}\n\nReturn the complete updated prompt."
        )
        refine_model = self._model if self._model else "haiku"

        try:
            client = ClaudeClient(model=refine_model)
            accumulated = ""
            for chunk in client.generate_stream(system, user_content):
                accumulated += chunk
                self.call_from_thread(self._stream_update, accumulated)

            sections = _parse_sections(accumulated)
            self.call_from_thread(self._finish_refinement, sections, user_message, client)
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
        self._auto_copy()
        # Invalidate variation cache for updated sections
        for name in updated:
            from prompt_master.vibe import _parse_sections

            content = _parse_sections(self.canvas.get_prompt_text()).get(name, "")
            self._variation_cache.content_key(name, content)
            # Old cache entries are stale — removal happens naturally via LRU

    def _refinement_error(self, error_msg: str) -> None:
        self.canvas.hide_loading()
        self.notify(f"Error: {error_msg}", severity="error", timeout=5)

    # ── Scoring ───────────────────────────────────────────────────────

    def _run_scoring(self) -> None:
        from prompt_master.tui.realtime_scorer import score_sections, compute_overall_score
        from prompt_master.vibe import _parse_sections
        from prompt_master.tui.section_block import SectionBlock

        prompt_text = self.canvas.get_prompt_text()
        sections = _parse_sections(prompt_text)
        scores = score_sections(sections, self._target)

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
            self.notify("No output file (use --output)", timeout=3)

    def action_help(self) -> None:
        self.notify(
            "Space: steer (◄► dimension, ▲▼ value) | Tab: explore variations | "
            "Ctrl+C: copy | Ctrl+S: save | Ctrl+Q: quit | Type below: refine",
            timeout=8,
        )
