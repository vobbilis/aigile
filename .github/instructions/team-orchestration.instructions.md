---
applyTo: "specs/**/*.md"
description: "Enforces planning-only behaviour and team orchestration standards for the aigile project."
---

# Aigile — Planning & Orchestration Standards

## Planning Rules (when creating or editing files in `specs/`)

- **Never write implementation code** in a plan document
- **Never edit** `backend/` or `frontend/` source files as part of producing a plan
- Every task must have: Task ID, Depends On, Assigned To (builder or validator)
- Final task must always be `validate-all`

### Required sections in every plan file

The `postToolUse` hook validates these exist. Missing any will block the write:

- `## Task Description`
- `## Objective`
- `## Relevant Files`
- `## Step by Step Tasks`
- `## Acceptance Criteria`
- `## Team Orchestration`
- `### Team Members`

### Project-specific task types

- `backend-task` — changes to `backend/` Python files
- `frontend-task` — changes to `frontend/src/` TypeScript/React files
- `test-task` — adds or updates tests
- `config-task` — CI, tooling, config files

## Orchestration Model

Plans are created with the `plan-with-team` prompt and executed with the `build` prompt.

### How it works

1. The **main agent** acts as orchestrator — it reads the plan and drives execution
2. **Builder sub-agents** implement tasks (dispatched via `runSubagent("builder", ...)`)
3. **Validator sub-agent** verifies each task (dispatched via `runSubagent("validator", ...)`)
4. Sub-agents are **stateless** — each invocation gets the full task description from the plan
5. Sub-agents **report back** to the orchestrator with structured status (`COMPLETED`/`FAILED` for builders, `PASS`/`FAIL` for validators)
6. The orchestrator decides: proceed to next task, or trigger a **fix cycle** (max 2 per task)

### Execution sequence per task

```
Orchestrator → runSubagent("builder", task description)
            ← builder returns: Status: COMPLETED/FAILED
Orchestrator → runSubagent("validator", verify task)
            ← validator returns: Status: PASS/FAIL
            If FAIL → re-dispatch builder with fix context (max 2 cycles)
            If PASS → mark task done, move to next
```

### Key constraints

- Sub-agents execute **sequentially**, not in parallel
- Sub-agents **cannot communicate** with each other — only with the orchestrator
- The **filesystem is shared** — agents see each other's file changes
- Task descriptions must be **exhaustive** — agents cannot ask for clarification
- Dependencies are honored by the orchestrator — tasks dispatch in `Depends On` order
