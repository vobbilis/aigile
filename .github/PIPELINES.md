# Copilot Agent Pipelines — Architecture & Design

> **Audience**: Engineers evaluating, extending, or debugging the agent pipeline system.
> Novice-friendly explanations with full technical depth for advanced users.

This document describes the three orchestration pipelines that power automated development in this repository. Each pipeline is a **prompt file** (`.github/prompts/*.prompt.md`) that turns GitHub Copilot's chat agent into a multi-agent orchestrator — dispatching specialized sub-agents to plan, build, validate, and review code changes.

---

## Table of Contents

- [System Overview](#system-overview)
- [Key Concepts](#key-concepts)
- [Pipeline 1: plan\_to\_build](#pipeline-1-plan_to_build)
- [Pipeline 2: build](#pipeline-2-build)
- [Pipeline 3: bug\_to\_pr](#pipeline-3-bug_to_pr)
- [Agent Registry](#agent-registry)
- [Guardrails & Safety Nets](#guardrails--safety-nets)
- [File Map](#file-map)
- [FAQ](#faq)

---

## System Overview

The system follows a **hub-and-spoke orchestration model**: the main Copilot chat agent acts as the orchestrator (hub), and stateless sub-agents (spokes) do the actual work. Sub-agents cannot talk to each other — all communication flows through the orchestrator.

```mermaid
graph TB
    User((👤 User))

    subgraph "Copilot Chat Agent (Orchestrator)"
        PTB["/plan_to_build"]
        BUILD["/build"]
        BTP["/bug_to_pr"]
    end

    subgraph "Sub-Agents (Stateless)"
        B["🔨 builder"]
        V["✅ validator"]
        BC["🔍 bug-creator"]
        BR["🧭 bug-router"]
        BFB["🔧 bug-fixer-backend"]
        BFF["🎨 bug-fixer-frontend"]
        REV["⚖️ bug-reviewer"]
    end

    subgraph "Guardrails"
        HOOK["postToolUse hook"]
        SESSION["sessionStart hook"]
    end

    subgraph "Artifacts"
        SPECS["specs/*.md"]
        BUGS["bugs/BUG-*/"]
        PR["GitHub PR"]
    end

    User -->|"invoke"| PTB
    User -->|"invoke"| BUILD
    User -->|"invoke"| BTP

    PTB -->|"produces"| SPECS
    BUILD -->|"reads"| SPECS
    BUILD -->|"dispatches"| B
    BUILD -->|"dispatches"| V
    BTP -->|"dispatches"| BC
    BTP -->|"dispatches"| BR
    BTP -->|"dispatches"| BFB
    BTP -->|"dispatches"| BFF
    BTP -->|"dispatches"| B
    BTP -->|"dispatches"| V
    BTP -->|"dispatches"| REV
    BTP -->|"produces"| BUGS
    BTP -->|"produces"| PR

    B -.->|"file writes trigger"| HOOK
    BFB -.->|"file writes trigger"| HOOK
    BFF -.->|"file writes trigger"| HOOK
    BC -.->|"file writes trigger"| HOOK

    style PTB fill:#4A90D9,color:#fff
    style BUILD fill:#7B68EE,color:#fff
    style BTP fill:#E74C3C,color:#fff
    style HOOK fill:#F39C12,color:#000
```

### How It Works (Plain English)

1. **You describe what you want** — a feature, a bug fix, a task.
2. **A pipeline takes over** — it reads your request, dispatches specialized agents, validates their work, and produces artifacts (specs, code, PRs).
3. **Each agent does one thing** — a builder writes code, a validator checks it, a reviewer judges it. They never freelance.
4. **Guardrails catch mistakes** — hooks automatically lint Python, typecheck TypeScript, and validate document structure on every file write.

---

## Key Concepts

| Concept | What It Means |
|---------|--------------|
| **Orchestrator** | The main Copilot chat agent. It reads prompts, dispatches sub-agents via `runSubagent()`, and makes sequencing decisions. It never writes implementation code. |
| **Sub-Agent** | A stateless agent (defined in `.github/agents/*.agent.md`) that receives a task, executes it, and returns a structured report. Cannot talk to other agents. |
| **Prompt File** | A `.prompt.md` file in `.github/prompts/` that defines a pipeline's behavior. Invoked via `/command` in Copilot Chat. |
| **Spec File** | A plan document in `specs/` that fully describes what to build, who builds it, and how to validate it. The bridge between planning and execution. |
| **TDD Preamble** | Instructions prepended to every builder dispatch: write a failing test first (RED), implement minimally (GREEN), then refactor. |
| **Fix Cycle** | When a validator reports FAIL, the builder is re-dispatched with the failure context. Max 2 fix cycles per task before rollback. |
| **Rollback** | If a task fails after 2 fix cycles, `git checkout` reverts its changes. Broken code never stays in the codebase. |
| **postToolUse Hook** | A Python script that runs after every file write — lints `.py` files, typechecks `.ts/.tsx` files, and validates spec/report structure. |

---

## Pipeline 1: plan_to_build

**File**: `.github/prompts/plan_to_build.prompt.md`
**Purpose**: Turn a user's feature request into a detailed, agent-executable specification.
**Output**: `specs/<descriptive-name>.md`

This pipeline is **planning only** — it reads code, asks clarifying questions, and writes a spec document. It never modifies source code.

### Flow

```mermaid
flowchart LR
    A["👤 User describes\nfeature/task"] --> B["Analyze\nRequirements"]
    B --> C["Explore Codebase\n(read, grep, search)"]
    C --> D{"Brainstorm?\n(feature/enhancement)"}
    D -->|"Yes"| E["Ask user:\nWhich approach?"]
    D -->|"Skip"| F["Design\nSolution"]
    E --> F
    F --> G{"Team\nComposition?"}
    G -->|"Medium/Complex"| H["Ask user:\nHow many builders?"]
    G -->|"Simple"| I["Single builder"]
    H --> I
    I --> J["Write tasks\n(≥50 words each)"]
    J --> K["Self-Audit\n(counts & rules)"]
    K --> L["Save to\nspecs/*.md"]
    L --> M["Verify\n(file exists + 7 sections)"]
    M --> N["📄 Spec Ready"]

    style A fill:#4A90D9,color:#fff
    style N fill:#27AE60,color:#fff
    style K fill:#F39C12,color:#000
    style M fill:#F39C12,color:#000
```

### What the Spec Contains

Every spec has **7 required sections** (enforced by the postToolUse hook):

| Section | Purpose |
|---------|---------|
| `## Task Description` | What needs to be done and why |
| `## Objective` | Measurable definition of "done" |
| `## Relevant Files` | Exact file paths involved |
| `## Step by Step Tasks` | Ordered tasks with IDs, dependencies, assignments |
| `## Acceptance Criteria` | Specific, verifiable outcomes |
| `## Team Orchestration` | Team composition and execution model |
| `### Team Members` | Named builders and validators with roles |

### Quality Rules

These rules ensure specs are executable by stateless agents:

- **Task size**: 2–5 minutes of work, ~20 lines max. "Implement user authentication" is too big — split it.
- **Description minimum**: ≥50 words per task. One-liners are forbidden.
- **Design assertions**: Every route/model/component task needs 2–3 structural test assertions, not just "it works."
- **Intermediate validators**: Plans with >5 builder tasks need checkpoint validators between phases.
- **Self-audit**: Before saving, count tasks, verify word counts, check validator frequency.

### Example: How a Task Looks in a Spec

```markdown
### 3. Add validation error response
- **Task ID**: add-validation-error
- **Role**: builder
- **Depends On**: create-pydantic-model
- **Assigned To**: builder-1
- **Description**: |
    Add Pydantic validation to the POST /metrics endpoint in backend/main.py.
    Create a MetricCreate model in backend/models.py with fields: name (str, required),
    value (float, required), tags (dict[str,str], optional, default_factory=dict).
    Follow the existing MetricOut model pattern. The route should return 422 for
    invalid input. Verify with: cd backend && pytest tests/test_api.py -v -k test_create
```

---

## Pipeline 2: build

**File**: `.github/prompts/build.prompt.md`
**Purpose**: Execute a spec by dispatching builder and validator sub-agents in dependency order.
**Input**: A spec file from `specs/`
**Output**: Implemented, tested, validated code changes.

This pipeline is the **execution engine**. It reads a plan, dispatches agents one at a time, and handles success, failure, fix cycles, and rollbacks.

### Flow

```mermaid
flowchart TD
    START["📄 Read spec from\nspecs/*.md"] --> PARSE["Parse tasks,\ndeps, team"]
    PARSE --> TODO["Create todo list"]
    TODO --> NEXT{"Next task?"}

    NEXT -->|"builder task"| DISPATCH_B["Dispatch builder\n(with TDD preamble)"]
    NEXT -->|"validator task\n(final)"| DISPATCH_V_FINAL["Dispatch validator\n(full acceptance criteria)"]
    NEXT -->|"no more tasks"| REPORT["📊 Build Report"]

    DISPATCH_B --> CHECK_B{"Builder status?"}
    CHECK_B -->|"COMPLETED"| DISPATCH_V["Dispatch validator\n(verify task)"]
    CHECK_B -->|"FAILED"| DISPATCH_V

    DISPATCH_V --> CHECK_V{"Validator status?"}
    CHECK_V -->|"PASS ✅"| MARK_DONE["Mark task done"]
    CHECK_V -->|"FAIL ❌"| FIX_CHECK{"Fix cycle ≤ 2?"}

    FIX_CHECK -->|"Yes"| REFIX["Re-dispatch builder\nwith failure context"]
    FIX_CHECK -->|"No (exhausted)"| ROLLBACK["Rollback via\ngit checkout"]

    REFIX --> DISPATCH_V
    ROLLBACK --> MARK_DONE

    MARK_DONE --> CHECKPOINT{"Every 3 tasks:\ncheckpoint report"}
    CHECKPOINT --> NEXT

    DISPATCH_V_FINAL --> REPORT

    style START fill:#7B68EE,color:#fff
    style REPORT fill:#27AE60,color:#fff
    style ROLLBACK fill:#E74C3C,color:#fff
    style FIX_CHECK fill:#F39C12,color:#000
```

### The TDD Preamble

Every builder dispatch includes these mandatory instructions:

```
1. Write a FAILING test FIRST (RED)
2. Write MINIMAL implementation to pass (GREEN)
3. Refactor if needed, confirm still GREEN
```

This ensures test-driven development at the agent level — tests always exist before implementation.

### Fix Cycle Mechanics

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant B as Builder
    participant V as Validator

    O->>B: Task + TDD preamble
    B-->>O: Status: COMPLETED
    O->>V: Verify task
    V-->>O: Status: FAIL ❌

    Note over O: Fix cycle 1 of 2

    O->>B: Fix context + failure details
    B-->>O: Status: COMPLETED
    O->>V: Re-verify
    V-->>O: Status: PASS ✅

    Note over O: Task complete ✅
```

If the validator still reports FAIL after 2 fix cycles:

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant B as Builder
    participant V as Validator

    Note over O: Fix cycle 2 FAILED

    O->>B: ROLLBACK — git checkout files
    B-->>O: Rolled back

    Note over O: Task marked "ROLLED BACK"<br/>Continue to next task
```

### Checkpoints

After every 3 builder tasks, the orchestrator pauses and reports progress. This gives the user visibility and a chance to course-correct.

### Orchestrator Rules

| Rule | Why |
|------|-----|
| Never implement code yourself | All code goes through `runSubagent("builder")` |
| Never run validation yourself | All checks go through `runSubagent("validator")` |
| Never skip validation | Every builder task is followed by a validator |
| Never say "done" without proof | Final report includes actual command output |
| Max 2 fix cycles per task | Prevents infinite loops on unfixable problems |
| Rollback on exhausted cycles | Broken code is never left in the codebase |

---

## Pipeline 3: bug_to_pr

**File**: `.github/prompts/bug_to_pr.prompt.md`
**Purpose**: Take a bug description and produce a reviewed, merged GitHub PR — fully automated.
**Input**: A bug description from the user
**Output**: A merged PR with bug report, test evidence, and review verdicts attached.

This is the most complex pipeline — it orchestrates **7 different agents** across **6 phases**, embeds the full `build` protocol for fix execution, implements adversarial code review with isolation guarantees, and handles crash recovery.

### End-to-End Flow

```mermaid
flowchart TD
    subgraph "Phase 0: Setup"
        S1["Parse bug description"]
        S2["Generate BUG-ID"]
        S3["Create branch\nfix/bug-xxx"]
        S4["Write pipeline-state.json"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph "Phase 1: Triage"
        T1["🔍 bug-creator\ninvestigates & writes report"]
        T2["🧭 bug-router\nclassifies module"]
        T3["Write routing.json"]
        T1 --> T2 --> T3
    end

    subgraph "Phase 2: Fix"
        F1["🔧 bug-fixer-*\ncreates fix plan"]
        F2["🔨 builder × N\nexecutes tasks (TDD)"]
        F3["✅ validator × N\nverifies each task"]
        F4["Capture test evidence"]
        F1 --> F2
        F2 --> F3
        F3 -->|"fail"| F2
        F3 -->|"pass"| F4
    end

    subgraph "Phase 3: PR"
        P1["git add, commit, push"]
        P2["gh pr create"]
        P3["Post bug report\nas PR comment"]
        P1 --> P2 --> P3
    end

    subgraph "Phase 4: Adversarial Review"
        R1["⚖️ reviewer-alpha\n(independent)"]
        R2["⚖️ reviewer-beta\n(independent)"]
        R3["Write both reviews\n(only after BOTH complete)"]
        R4["Post verdicts\nto PR"]
        R1 --> R3
        R2 --> R3
        R3 --> R4
    end

    subgraph "Phase 5: Merge Gate"
        M1{"Both\nAPPROVE?"}
        M2["Ask user:\nMerge PR?"]
        M3["gh pr merge\n--delete-branch"]
        M4["Report rejection\nreasons"]
        M5{"Retry?\n(≤2 cycles)"}
        M1 -->|"Yes"| M2
        M2 -->|"Yes"| M3
        M2 -->|"No"| DONE
        M1 -->|"No"| M4
        M4 --> M5
        M5 -->|"Yes"| F1
        M5 -->|"No"| DONE
    end

    S4 --> T1
    T3 --> F1
    F4 --> P1
    P3 --> R1
    P3 --> R2
    R4 --> M1
    M3 --> DONE["📊 Pipeline Report"]

    style S1 fill:#4A90D9,color:#fff
    style DONE fill:#27AE60,color:#fff
    style R3 fill:#F39C12,color:#000
    style M1 fill:#F39C12,color:#000
```

### Phase Details

#### Phase 0 — Setup
Creates the bug directory (`bugs/BUG-XXX/`), a git branch (`fix/bug-xxx`), and initializes the pipeline state file for crash recovery.

#### Phase 1 — Triage
The **bug-creator** agent reads the codebase, attempts to reproduce the bug, and writes a JIRA-format report with 8 required sections. The **bug-router** agent (read-only) classifies which module owns the bug and which fixer agent should handle it.

#### Phase 2 — Fix (Nested Orchestration)
This is where the `plan_to_build` + `build` pipelines run *inside* the bug pipeline:

```mermaid
flowchart LR
    subgraph "Phase 2a: Planning"
        FIXER["bug-fixer-*\ncreates fix spec"]
    end

    subgraph "Phase 2b: Execution (inline build protocol)"
        LOOP["For each task in spec:"]
        BLD["builder executes\n(TDD)"]
        VAL["validator verifies"]
        FIX["fix cycle\n(max 2)"]
        LOOP --> BLD --> VAL
        VAL -->|"fail"| FIX --> BLD
        VAL -->|"pass"| LOOP
    end

    subgraph "Phase 2c: Evidence"
        TEST["Run module tests\ncapture output"]
    end

    FIXER --> LOOP
    LOOP -->|"all done"| TEST

    style FIXER fill:#2ECC71,color:#fff
    style TEST fill:#3498DB,color:#fff
```

#### Phase 3 — PR Creation
Commits all changes, pushes the branch, creates a GitHub PR via `gh` CLI, and posts the bug report as a PR comment.

#### Phase 4 — Adversarial Review (Isolation Protocol)

Two independent reviewers evaluate the fix against a **5-point checklist**:

1. Root cause addressed?
2. No regressions introduced?
3. Test evidence sufficient?
4. Edge cases covered?
5. Fix is minimal?

**The isolation guarantee**: Review files are written to disk **only after both reviewers complete**. When reviewer-alpha runs, beta's file doesn't exist on the filesystem (and vice versa). This is a structural guarantee, not just a prompt instruction.

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant A as Reviewer Alpha
    participant B as Reviewer Beta
    participant FS as Filesystem

    O->>A: Review the fix independently
    A-->>O: Verdict (held in memory)
    Note over O,FS: Alpha's file NOT written yet

    O->>B: Review the fix independently
    B-->>O: Verdict (held in memory)
    Note over O,FS: Beta's file NOT written yet

    O->>FS: Write alpha.md + beta.md
    Note over FS: Both files written simultaneously
    O->>FS: Post verdicts to PR
```

#### Phase 5 — Merge Gate
If both reviewers approve, the user is asked for final confirmation before merging. If either rejects, the pipeline can re-enter the fix phase with rejection feedback (up to 2 fix-review cycles total).

### Crash Recovery

The pipeline writes a `pipeline-state.json` checkpoint after each phase:

```json
{
  "bug_id": "BUG-001",
  "phase": "triage",
  "branch": "fix/bug-001",
  "fix_cycle": 0,
  "module": "frontend",
  "fixer_agent": "bug-fixer-frontend"
}
```

On resume, the orchestrator reads this file and skips completed phases. All filesystem artifacts (reports, plans, test results) survive crashes.

### Fix-Review Cycles

```mermaid
flowchart LR
    FIX1["Phase 2: Fix\n(cycle 1)"] --> PR1["Phase 3: PR"]
    PR1 --> REV1["Phase 4: Review"]
    REV1 -->|"APPROVE + APPROVE"| MERGE["Phase 5: Merge ✅"]
    REV1 -->|"Any REJECT"| FIX2["Phase 2: Re-fix\n(cycle 2, with feedback)"]
    FIX2 --> REV2["Phase 4: Re-review"]
    REV2 -->|"APPROVE + APPROVE"| MERGE
    REV2 -->|"Any REJECT"| STOP["Pipeline stops ❌\nAll reasons reported"]

    style MERGE fill:#27AE60,color:#fff
    style STOP fill:#E74C3C,color:#fff
```

---

## Agent Registry

All agents are defined in `.github/agents/` and share these traits:
- **Stateless**: Each invocation starts fresh — no memory of previous tasks.
- **Structured reports**: Every agent ends with a parseable status (`COMPLETED`/`FAILED` for builders, `PASS`/`FAIL` for validators).
- **Scoped**: Each agent has a defined purpose and stays within it.

| Agent | File | Type | Purpose |
|-------|------|------|---------|
| **builder** | `builder.agent.md` | Read-write | Implements one task with TDD. Writes tests first, then code. |
| **validator** | `validator.agent.md` | Read-only* | Verifies a task was completed. Runs commands, shows actual output. |
| **bug-creator** | `bug-creator.agent.md` | Read-write | Investigates bugs, writes JIRA-format reports (8 required sections). |
| **bug-router** | `bug-router.agent.md` | Read-only | Classifies which module owns a bug. Outputs JSON routing decision. |
| **bug-fixer-backend** | `bug-fixer-backend.agent.md` | Read-write | Creates fix plans for `backend/` bugs in `plan_to_build` format. |
| **bug-fixer-frontend** | `bug-fixer-frontend.agent.md` | Read-write | Creates fix plans for `frontend/src/` bugs in `plan_to_build` format. |
| **bug-reviewer** | `bug-reviewer.agent.md` | Read-only | Adversarial 5-point reviewer. Returns APPROVE or REJECT verdict. |

*\* Validator runs commands to check work but does not modify source files.*

### Module Registry

The module registry (`.github/bug-modules.json`) maps code areas to agents:

```json
{
  "modules": {
    "backend":  { "fixer": "bug-fixer-backend",  "paths": ["backend/"],       "test_command": "cd backend && pytest tests/ -v" },
    "frontend": { "fixer": "bug-fixer-frontend", "paths": ["frontend/src/"], "test_command": "cd frontend && npm test -- --run" }
  },
  "default_fixer": "bug-fixer-backend"
}
```

---

## Guardrails & Safety Nets

The system has multiple layers of automated protection. Some are system-enforced (hooks), others are protocol-enforced (prompt instructions + orchestrator discipline).

### Layer 1: postToolUse Hook (System-Enforced)

**File**: `.github/hooks/validators/post_tool_validator.py`
**Trigger**: Every file write by any agent.

```mermaid
flowchart TD
    WRITE["Agent writes a file"] --> CHECK{"File type?"}

    CHECK -->|".py"| RUFF["ruff check\n(Python lint)"]
    CHECK -->|".ts / .tsx"| TSC["tsc --noEmit\n(TypeScript typecheck)"]
    CHECK -->|"specs/*.md"| SPEC["Validate 7 required sections\n+ validator frequency"]
    CHECK -->|"bugs/*/report.md"| BUG["Validate 8 required sections"]
    CHECK -->|"other"| ALLOW["✅ Allow"]

    RUFF -->|"pass"| ALLOW
    RUFF -->|"fail"| BLOCK["🛑 Block write\n+ inject error context"]
    TSC -->|"pass"| ALLOW
    TSC -->|"fail"| BLOCK
    SPEC -->|"pass"| ALLOW
    SPEC -->|"fail"| BLOCK
    BUG -->|"pass"| ALLOW
    BUG -->|"fail"| BLOCK

    style BLOCK fill:#E74C3C,color:#fff
    style ALLOW fill:#27AE60,color:#fff
```

**What it catches:**
| Check | Trigger | Action on Failure |
|-------|---------|-------------------|
| Python lint | Any `.py` file write | Blocks write, shows ruff errors |
| TypeScript typecheck | Any `.ts`/`.tsx` file write | Blocks write, shows tsc errors |
| Spec section validation | Any `specs/*.md` write | Blocks if any of 7 sections missing |
| Spec validator frequency | `specs/*.md` with >5 builder tasks | Blocks if insufficient intermediate validators |
| Bug report validation | Any `bugs/*/report.md` write | Blocks if any of 8 sections missing |

### Layer 2: sessionStart Hook

**File**: `.github/hooks/setup.sh`
**Trigger**: Every new Copilot chat session.
**Action**: Installs Python and Node dependencies automatically. Agents never fail due to missing packages.

### Layer 3: Orchestrator Protocol (Prompt-Enforced)

| Rule | Enforced By | Pipeline |
|------|------------|----------|
| Orchestrator never writes code | Prompt instructions | build, bug_to_pr |
| Every builder task gets a validator | Prompt instructions | build, bug_to_pr |
| Max 2 fix cycles, then rollback | Prompt instructions | build, bug_to_pr |
| Review files written only after both reviewers complete | Structural design + prompt | bug_to_pr |
| `pipeline-state.json` updated after each phase | Prompt instructions | bug_to_pr |
| Working directory reset at start of each phase | Prompt instructions | bug_to_pr |
| User confirmation required before merge | `ask_questions` call | bug_to_pr |
| Checkpoint reports every 3 builder tasks | Prompt instructions | build, bug_to_pr |

### Layer 4: Spec Quality Rules (Plan-Time)

| Rule | Description |
|------|-------------|
| ≥50 words per task | One-line descriptions are forbidden |
| Design assertions | 2–3 structural test assertions per route/model/component task |
| Intermediate validators | Required when builder count > 5 |
| Self-audit before save | Count tasks, verify word counts, check validator frequency |
| Brainstorm gate | Non-trivial features require approach discussion before planning |

### Layer 5: instructions/ (Always-On)

**File**: `.github/instructions/team-orchestration.instructions.md`
**Scope**: Applies to all files in `specs/**/*.md`
**Effect**: Reinforces that spec files are planning-only — never write implementation code in a plan.

---

## File Map

```
.github/
├── agents/                          # Agent definitions
│   ├── builder.agent.md             # Implements tasks with TDD
│   ├── validator.agent.md           # Verifies task completion
│   ├── bug-creator.agent.md         # Writes bug reports
│   ├── bug-router.agent.md          # Classifies bug modules
│   ├── bug-fixer-backend.agent.md   # Plans backend fixes
│   ├── bug-fixer-frontend.agent.md  # Plans frontend fixes
│   └── bug-reviewer.agent.md        # Adversarial code reviewer
│
├── hooks/
│   ├── hooks.json                   # Hook configuration
│   ├── setup.sh                     # sessionStart: install deps
│   └── validators/
│       └── post_tool_validator.py   # postToolUse: lint, typecheck, section validation
│
├── instructions/
│   └── team-orchestration.instructions.md  # Always-on planning rules
│
├── prompts/
│   ├── plan_to_build.prompt.md      # Pipeline 1: planning
│   ├── build.prompt.md              # Pipeline 2: execution
│   └── bug_to_pr.prompt.md          # Pipeline 3: end-to-end bug fix
│
├── bug-modules.json                 # Module → agent mapping
└── copilot-instructions.md          # Global project conventions

specs/                               # Generated plan documents
bugs/                                # Generated bug artifacts
├── BUG-XXX/
│   ├── report.md                    # JIRA-format bug report
│   ├── routing.json                 # Module classification
│   ├── test-results.md              # Captured test output
│   ├── pipeline-state.json          # Crash recovery checkpoint
│   ├── verdict.json                 # Merge gate decision
│   └── reviews/
│       ├── alpha.md                 # Reviewer alpha verdict
│       └── beta.md                  # Reviewer beta verdict
```

---

## FAQ

### How do I use these pipelines?

In VS Code with Copilot Chat in **Agent mode**:

| To do this... | Type this... |
|---------------|-------------|
| Plan a feature | `/plan_to_build "add metric history endpoint"` |
| Execute a plan | `execute the plan in specs/add-metric-history.md` (uses build prompt) |
| Fix a bug end-to-end | `/bug_to_pr "alerts panel flickers when metrics refresh"` |

### Can agents talk to each other?

No. All sub-agents are stateless and communicate only with the orchestrator. The filesystem is their shared state — one agent's file writes are visible to the next agent dispatched.

### What happens if an agent fails?

The orchestrator handles it:
1. **Builder fails validation** → re-dispatched with failure context (up to 2 fix cycles)
2. **Fix cycles exhausted** → `git checkout` rollback, task skipped, pipeline continues
3. **Reviewer rejects** → pipeline can re-enter fix phase with feedback (up to 2 cycles)
4. **Pipeline crashes** → `pipeline-state.json` preserves progress; resume from last checkpoint

### Why two reviewers?

Adversarial review catches issues a single reviewer might miss. The isolation protocol ensures independent judgment — neither reviewer can see the other's verdict until both are done.

### What's the difference from Claude Code's version?

This system was ported from Claude Code slash commands. Key differences:

| Capability | Claude Code | Copilot |
|-----------|------------|---------|
| Agent communication | `SendMessage` (direct) | Orchestrator mediates all |
| Parallel execution | `run_in_background` | Sequential only |
| Tool restrictions | `disallowedTools` (system) | Prompt-enforced |
| Review isolation | `PreToolUse` hook (system) | Structural + prompt |
| Session persistence | Built-in resume | `pipeline-state.json` file |
| Sub-agent nesting | Agents call Skills | Orchestrator bridges |

The Copilot version achieves equivalent outcomes through different mechanisms — structural design and protocol discipline replace system-level enforcement.

### How do I add a new module?

1. Add an entry to `.github/bug-modules.json` with `fixer`, `paths`, and `test_command`
2. Create `.github/agents/bug-fixer-<module>.agent.md` following the existing fixer pattern
3. The bug-router will automatically include the new module in its classification
