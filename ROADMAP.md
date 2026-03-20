# Roadmap — Prompt Master v1.0

This document tracks what's done, what's in progress, and what's needed before the v1.0 stable release.

---

## Status Overview

| Phase | Status | Version |
|-------|--------|---------|
| Core CLI + Templates | Done | v0.1.0 |
| Conversational Chat Mode | Done | v0.2.0 |
| Benchmarking Suite | Done | v0.2.0 |
| Documentation + README | Done | v0.2.0 |
| Workflow & Parallelization Domain | Done | v0.3.0 |
| Claude Code / OpenClaw Skills | Done | v0.3.0 |
| Production Hardening | Done | v0.4.0 |
| Vibe Mode | Done | v0.4.0 |
| TUI Canvas | Done | v0.5.0 |
| Voice Input | Planned | v0.6.0 |
| Thought Guidance | Planned | v0.6.0 |
| Stable Release | Planned | v1.0.0 |

---

## Completed in v0.4.0

### Must-Have (all complete)

- [x] **Error handling hardening** — Retry with exponential backoff for API timeouts and rate limits (`client.py`)
- [x] **Input validation** — `validate_idea()` rejects empty/too-short/too-long input, sanitizes whitespace
- [x] **API cost guardrails** — `UsageStats` tracks tokens and cost per call, `--max-tokens` flag, cost displayed after API calls
- [x] **Template validation** — `validate_template()` checks schema (meta, role, defaults sections) on load
- [x] **Session cleanup** — `prompt-master sessions list`, `sessions prune --older-than 30d`, `sessions delete`
- [x] **CI/CD pipeline** — GitHub Actions: lint (ruff), test (pytest) across Python 3.8/3.10/3.12, benchmark regression
- [x] **Packaging for PyPI** — Full metadata (author, URLs, classifiers, readme, license), sdist + wheel ready
- [x] **License file** — MIT LICENSE at repo root

### Should-Have (all complete)

- [x] **Prompt history** — `~/.prompt_master/history.jsonl` with `prompt-master history list|show|clear`
- [x] **Config file** — `~/.prompt_master/config.toml` for default target, model, max_tokens, format
- [x] **Model selection** — `--model sonnet|haiku|opus` on optimize and chat commands
- [x] **Output formats** — `--format json|markdown|plain` for programmatic use
- [x] **Benchmark regression CI** — CI fails if benchmark structural avg drops below 75%

### Vibe Mode (complete)

- [x] **`prompt-master vibe "idea"`** — Generate prompt variations along 5 dimensions
- [x] **VibeEngine** with `generate_variations()`, `mutate()`, `compare()`
- [x] **5 dimensions**: tone, audience, format, specificity, style
- [x] **Offline fallback** — Template-based variations when no API key
- [x] **CLI**: `-n count`, `-d dimensions`, `-o output`, `--no-api`
- [x] **Variation parsing** — `===VARIATION_START===` / `===VARIATION_END===` markers
- [x] **Serialization** — `to_dict()` / `from_dict()` for persistence

---

## Before v1.0.0 — Remaining Work

### Nice-to-Have (ship with v1.0 if possible)

- [ ] **Voice Input** — `--voice` flag on `chat` command. Record from mic, transcribe via local Whisper or OpenAI API.
- [ ] **Thought Guidance** — `--guidance` flag on `chat`. Claude proactively suggests related topics, alternative framings, gaps/pitfalls.
- [ ] **Interactive vibe exploration** — Pick a variation, mutate it, branch further in a tree-exploration loop.
- [ ] **Workflow visualization** — Render dependency graphs as Mermaid/ASCII diagrams.
- [ ] **Workflow export formats** — Export workflows as LangGraph, CrewAI, or AutoGen configs.

### Post-stable (v1.x)

- [ ] **Plugin system** — Custom post-processors, output adapters, template sources.
- [ ] **Team features** — Shared template repositories, prompt review workflows.
- [ ] **Streaming in optimize mode** — `--stream` flag for real-time output.

---

## Release Checklist (v1.0.0)

```
Pre-release:
  [x] All must-have items complete
  [ ] 90%+ test coverage
  [x] Benchmark structural avg > 80% (template mode) — currently 82.8%
  [ ] Benchmark structural avg > 90% (API mode)
  [x] README reflects all current features
  [x] CHANGELOG.md up to date
  [x] pyproject.toml metadata complete
  [x] LICENSE file present
  [ ] Tested on Python 3.8, 3.10, 3.12 (CI configured, pending first run)
  [ ] pip install from PyPI works clean

Release:
  [ ] Tag v1.0.0
  [ ] Build sdist + wheel
  [ ] Upload to PyPI
  [ ] GitHub release with changelog
  [ ] Update README badges with PyPI version
```

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| v0.1.0 | 2026-03-20 | Initial release: CLI optimizer, templates, interactive mode, 33 tests |
| v0.2.0 | 2026-03-20 | Chat mode, session persistence, benchmarking suite, docs, 76+ tests |
| v0.3.0 | 2026-03-20 | Workflow domain, parallelization awareness, Claude Code/OpenClaw skills, 121 tests |
| v0.4.0 | 2026-03-20 | Production hardening (all must-haves + should-haves), Vibe Mode, 181 tests |
| v0.5.0 | 2026-03-20 | TUI Canvas for visual prompt crafting with keybindings, section editing, and variation exploration |
