# Changelog

All notable changes to Prompt Master will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [0.5.0] - 2026-03-20

### Added
- **TUI Canvas** (`prompt-master tui`) — interactive visual prompt crafting in the terminal
  - Full-screen Textual-based canvas with split-pane layout
  - Section-based prompt editing with live preview
  - Variation exploration drawer (`Tab` to explore, `1-9` to pick)
  - AI-powered recommendations (`Ctrl+R`) and workflow decomposition (`Ctrl+D`)
  - Conversation panel with streaming responses (`Ctrl+H` to toggle history)
  - Centralized keybinding system (`keybindings.py`) with `?` help overlay
  - Session resume support (`--resume`) and file output on exit (`--output`)
  - Offline mode (`--no-api`) for template-based-only editing
  - Model selection (`--model sonnet|haiku|opus`)
- **`textual>=0.75`** added as a dependency

### Changed
- `cli.py` — Added `tui` command with `--target`, `--resume`, `--output`, `--model`, `--no-api` options
- Bumped version to 0.5.0

---

## [0.4.0] - 2026-03-20

### Added
- **Vibe Mode** (`prompt-master vibe "idea"`) — generate prompt variations along 5 dimensions
  - `VibeEngine` with `generate_variations()`, `mutate()`, `compare()`
  - 5 dimensions: tone, audience, format, specificity, style
  - Variation markers (`===VARIATION_START===` / `===VARIATION_END===`) for API parsing
  - Template-based fallback variations (no API key needed)
  - CLI options: `-n count`, `-d dimensions`, `-o output`, `--no-api`
  - Full serialization support (`to_dict()` / `from_dict()`)
- **Input validation** (`validation.py`) — `validate_idea()` rejects empty/short/long input
  - `validate_template()` schema validation for TOML templates
- **API cost guardrails** — `UsageStats` class tracks tokens and cost per call
  - `estimate_cost()` for all Claude models
  - `--max-tokens` flag on optimize and chat commands
  - Cost summary displayed after API calls
- **Retry with exponential backoff** — `client.py` retries on `APIConnectionError` and `RateLimitError` (3 attempts)
- **Model selection** — `--model sonnet|haiku|opus` on optimize and chat commands
- **Output formats** — `--format json|markdown|plain` on optimize command
- **Config file** (`config.py`) — `~/.prompt_master/config.toml` for default target, model, max_tokens, format
- **Prompt history** (`history.py`) — `~/.prompt_master/history.jsonl` auto-records all generations
  - `prompt-master history list|show|clear` commands
- **Session management** — `prompt-master sessions list|prune|delete` commands
  - `prune_sessions(older_than_days)` for cleanup
- **CI/CD pipeline** — GitHub Actions with lint (ruff), test (pytest 3.8/3.10/3.12), benchmark regression
- **PyPI-ready packaging** — Full metadata: author, URLs, classifiers, readme, license
- **MIT LICENSE** at repo root

### Changed
- `client.py` — Rewritten with model catalog, retry logic, `UsageStats` tracking, configurable `max_tokens`
- `optimizer.py` — `optimize_prompt()` accepts `model` and `max_tokens` params, returns usage metadata
- `cli.py` — Major expansion: vibe, history, sessions commands; `--model`, `--max-tokens`, `--format` options; config integration
- `templates.py` — `load_template()` now validates schema via `validate_template()`
- Bumped version to 0.4.0

## [0.3.0] - 2026-03-20

### Added
- **Workflow target domain** (`-t workflow`) — multi-agent workflow design with parallelization awareness
  - Specialized system prompt for agent decomposition, dependency graphs, and orchestration patterns
  - Built-in workflow template with agent table, dependency graph, and error handling structure
  - Interactive mode questions: agents, orchestration pattern, tools/APIs
  - 5 workflow benchmark cases (simple pipeline through complex orchestration)
- **Parallelization awareness across all targets** — META_SYSTEM_PROMPT now includes parallelization as the 7th principle; workflow structures are proposed whenever the idea involves pipelines or multi-step processes, regardless of target
- **Claude Code / OpenClaw skills** (`.claude/commands/`)
  - `/optimize-prompt` — apply the full 7-principle optimization methodology inside Claude Code
  - `/design-workflow` — design complete multi-agent workflows with dependency graphs
  - `/project:benchmark` — run and interpret the benchmark suite with improvement suggestions
- **CLAUDE.md** — project context file for Claude Code auto-discovery

### Changed
- `optimizer.py` — META_SYSTEM_PROMPT expanded with parallelization awareness (principle 7) and multi-agent workflow guidance
- `fallback.py` — Added workflow target roles, task prefixes, format, and context fields (agents, orchestration, tools)
- `prompts.py` — Added workflow target hint and parallelization guidance to chat system prompt
- `interactive.py` — Added workflow-specific questions (agents, orchestration, tools)
- All CLI target choice lists now include `workflow`
- Bumped version to 0.3.0

## [0.2.0] - 2026-03-20

### Added
- **Conversational chat mode** (`prompt-master chat`) — interactive prompt building through natural dialogue with Claude
  - Streaming responses with real-time marker filtering
  - Slash commands: `/done`, `/draft`, `/save`, `/quit`, `/help`
  - Session persistence with save/resume (`--resume <id>`)
  - Domain-aware system prompts for all four targets
- **Benchmarking suite** (`prompt-master benchmark`) — systematic quality evaluation
  - 18 test cases across 4 domains (general, code, creative, analysis)
  - Automated structural scorer (sections, keywords, specificity, structure)
  - Optional LLM-as-judge evaluation (`--judge`)
  - JSON report export (`--save`) and comparison tooling
  - Difficulty-graded cases (easy/medium/hard)
- **Documentation** — README with architecture overview, quick start, feature docs
- **ROADMAP.md** — Release plan for v1.0

### Changed
- `client.py` — Added `converse()` and `converse_stream()` methods for multi-turn conversations
- Bumped version to 0.2.0

## [0.1.0] - 2026-03-20

### Added
- Core CLI with `prompt-master optimize` command
- Claude API-powered optimization via meta-prompt engineering
- Template-based fallback optimization (no API key needed)
- Interactive clarifying-question mode (`-m interactive`)
- 4 built-in TOML templates: general, code, creative, analysis
- Custom template management: `prompt-master templates list|show|save`
- 33 passing tests
