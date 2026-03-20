<div align="center">

```
                                  _                         _
  _ __  _ __ ___  _ __ ___  _ __ | |_   _ __ ___   __ _ ___| |_ ___ _ __
 | '_ \| '__/ _ \| '_ ` _ \| '_ \| __| | '_ ` _ \ / _` / __| __/ _ \ '__|
 | |_) | | | (_) | | | | | | |_) | |_  | | | | | | (_| \__ \ ||  __/ |
 | .__/|_|  \___/|_| |_| |_| .__/ \__| |_| |_| |_|\__,_|___/\__\___|_|
 |_|                        |_|
```

**Turn vague ideas into optimized prompts.**

*One command. Five domains. Two modes — template-based or AI-powered.*
*Parallelization-aware. Multi-agent workflow native.*

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](#installation)
[![Tests](https://img.shields.io/badge/tests-180%2B%20passing-brightgreen)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](#license)

</div>

---

## The Problem

You have a great idea. You type it into ChatGPT. The result is... okay. Because your prompt was vague, and AI does exactly what you ask — no more, no less.

**Prompt Master** bridges the gap between what you *think* and what the AI *needs to hear*:

```
Your idea:    "build an api"
```
```
Prompt Master output:

  # Role
  You are an expert software engineer with deep knowledge of best practices,
  design patterns, and clean code principles.

  # Task
  Write code that builds a RESTful API with proper endpoint structure,
  request validation, error handling, and authentication middleware.

  # Output Format
  Provide the code in a fenced code block with the language specified.
  Include comments for complex logic.

  # Requirements
  Follow best practices. Include error handling and input validation.
  Write clean, readable code with meaningful variable names.
```

---

## Quick Start

### Install

```bash
pip install -e .              # from source
```

### Set up (optional — works without an API key too)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."    # enables AI-powered optimization
```

### Use

```bash
# One-shot optimization (template-based, instant)
prompt-master optimize "build an api" -t code

# AI-powered optimization
prompt-master optimize "build an api" -t code

# Interactive: asks clarifying questions first
prompt-master optimize "build an api" -t code -m interactive

# Chat mode: collaborative back-and-forth with Claude
prompt-master chat "I want to build something with websockets" -t code
```

---

## Features

### Dual-Mode Optimization

| Mode | Speed | Quality | API Key? |
|------|-------|---------|----------|
| **Template** (`--no-api`) | Instant | Good | No |
| **AI-powered** | 2-5s | Excellent | Yes |

Template mode uses structured slot-filling with domain-specific templates. AI mode sends your idea to Claude with a meta-prompt engineered for prompt optimization. Falls back to template mode gracefully if no API key is set.

### Five Target Domains

```bash
prompt-master optimize "your idea" -t general    # default — clear, structured
prompt-master optimize "your idea" -t code       # languages, frameworks, errors
prompt-master optimize "your idea" -t creative   # tone, style, voice, narrative
prompt-master optimize "your idea" -t analysis   # data sources, methodology
prompt-master optimize "your idea" -t workflow   # multi-agent, parallelization
```

### Workflow & Multi-Agent Design

The `workflow` target is purpose-built for designing parallelized, multi-agent systems:

```bash
prompt-master optimize "automated code review pipeline" -t workflow
```

```
Prompt Master output:

  # Role
  You are a multi-agent systems architect specializing in workflow
  decomposition, task parallelization, and orchestration design.

  # Task
  Design a multi-agent workflow that implements an automated code
  review pipeline with specialized agents for style, security,
  performance, and test coverage analysis.

  # Agents
  | Agent | Role | Tools | Input | Output |
  |-------|------|-------|-------|--------|
  | StyleAgent    | Check formatting & conventions | linter    | diff | style report   |
  | SecurityAgent | Scan for vulnerabilities       | semgrep   | diff | security report |
  | PerfAgent     | Identify performance issues    | profiler  | diff | perf report     |
  | TestAgent     | Verify test coverage           | pytest    | diff | coverage report |
  | Aggregator    | Merge all reports              | none      | reports | final review |

  # Dependency Graph
  [StyleAgent | SecurityAgent | PerfAgent | TestAgent] -> [Aggregator]
  (all review agents run in parallel, Aggregator waits for all)

  # Orchestration
  Fan-out/fan-in: dispatch to all review agents concurrently,
  aggregate results when all complete.

  # Error Handling
  - Any agent fails: retry 2x, then mark section as "review skipped"
  - Aggregator always runs with whatever results are available
```

Parallelization awareness is active across **all** targets — even in `code` or `analysis` mode, if your idea involves a pipeline or multi-step process, Prompt Master will suggest concurrent execution where it fits.

### Conversational Chat Mode

Don't know exactly what you want? Dump your chaotic thoughts and refine them through dialogue:

```bash
prompt-master chat "something about a REST API for managing recipes"
```

```
  Prompt Master — Chat Mode
  Target: code  |  Session: a3f2b1c9
  Type /help for commands, /done to finalize
  ──────────────────────────────────────────────────────

  You: something about a REST API for managing recipes

  Claude: So you want to build a recipe management API — nice!
  A couple of quick questions: Are you thinking CRUD operations
  (create, read, update, delete recipes)? And do you have a
  preferred framework — Flask, FastAPI, Express?

  You: fastapi, yeah CRUD plus search by ingredients

  Claude: Got it — here's a draft:
  ===PROMPT_START===
  ...structured prompt...
  ===PROMPT_END===

  You: add pagination and auth

  Claude: Updated:
  ...refined prompt...

  You: /done
```

**Chat commands:**

| Command | Action |
|---------|--------|
| `/done` | Finalize and extract the prompt |
| `/draft` | Show current prompt draft |
| `/save` | Save session for later |
| `/quit` | Save and exit |
| `/help` | List commands |

**Session persistence** — resume any conversation:

```bash
prompt-master chat --resume a3f2b1c9
```

### Interactive Mode

Guided clarification before optimization — asks the right questions for each domain:

```bash
prompt-master optimize "build an api" -t code -m interactive
```

```
Your idea: build an api
Who is the intended audience? > junior developers
Any specific constraints? > must use Python 3.10+
Programming language and framework? > Python with FastAPI
Desired output format? > code with comments
```

### Custom Templates

```bash
prompt-master templates list              # see all templates
prompt-master templates show code         # view a template
prompt-master templates save my-tmpl --from custom.toml   # add your own
```

Templates are TOML files that define role, task prefix, output format, and constraints. User templates in `~/.prompt_master/templates/` override built-in ones.

### Visual Canvas (TUI)

A full-screen interactive canvas for visual prompt crafting, powered by Textual:

```bash
# Open with an idea
prompt-master tui "build a REST API for recipes" -t code

# Resume a previous session
prompt-master tui --resume a3f2b1c9

# Offline mode (no API calls)
prompt-master tui "data pipeline" --no-api

# Save prompt to file on exit
prompt-master tui "chatbot assistant" -o prompt.md
```

```
  Prompt Master — TUI Canvas                         [?] Help  [Ctrl+Q] Quit
  ┌─── Sections ──────────────────────┐┌─── Preview ──────────────────────────┐
  │                                    ││                                      │
  │  # Role                            ││  # Role                              │
  │  You are an expert software...     ││  You are an expert software          │
  │                                    ││  engineer specializing in ...        │
  │  # Task                            ││                                      │
  │  Design and implement a ...        ││  # Task                              │
  │                                    ││  Design and implement a RESTful...   │
  │  # Output Format                   ││                                      │
  │  Provide the code in ...           ││  # Output Format                     │
  │                                    ││  Provide the code in a fenced...     │
  └────────────────────────────────────┘└──────────────────────────────────────┘
  ┌─── Conversation ──────────────────────────────────────────────────────────┐
  │  > make the error handling more specific                                  │
  └───────────────────────────────────────────────────────────────────────────┘
  [Tab] Explore  [Ctrl+R] Recommend  [Ctrl+D] Decompose  [Ctrl+S] Save
```

**Keybindings:**

| Key | Action |
|-----|--------|
| `Tab` | Explore variations for the current section |
| `Ctrl+R` | Get AI recommendation for improvement |
| `Ctrl+D` | Decompose into a multi-agent workflow |
| `Ctrl+S` | Save prompt |
| `Ctrl+H` | Toggle conversation history |
| `Ctrl+Z` | Undo last change |
| `?` | Show help overlay |
| `Ctrl+Q` | Quit |

### Benchmarking Suite

Measure and track prompt quality across releases:

```bash
# Run full benchmark (template mode — no API cost)
prompt-master benchmark --no-api

# Benchmark a specific domain
prompt-master benchmark -d code --no-api

# Include LLM-as-judge scoring (requires API)
prompt-master benchmark --judge

# Save results for comparison
prompt-master benchmark --no-api --save --tag v0.2.0
```

The benchmark suite evaluates 23 cases across all five domains, checking:
- **Structure** — markdown headers, formatting, lists
- **Sections** — required sections present (Role, Task, Output Format)
- **Keywords** — domain-relevant terms preserved
- **Specificity** — vague filler phrases eliminated
- **LLM judge** (optional) — clarity, completeness, intent preservation, domain fit

```
  Prompt Master — Benchmark Report
  ══════════════════════════════════════════════════════
  Date:    2026-03-20T12:00:00
  Cases:   23
  Domains: general, code, creative, analysis, workflow

  ── GENERAL ──
    gen-01  [████████████████░░░░]  80.0%  [TPL]    3ms  vague_greeting
    gen-02  [██████████████████░░]  90.0%  [TPL]    2ms  email_request
    ...

  ── SUMMARY ──
  Structural avg: 82.5%
```

### Claude Code & OpenClaw Skills

Prompt Master ships with slash commands for Claude Code and OpenClaw — use prompt-master's methodology directly inside your AI coding assistant:

```bash
# In Claude Code or OpenClaw, type:
/optimize-prompt "build a REST API for managing recipes"
/design-workflow "automated CI/CD pipeline with testing and deployment"
/project:benchmark
```

| Skill | What it does |
|-------|-------------|
| `/optimize-prompt` | Applies the full 7-principle optimization (including parallelization awareness) to any idea |
| `/design-workflow` | Designs a complete multi-agent workflow with dependency graph, orchestration pattern, and error handling |
| `/project:benchmark` | Runs the benchmark suite and analyzes results with improvement suggestions |

Install by cloning the repo — Claude Code auto-discovers `.claude/commands/`:

```bash
git clone https://github.com/thrmnn/prompt_master.git
cd prompt_master
# Skills are now available as /optimize-prompt, /design-workflow, /project:benchmark
```

---

## Architecture

```
prompt-master
├── optimize          Single-shot prompt optimization
│   ├── API mode      Claude-powered with meta-prompt engineering
│   └── Template mode Structured slot-filling (instant, offline)
├── chat              Conversational prompt building
│   ├── Engine        Multi-turn state machine with marker filtering
│   ├── Sessions      JSON persistence (~/.prompt_master/sessions/)
│   └── Display       Streaming output with color formatting
├── tui               Visual canvas for interactive prompt crafting
│   ├── Canvas        Full-screen Textual app with split-pane layout
│   ├── Keybindings   Centralized key definitions and help overlay
│   └── Sections      Editable prompt sections with live preview
├── templates         TOML-based prompt templates
│   ├── Built-in      general, code, creative, analysis, workflow
│   └── User          ~/.prompt_master/templates/
├── benchmark         Quality evaluation suite
│   ├── Cases         23 TOML test cases across 5 domains
│   ├── Scorer        Automated structural checks
│   ├── Judge         LLM-as-judge evaluation (optional)
│   └── Report        Terminal + JSON output
└── .claude/commands  Claude Code & OpenClaw skills
    ├── optimize-prompt   Optimize any prompt with PM methodology
    ├── design-workflow   Design multi-agent workflows
    └── benchmark         Run and analyze benchmarks
```

### Module Map

| Module | Purpose |
|--------|---------|
| `cli.py` | Click command definitions |
| `optimizer.py` | Core optimization pipeline (API + fallback) |
| `client.py` | Anthropic SDK wrapper with streaming |
| `fallback.py` | Template-based prompt building |
| `templates.py` | Template loading, discovery, persistence |
| `prompts.py` | System prompts for chat mode |
| `conversation.py` | Chat state machine + stream marker filter |
| `chat.py` | Interactive chat loop orchestration |
| `session.py` | Session save/load/resume |
| `display.py` | Terminal UX (colors, streaming, banners) |
| `interactive.py` | Clarifying question flow |
| `tui/` | Visual canvas app (Textual-based TUI) |
| `tui/keybindings.py` | Centralized keybinding definitions and help text |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_conversation.py -v

# Run with coverage
python -m pytest tests/ --cov=prompt_master --cov-report=term-missing
```

100+ tests covering: CLI commands, optimization pipeline, template management, conversation engine, stream filtering, session persistence, chat integration, benchmarking, and workflow domain.

---

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude API access | *(none — template mode)* |
| `~/.prompt_master/templates/` | Custom templates | *(empty)* |
| `~/.prompt_master/sessions/` | Chat session storage | *(auto-created)* |

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan toward v1.0 and beyond.

**Next up:**
- Voice input via Whisper
- Thought Guidance — proactive suggestions during chat
- Workflow visualization — render dependency graphs as diagrams

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Run tests (`python -m pytest tests/ -v`)
4. Run benchmarks to check quality (`prompt-master benchmark --no-api`)
5. Commit and open a PR

---

## License

MIT
