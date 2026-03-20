# Prompt Master — Claude Code Context

## What this project is

Prompt Master is a CLI tool that transforms vague ideas into optimized, structured prompts. It supports 5 target domains (general, code, creative, analysis, workflow), dual optimization modes (AI-powered via Claude API + template-based fallback), conversational chat for iterative refinement, and a benchmarking suite.

## Project structure

```
src/prompt_master/       # Core library
  cli.py                 # Click CLI: optimize, chat, benchmark, templates
  optimizer.py           # API + fallback optimization pipeline, META_SYSTEM_PROMPT
  client.py              # Anthropic SDK wrapper (generate, converse, converse_stream)
  fallback.py            # Template-based prompt building (TARGET_ROLES, etc.)
  prompts.py             # System prompts for chat mode + target hints
  conversation.py        # Multi-turn engine, StreamFilter, Phase state machine
  chat.py                # Interactive chat loop with slash commands
  session.py             # Session persistence (~/.prompt_master/sessions/)
  display.py             # Terminal UX (colors, streaming, banners)
  interactive.py         # Clarifying question flow
  templates.py           # Template loading/saving from TOML files
templates/               # Built-in TOML templates (general, code, creative, analysis, workflow)
benchmarks/              # Quality evaluation suite
  cases/                 # TOML test case definitions per domain
  scorer.py              # Structural scoring (sections, keywords, specificity)
  judge.py               # LLM-as-judge evaluation
  runner.py              # Benchmark orchestration
  report.py              # Terminal + comparison formatting
tests/                   # pytest suite (100+ tests)
```

## Key commands

```bash
prompt-master optimize "idea" -t <target> [--no-api] [-m interactive] [-o file]
prompt-master chat "idea" -t <target> [--resume <id>] [-o file]
prompt-master benchmark [-d <domain>] [--no-api] [--judge] [--save]
prompt-master templates list|show|save
```

## Targets: general, code, creative, analysis, workflow

The `workflow` target is specifically designed for multi-agent system design with parallelization awareness. It decomposes tasks into specialized agents, identifies dependency graphs, and proposes orchestration patterns.

## How to run tests

```bash
python -m pytest tests/ -v
```

All tests must pass before committing. The benchmark suite (`prompt-master benchmark --no-api`) can run without an API key.

## Development patterns

- Click for CLI, Anthropic SDK for API
- Dataclasses for models (OptimizationResult, ConversationEngine, etc.)
- TOML for templates and benchmark cases
- JSON for session persistence
- pytest + pytest-mock for testing
- All new features need tests alongside
- Template mode must always work offline (no API key)

## When modifying the optimizer

The prompt engineering logic lives in two layers:
1. `optimizer.py:META_SYSTEM_PROMPT` — the meta-prompt that guides Claude to write good prompts
2. `fallback.py` — template-based slot-filling that works offline

Both must support all 5 targets. Changes to one should be reflected in the other where applicable.

## Custom slash commands

See `.claude/commands/` for project-specific slash commands:
- `/optimize-prompt` — optimize any prompt using prompt-master methodology
- `/design-workflow` — design a multi-agent workflow with parallelization
- `/project:benchmark` — run and interpret the benchmark suite
