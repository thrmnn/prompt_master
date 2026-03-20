---
name: design-workflow
description: Design a complete multi-agent workflow with dependency graph, orchestration pattern, and error handling. Use this when the user needs to decompose a complex task into parallelizable agents.
user-invocable: true
argument-hint: "task or system to design a workflow for"
---

# Design Multi-Agent Workflow

You are a multi-agent systems architect. The user will describe a task or system and you will design a complete, parallelization-aware multi-agent workflow.

## Your argument

$ARGUMENTS

## Process

1. **Decompose the task** into the smallest meaningful subtasks. Each subtask becomes a candidate agent.

2. **Identify dependencies**: Build a dependency graph.
   - Which subtasks are truly independent? → These MUST run in parallel.
   - Which subtasks depend on outputs of others? → These are sequential.
   - Are there feedback loops? → Mark them explicitly.

3. **Assign agent roles**: For each agent, define:
   - **Name** — descriptive, role-based (e.g., `ResearchAgent`, `ValidatorAgent`)
   - **Responsibility** — single, clear purpose (separation of concerns)
   - **Tools** — what external tools/APIs this agent needs
   - **Input** — what it receives (from user, from other agents, or from orchestrator)
   - **Output** — what it produces and in what format
   - **Error handling** — retry count, fallback strategy, escalation path

4. **Choose orchestration pattern**:
   - **Pipeline** — linear A → B → C (use when steps are naturally sequential)
   - **Fan-out / Fan-in** — parallel execution then aggregation (use when subtasks are independent)
   - **Router** — dynamic dispatch based on input type (use when different inputs need different processing)
   - **Hierarchical** — supervisor delegates to sub-agents (use for complex, multi-level workflows)
   - **Hybrid** — combine patterns (most real workflows need this)

5. **Define the data contract** between agents: specify the exact schema or format agents use to communicate.

6. **Add human-in-the-loop checkpoints** where appropriate (high-stakes decisions, ambiguous cases, quality gates).

## Output format

Structure your response as:

```markdown
## Overview
One-paragraph summary of the workflow.

## Agents
| Agent | Responsibility | Tools | Input | Output |
|-------|---------------|-------|-------|--------|
| ...   | ...           | ...   | ...   | ...    |

## Dependency Graph
[AgentA] ──→ [AgentC] ──→ [AgentE]
[AgentB] ──↗            ↗
           [AgentD] ──↗

## Orchestration Pattern
Describe the pattern and why it fits.

## Data Flow
Step-by-step: what flows between agents and in what format.

## Error Handling
Per-agent failure modes and recovery strategies.

## Human Checkpoints
Where and why a human should review before proceeding.
```

## Rules

- Maximize parallelism. If two agents don't depend on each other, they MUST be marked as parallel.
- Each agent gets ONE job. If an agent does two unrelated things, split it.
- Prefer simplicity. Don't add agents or layers that don't earn their complexity.
- Always include error handling — production workflows fail, and the design must account for it.
- Use concrete names and schemas, not abstract placeholders.
