# Copilot Agent Pipelines — Architecture & Design

> **Audience**: Engineers evaluating, extending, or debugging the agent pipeline system.
> Novice-friendly explanations with full technical depth for advanced users.

This document describes the four orchestration pipelines that power automated development in this repository. Each pipeline is a **prompt file** (`.github/prompts/*.prompt.md`) that turns GitHub Copilot's chat agent into a multi-agent orchestrator — dispatching specialized sub-agents to plan, build, validate, review, and deploy code changes.

---

## Table of Contents

- [System Overview](#system-overview)
- [Key Concepts](#key-concepts)
- [Pipeline 1: plan\_to\_build](#pipeline-1-plan_to_build)
- [Pipeline 2: build](#pipeline-2-build)
- [Pipeline 3: bug\_to\_pr](#pipeline-3-bug_to_pr)
- [Pipeline 4: pr\_to\_cicd](#pipeline-4-pr_to_cicd)
- [Agent Registry](#agent-registry)
- [Guardrails & Safety Nets](#guardrails--safety-nets)
- [Engineering Philosophy — Skills Embedded in Pipelines](#engineering-philosophy--skills-embedded-in-pipelines)
- [File Map](#file-map)
- [FAQ](#faq)

---

## System Overview

The system follows a **hub-and-spoke orchestration model**: the main Copilot chat agent acts as the orchestrator (hub), and stateless sub-agents (spokes) do the actual work. Sub-agents cannot talk to each other — all communication flows through the orchestrator.

```mermaid
graph TB
    User((User))

    subgraph "Copilot Chat Agent (Orchestrator)"
        PTB["/plan_to_build"]
        BUILD["/build"]
        BTP["/bug_to_pr"]
        PTC["/pr_to_cicd"]
    end

    subgraph "Sub-Agents (Stateless)"
        B["builder"]
        V["validator"]
        BC["bug-creator"]
        BR["bug-router"]
        BFB["bug-fixer-backend"]
        BFF["bug-fixer-frontend"]
        BFJ["bug-fixer-java"]
        BFG["bug-fixer-go"]
        REV["bug-reviewer"]
        DREV["deploy-reviewer"]
    end

    subgraph "Config"
        PROJ["project.json"]
    end

    subgraph "Adapters"
        CIA["ci-adapter.sh"]
        DEP["deploy-adapter.sh"]
    end

    subgraph "Guardrails"
        HOOK["postToolUse hook"]
        SESSION["sessionStart hook"]
    end

    subgraph "Artifacts"
        SPECS["specs/*.md"]
        BUGS["bugs/BUG-*/"]
        CIDEPLOY["ci-results/DEPLOY-*/"]
        PR["GitHub PR"]
    end

    User -->|"invoke"| PTB
    User -->|"invoke"| BUILD
    User -->|"invoke"| BTP
    User -->|"invoke"| PTC

    PTB -->|"produces"| SPECS
    BUILD -->|"reads"| SPECS
    BUILD -->|"dispatches"| B
    BUILD -->|"dispatches"| V
    BTP -->|"dispatches"| BC
    BTP -->|"dispatches"| BR
    BTP -->|"dispatches"| BFB
    BTP -->|"dispatches"| BFF
    BTP -->|"dispatches"| BFJ
    BTP -->|"dispatches"| BFG
    BTP -->|"dispatches"| B
    BTP -->|"dispatches"| V
    BTP -->|"dispatches"| REV
    BTP -->|"produces"| BUGS
    PTC -->|"dispatches"| DREV
    PTC -->|"calls"| CIA
    PTC -->|"calls"| DEP
    PTC -->|"produces"| CIDEPLOY

    B -->|"reads"| PROJ
    V -->|"reads"| PROJ
    HOOK -->|"reads"| PROJ
    CIA -->|"reads"| PROJ
    DEP -->|"reads"| PROJ
    BTP -->|"produces"| PR

    B -.->|"file writes trigger"| HOOK
    BFB -.->|"file writes trigger"| HOOK
    BFF -.->|"file writes trigger"| HOOK
    BC -.->|"file writes trigger"| HOOK

    style PTB fill:#4A90D9,color:#fff
    style BUILD fill:#7B68EE,color:#fff
    style BTP fill:#E74C3C,color:#fff
    style PTC fill:#16A085,color:#fff
    style HOOK fill:#F39C12,color:#000
```

### How It Works (Plain English)

1. **You describe what you want** — a feature, a bug fix, a deployment.
2. **A pipeline takes over** — it reads your request, dispatches specialized agents, validates their work, and produces artifacts (specs, code, PRs, deployment records).
3. **Each agent does one thing** — a builder writes code, a validator checks it, a reviewer judges it, an adapter talks to CI/CD. They never freelance.
4. **Guardrails catch mistakes** — hooks automatically lint Python, typecheck TypeScript, and validate document structure on every file write.
5. **Human gates protect production** — deployment and rollback always require explicit user confirmation.

---

## Key Concepts

| Concept              | What It Means                                                                                                                                                  |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Orchestrator**     | The main Copilot chat agent. It reads prompts, dispatches sub-agents via `runSubagent()`, and makes sequencing decisions. It never writes implementation code. |
| **Sub-Agent**        | A stateless agent (defined in `.github/agents/*.agent.md`) that receives a task, executes it, and returns a structured report. Cannot talk to other agents.    |
| **Prompt File**      | A `.prompt.md` file in `.github/prompts/` that defines a pipeline's behavior. Invoked via `/command` in Copilot Chat.                                          |
| **Spec File**        | A plan document in `specs/` that fully describes what to build, who builds it, and how to validate it. The bridge between planning and execution.              |
| **TDD Preamble**     | Instructions prepended to every builder dispatch: write a failing test first (RED), implement minimally (GREEN), then refactor.                                |
| **Fix Cycle**        | When a validator reports FAIL, the builder is re-dispatched with the failure context. Max 2 fix cycles per task before rollback.                               |
| **Rollback**         | If a task fails after 2 fix cycles, `git checkout` reverts its changes. Broken code never stays in the codebase.                                               |
| **postToolUse Hook** | A Python script that runs after every file write — lints `.py` files, typechecks `.ts/.tsx` files, and validates spec/report structure.                        |

---

## Pipeline 1: plan_to_build

**File**: `.github/prompts/plan_to_build.prompt.md`
**Purpose**: Turn a user's feature request into a detailed, agent-executable specification.
**Output**: `specs/<descriptive-name>.md`

This pipeline is **planning only** — it reads code, asks clarifying questions, and writes a spec document. It never modifies source code.

### Flow

```mermaid
flowchart LR
    A["User describes\nfeature/task"] --> B["Analyze\nRequirements"]
    B --> C["Explore Codebase\n(read, grep, search)"]
    C --> D{"Brainstorm?\n(feature/enhancement)"}
    D -->|"Yes"| E["Ask user:\nWhich approach?"]
    D -->|"Skip"| F["Design\nSolution"]
    E --> F
    F --> G{"Team\nComposition?"}
    G -->|"Medium/Complex"| H["Ask user:\nHow many builders?"]
    G -->|"Simple"| I["Single builder"]
    H --> I
    I --> J["Write tasks\n(50+ words each)"]
    J --> K["Self-Audit\n(counts & rules)"]
    K --> L["Save to\nspecs/*.md"]
    L --> M["Verify\n(file exists + 7 sections)"]
    M --> N["Spec Ready"]

    style A fill:#4A90D9,color:#fff
    style N fill:#27AE60,color:#fff
    style K fill:#F39C12,color:#000
    style M fill:#F39C12,color:#000
```

### What the Spec Contains

Every spec has **7 required sections** (enforced by the postToolUse hook):

| Section                  | Purpose                                           |
| ------------------------ | ------------------------------------------------- |
| `## Task Description`    | What needs to be done and why                     |
| `## Objective`           | Measurable definition of "done"                   |
| `## Relevant Files`      | Exact file paths involved                         |
| `## Step by Step Tasks`  | Ordered tasks with IDs, dependencies, assignments |
| `## Acceptance Criteria` | Specific, verifiable outcomes                     |
| `## Team Orchestration`  | Team composition and execution model              |
| `### Team Members`       | Named builders and validators with roles          |

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
    START["Read spec from\nspecs/*.md"] --> PARSE["Parse tasks,\ndeps, team"]
    PARSE --> TODO["Create todo list"]
    TODO --> NEXT{"Next task?"}

    NEXT -->|"builder task"| DISPATCH_B["Dispatch builder\n(with TDD preamble)"]
    NEXT -->|"validator task\n(final)"| DISPATCH_V_FINAL["Dispatch validator\n(full acceptance criteria)"]
    NEXT -->|"no more tasks"| REPORT["Build Report"]

    DISPATCH_B --> CHECK_B{"Builder status?"}
    CHECK_B -->|"COMPLETED"| DISPATCH_V["Dispatch validator\n(verify task)"]
    CHECK_B -->|"FAILED"| DISPATCH_V

    DISPATCH_V --> CHECK_V{"Validator status?"}
    CHECK_V -->|"PASS"| MARK_DONE["Mark task done"]
    CHECK_V -->|"FAIL"| FIX_CHECK{"Fix cycle <= 2?"}

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
    V-->>O: Status: FAIL

    Note over O: Fix cycle 1 of 2

    O->>B: Fix context + failure details
    B-->>O: Status: COMPLETED
    O->>V: Re-verify
    V-->>O: Status: PASS

    Note over O: Task complete
```

If the validator still reports FAIL after 2 fix cycles:

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant B as Builder
    participant V as Validator

    Note over O: Fix cycle 2 FAILED

    O->>B: ROLLBACK - git checkout files
    B-->>O: Rolled back

    Note over O: Task marked "ROLLED BACK"<br/>Continue to next task
```

### Checkpoints

After every 3 builder tasks, the orchestrator pauses and reports progress. This gives the user visibility and a chance to course-correct.

### Orchestrator Rules

| Rule                           | Why                                              |
| ------------------------------ | ------------------------------------------------ |
| Never implement code yourself  | All code goes through `runSubagent("builder")`   |
| Never run validation yourself  | All checks go through `runSubagent("validator")` |
| Never skip validation          | Every builder task is followed by a validator    |
| Never say "done" without proof | Final report includes actual command output      |
| Max 2 fix cycles per task      | Prevents infinite loops on unfixable problems    |
| Rollback on exhausted cycles   | Broken code is never left in the codebase        |

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
        T1["bug-creator\ninvestigates and writes report"]
        T2["bug-router\nclassifies module"]
        T3["Write routing.json"]
        T1 --> T2 --> T3
    end

    subgraph "Phase 2: Fix"
        F1["bug-fixer-*\ncreates fix plan"]
        F2["builder x N\nexecutes tasks (TDD)"]
        F3["validator x N\nverifies each task"]
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
        R1["reviewer-alpha\n(independent)"]
        R2["reviewer-beta\n(independent)"]
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
        M5{"Retry?\n(max 2 cycles)"}
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
    M3 --> DONE["Pipeline Report"]

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
    REV1 -->|"APPROVE + APPROVE"| MERGE["Phase 5: Merge"]
    REV1 -->|"Any REJECT"| FIX2["Phase 2: Re-fix\n(cycle 2, with feedback)"]
    FIX2 --> REV2["Phase 4: Re-review"]
    REV2 -->|"APPROVE + APPROVE"| MERGE
    REV2 -->|"Any REJECT"| STOP["Pipeline stops\nAll reasons reported"]

    style MERGE fill:#27AE60,color:#fff
    style STOP fill:#E74C3C,color:#fff
```

---

## Pipeline 4: pr_to_cicd

**File**: `.github/prompts/pr_to_cicd.prompt.md`
**Purpose**: Promote a merged PR through CI verification, adversarial review, deployment, and post-deploy health checks.
**Input**: A PR number (and optional target environment)
**Output**: A deployed release with CI logs, review verdicts, health check records, and a deployment report — all posted to the PR.

This pipeline completes the development lifecycle. Where `bug_to_pr` ends at a merged PR, `pr_to_cicd` picks up and carries it through to production. It uses **adapter scripts** to stay provider-agnostic — swap Jenkins for GitHub Actions or Spinnaker for ArgoCD by editing one shell script.

### End-to-End Flow

```mermaid
flowchart TD
    subgraph "Phase 0: Setup"
        S1["Verify PR is merged"]
        S2["Generate DEPLOY-ID"]
        S3["Check adapter scripts"]
        S4["Verify auth + config"]
        S1 --> S2 --> S3 --> S4
    end

    subgraph "Phase 1: CI Verification"
        C1["ci-adapter.sh trigger"]
        C2["Poll status\n(30 iterations x 30s)"]
        C3["Capture CI logs"]
        C1 --> C2 --> C3
    end

    subgraph "Phase 2: Adversarial CI Review"
        R1["deploy-reviewer\n(alpha)"]
        R2["deploy-reviewer\n(beta)"]
        R3["Write both reviews\n(only after BOTH complete)"]
        R4["Post verdicts to PR"]
        R1 --> R3
        R2 --> R3
        R3 --> R4
    end

    subgraph "Phase 3: Deploy Gate"
        D1{"Both\nAPPROVE?"}
        D2["Ask user:\nDeploy?"]
        D3["deploy-adapter.sh trigger"]
        D4["Poll status\n(60 iterations x 30s)"]
        D5["Capture deploy logs"]
        D1 -->|"Yes"| D2
        D2 -->|"Yes"| D3
        D3 --> D4 --> D5
        D1 -->|"No"| RETRY{"Retry?\n(max 2 cycles)"}
        RETRY -->|"Yes"| C1
        RETRY -->|"No"| DONE
    end

    subgraph "Phase 4: Post-Deploy Verification"
        H1["Health checks\n(every 10s for 60s)"]
        H2["deploy-reviewer\n(post-deploy)"]
        H3{"Verdict?"}
        H4["Ask user:\nRollback?"]
        H1 --> H2 --> H3
        H3 -->|"APPROVE"| DONE
        H3 -->|"REJECT"| H4
        H4 -->|"Yes"| RB["deploy-adapter.sh\nrollback"]
        H4 -->|"No"| DONE
    end

    subgraph "Phase 5: Report"
        RPT["Commit artefacts\nPost summary to PR"]
    end

    S4 --> C1
    C3 --> R1
    C3 --> R2
    R4 --> D1
    D5 --> H1
    RB --> DONE
    RPT --> DONE["Pipeline Complete"]

    style S1 fill:#16A085,color:#fff
    style DONE fill:#27AE60,color:#fff
    style R3 fill:#F39C12,color:#000
    style D1 fill:#F39C12,color:#000
    style H3 fill:#F39C12,color:#000
```

### Adapter Architecture

The pipeline never calls Jenkins or Spinnaker directly. Instead, it calls **adapter scripts** that abstract the CI/CD provider:

```mermaid
flowchart LR
    subgraph "Pipeline (provider-agnostic)"
        ORC["pr_to_cicd\norchestrator"]
    end

    subgraph "Adapters (.github/adapters/)"
        CI["ci-adapter.sh\ntrigger | status | logs"]
        DEP["deploy-adapter.sh\ntrigger | status | logs | rollback"]
    end

    subgraph "Providers (swappable)"
        J["Jenkins"]
        GHA["GitHub Actions"]
        S["Spinnaker"]
        ARGO["ArgoCD"]
    end

    ORC --> CI
    ORC --> DEP
    CI -.->|"stub / curl / MCP"| J
    CI -.->|"replace adapter"| GHA
    DEP -.->|"stub / curl / MCP"| S
    DEP -.->|"replace adapter"| ARGO

    style ORC fill:#16A085,color:#fff
    style CI fill:#3498DB,color:#fff
    style DEP fill:#3498DB,color:#fff
```

Each adapter supports three modes, detected automatically from `project.json`:

| Mode     | When                                         | Behavior                              |
| -------- | -------------------------------------------- | ------------------------------------- |
| **stub** | No CI/deploy URLs configured (default)       | Returns mock data for dry-run testing |
| **curl** | `ci.job_url` or `deploy.pipeline_url` is set | Calls REST API directly               |
| **MCP**  | `mcp_servers.jenkins` or `.spinnaker` is set | Uses MCP tools (falls back to curl)   |

### Phase Details

#### Phase 0 — Setup
Verifies the PR is actually merged, generates a `DEPLOY-NNN` ID, checks that adapter scripts exist and are executable, and validates configuration in `project.json`.

#### Phase 1 — CI Verification
Triggers a CI build via `ci-adapter.sh trigger`, polls `ci-adapter.sh status` every 30 seconds (max 15 minutes), and captures the full build log. A failing CI build is a **hard stop** — the pipeline will not proceed to deployment.

#### Phase 2 — Adversarial CI Review
Same isolation protocol as `bug_to_pr`. Two independent `deploy-reviewer` agents evaluate the CI build against a 5-point checklist (tests passed, no errors, no risk warnings, artefacts produced, no security scan failures). Verdicts are held in memory until both complete, then written simultaneously.

#### Phase 3 — Deploy Gate
If both reviewers approve, the user is **always asked for confirmation** before deployment. The pipeline triggers `deploy-adapter.sh trigger`, polls status (max 30 minutes), and captures deploy logs. If deployment fails, the user is asked whether to rollback (never automatic).

#### Phase 4 — Post-Deploy Verification
Runs health checks with exponential backoff (every 10s for 60s), then dispatches a post-deploy reviewer to evaluate deployment logs and health check results. If the reviewer rejects, the user is asked about rollback.

#### Phase 5 — Report
Commits all artefacts to `ci-results/DEPLOY-NNN/`, posts a comprehensive summary to the PR, and presents a final report to the user.

### Deploy-Review Cycles

The pipeline allows **maximum 2 deploy-review cycles**:

```mermaid
flowchart LR
    CI1["Phase 1: CI\n(cycle 1)"] --> REV1["Phase 2: Review"]
    REV1 -->|"APPROVE + APPROVE"| DEP1["Phase 3: Deploy"]
    DEP1 --> HEALTH["Phase 4: Health"]
    HEALTH --> DONE["Phase 5: Report"]
    REV1 -->|"Any REJECT"| CI2["Phase 1: Re-CI\n(cycle 2)"]
    CI2 --> REV2["Phase 2: Re-review"]
    REV2 -->|"APPROVE + APPROVE"| DEP1
    REV2 -->|"Any REJECT"| STOP["Pipeline stops\nAll reasons reported"]

    style DONE fill:#27AE60,color:#fff
    style STOP fill:#E74C3C,color:#fff
```

User can override a review rejection by choosing "Deploy anyway" in Phase 3. Overrides are recorded in the pipeline state and noted in the final report.

### Human Gates

Every destructive action requires explicit user confirmation:

| Action                   | Gate                                         |
| ------------------------ | -------------------------------------------- |
| Trigger deployment       | `ask_questions`: "Deploy PR #N to env?"      |
| Rollback after failure   | `ask_questions`: "Trigger rollback?"         |
| Override reviewer reject | `ask_questions`: "Deploy anyway (override)?" |

The pipeline **never** auto-deploys or auto-rollbacks.

### Crash Recovery

Same pattern as `bug_to_pr` — a `pipeline-state.json` checkpoint is written after every phase:

```json
{
  "deploy_id": "DEPLOY-001",
  "phase": "ci_review",
  "pr_number": 5,
  "commit_sha": "abc1234",
  "environment": "production",
  "build_id": "STUB-BUILD-123",
  "ci_status": "SUCCESS",
  "alpha_verdict": "APPROVE",
  "beta_verdict": "APPROVE",
  "deploy_cycle": 0
}
```

On resume, the orchestrator reads this file and skips completed phases.

---

## Agent Registry

All agents are defined in `.github/agents/` and share these traits:
- **Stateless**: Each invocation starts fresh — no memory of previous tasks.
- **Structured reports**: Every agent ends with a parseable status (`COMPLETED`/`FAILED` for builders, `PASS`/`FAIL` for validators).
- **Scoped**: Each agent has a defined purpose and stays within it.

| Agent                  | File                          | Type       | Purpose                                                                |
| ---------------------- | ----------------------------- | ---------- | ---------------------------------------------------------------------- |
| **builder**            | `builder.agent.md`            | Read-write | Implements one task with TDD. Writes tests first, then code.           |
| **validator**          | `validator.agent.md`          | Read-only* | Verifies a task was completed. Runs commands, shows actual output.     |
| **bug-creator**        | `bug-creator.agent.md`        | Read-write | Investigates bugs, writes JIRA-format reports (8 required sections).   |
| **bug-router**         | `bug-router.agent.md`         | Read-only  | Classifies which module owns a bug. Outputs JSON routing decision.     |
| **bug-fixer-backend**  | `bug-fixer-backend.agent.md`  | Read-write | Creates fix plans for backend bugs in `plan_to_build` format.          |
| **bug-fixer-frontend** | `bug-fixer-frontend.agent.md` | Read-write | Creates fix plans for frontend bugs in `plan_to_build` format.         |
| **bug-fixer-java**     | `bug-fixer-java.agent.md`     | Read-write | Creates fix plans for Java bugs in `plan_to_build` format.             |
| **bug-fixer-go**       | `bug-fixer-go.agent.md`       | Read-write | Creates fix plans for Go bugs in `plan_to_build` format.               |
| **bug-reviewer**       | `bug-reviewer.agent.md`       | Read-only  | Adversarial 5-point reviewer. Returns APPROVE or REJECT verdict.       |
| **deploy-reviewer**    | `deploy-reviewer.agent.md`    | Read-only  | Adversarial CI/deploy reviewer with 3 roles: alpha, beta, post-deploy. |

*\* Validator runs commands to check work but does not modify source files.*

### Module Registry

The project config (`.github/project.json`) is the single source of truth.
The module registry (`.github/bug-modules.json`) is a derived routing view.

All agents and `post_tool_validator.py` read from `project.json` at runtime:

```json
{
  "name": "aigile",
  "modules": {
    "backend":  { "tech": "Python / FastAPI",    "paths": ["backend/"],         "test": "cd backend && pytest tests/ -v",  "lint": "cd backend && ruff check .",     "fixer_agent": "bug-fixer-backend" },
    "frontend": { "tech": "TypeScript / React",   "paths": ["frontend/src/"],    "test": "cd frontend && npm test -- --run", "lint": "cd frontend && npm run lint",   "fixer_agent": "bug-fixer-frontend" },
    "java":     { "tech": "Java / Spring Boot",   "paths": ["java-service/src/"], "test": "cd java-service && ./mvnw test",   "lint": "cd java-service && ./mvnw checkstyle:check", "fixer_agent": "bug-fixer-java" },
    "go":       { "tech": "Go",                   "paths": ["go-service/"],       "test": "cd go-service && go test ./...",   "lint": "cd go-service && golangci-lint run",          "fixer_agent": "bug-fixer-go" }
  },
  "ci": { "provider": "jenkins", "job_url": "", "auth_env": "JENKINS_TOKEN" },
  "deploy": { "provider": "spinnaker", "pipeline_url": "", "application": "", "pipeline_name": "", "auth_env": "SPINNAKER_TOKEN", "health_check_url": "http://localhost:8000/health" },
  "mcp_servers": {},
  "default_fixer": "bug-fixer-backend"
}
```

The `ci`, `deploy`, and `mcp_servers` blocks are used by the adapter scripts (`.github/adapters/`) and the `pr_to_cicd` pipeline. Leave URLs empty for stub mode.

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
    CHECK -->|"other"| ALLOW["Allow"]

    RUFF -->|"pass"| ALLOW
    RUFF -->|"fail"| BLOCK["BLOCK write\n+ inject error context"]
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
| Check                    | Trigger                            | Action on Failure                              |
| ------------------------ | ---------------------------------- | ---------------------------------------------- |
| Python lint              | Any `.py` file write               | Blocks write, shows ruff errors                |
| TypeScript typecheck     | Any `.ts`/`.tsx` file write        | Blocks write, shows tsc errors                 |
| Spec section validation  | Any `specs/*.md` write             | Blocks if any of 7 sections missing            |
| Spec validator frequency | `specs/*.md` with >5 builder tasks | Blocks if insufficient intermediate validators |
| Bug report validation    | Any `bugs/*/report.md` write       | Blocks if any of 8 sections missing            |

### Layer 2: sessionStart Hook

**File**: `.github/hooks/setup.sh`
**Trigger**: Every new Copilot chat session.
**Action**: Installs Python and Node dependencies automatically. Agents never fail due to missing packages.

### Layer 3: Orchestrator Protocol (Prompt-Enforced)

| Rule                                                    | Enforced By                | Pipeline         |
| ------------------------------------------------------- | -------------------------- | ---------------- |
| Orchestrator never writes code                          | Prompt instructions        | build, bug_to_pr |
| Every builder task gets a validator                     | Prompt instructions        | build, bug_to_pr |
| Max 2 fix cycles, then rollback                         | Prompt instructions        | build, bug_to_pr |
| Review files written only after both reviewers complete | Structural design + prompt | bug_to_pr        |
| `pipeline-state.json` updated after each phase          | Prompt instructions        | bug_to_pr        |
| Working directory reset at start of each phase          | Prompt instructions        | bug_to_pr        |
| User confirmation required before merge                 | `ask_questions` call       | bug_to_pr        |
| User confirmation required before deploy and rollback   | `ask_questions` call       | pr_to_cicd       |
| CI review files written only after both reviewers done  | Structural design + prompt | pr_to_cicd       |
| All CI/CD calls go through adapter scripts              | Prompt instructions        | pr_to_cicd       |
| Never auto-rollback                                     | Prompt instructions        | pr_to_cicd       |
| Max 2 deploy-review cycles                              | Prompt instructions        | pr_to_cicd       |
| Health checks with backoff (10s intervals, 60s total)   | Prompt instructions        | pr_to_cicd       |
| Checkpoint reports every 3 builder tasks                | Prompt instructions        | build, bug_to_pr |

### Layer 4: Spec Quality Rules (Plan-Time)

| Rule                    | Description                                                      |
| ----------------------- | ---------------------------------------------------------------- |
| ≥50 words per task      | One-line descriptions are forbidden                              |
| Design assertions       | 2–3 structural test assertions per route/model/component task    |
| Intermediate validators | Required when builder count > 5                                  |
| Self-audit before save  | Count tasks, verify word counts, check validator frequency       |
| Brainstorm gate         | Non-trivial features require approach discussion before planning |

### Layer 5: instructions/ (Always-On)

**File**: `.github/instructions/team-orchestration.instructions.md`
**Scope**: Applies to all files in `specs/**/*.md`
**Effect**: Reinforces that spec files are planning-only — never write implementation code in a plan.

---

## Engineering Philosophy — Skills Embedded in Pipelines

The pipelines aren't ad-hoc automation. They encode the team's **engineering skills** (`.github/skills/`) directly into agent behavior. Each skill defines a philosophy (mandatory practices, forbidden anti-patterns) — and those rules are baked into the prompts and agents as concrete, enforceable instructions.

This means agents don't just "write code" — they follow the same engineering standards a senior engineer would, automatically.

### Skill → Pipeline Mapping

| Skill                              | Embedded In                                                              | Key Rules Extracted                                                               |
| ---------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **brainstorming**                  | `plan_to_build` prompt — "Prerequisite: Explore Before Planning" section | One question at a time, multiple-choice preferred, skip table for trivial tasks   |
| **writing-plans**                  | `plan_to_build` prompt — "Task Quality Rules" section                    | ≥50 word descriptions, 2–5 min task size, design assertions, self-audit checklist |
| **plan-reviewer**                  | `plan_to_build` prompt — Workflow step 8 "Self-Review"                   | Gap analysis: missing deps, risky areas, edge cases, rollback paths               |
| **test-driven-development**        | `builder` agent + `build` prompt builder preamble                        | RED-GREEN-REFACTOR cycle, test-first is mandatory, skip table for config          |
| **terminal-discipline**            | `builder` agent                                                          | No interrupting running commands, note long durations, read full output           |
| **systematic-debugging**           | `builder` agent + `build` prompt fix cycle dispatch                      | 4-phase: reproduce → isolate → root cause → fix. No random changes.               |
| **verification-before-completion** | `validator` agent + `build` prompt report section                        | Never say PASS without actual output, paste real command results                  |
| **safe-rollback**                  | `build` prompt — exhausted fix cycle handler                             | `git checkout` rollback when 2 fix cycles fail, verify with `git diff`            |
| **executing-plans**                | `build` prompt — batch checkpoints                                       | Pause every 3 tasks, report progress, give user a chance to course-correct        |
| **code-refactoring**               | `plan_to_build` prompt — task splitting rules                            | "Too Big" test: >2 files or >20 lines = split it                                  |
| **requesting-code-review**         | `bug_to_pr` prompt — Phase 4 adversarial review                          | Independent dual reviewers, 5-point checklist, structural isolation               |
| **finishing-a-development-branch** | `bug_to_pr` prompt — Phase 5 merge gate                                  | User confirmation before merge, clean branch deletion                             |

### How This Works in Practice

```mermaid
graph LR
    subgraph "Skills (Philosophy)"
        S1["test-driven-development\nRED - GREEN - REFACTOR"]
        S2["systematic-debugging\nreproduce - isolate - root cause - fix"]
        S3["writing-plans\n50+ words, design assertions"]
        S4["verification-before-completion\nproof, not promises"]
    end

    subgraph "Pipelines (Enforcement)"
        P1["builder agent\nTDD preamble"]
        P2["build prompt\nfix cycle dispatch"]
        P3["plan_to_build prompt\nTask Quality Rules"]
        P4["validator agent\nshow actual output"]
    end

    S1 -->|"extracted into"| P1
    S2 -->|"extracted into"| P2
    S3 -->|"extracted into"| P3
    S4 -->|"extracted into"| P4

    style S1 fill:#3498DB,color:#fff
    style S2 fill:#3498DB,color:#fff
    style S3 fill:#3498DB,color:#fff
    style S4 fill:#3498DB,color:#fff
    style P1 fill:#2ECC71,color:#fff
    style P2 fill:#2ECC71,color:#fff
    style P3 fill:#2ECC71,color:#fff
    style P4 fill:#2ECC71,color:#fff
```

The skills directory contains ~30 skills covering everything from Rust database architecture to Playwright automation. Not all apply to this project — but the ones that do are **compiled into** the pipeline prompts and agent instructions, turning philosophy into automated enforcement.

---

## File Map

```
.github/
├── project.json                     # Single source of truth for project config
│                                    # (modules, paths, tech stacks, commands)
├── agents/                          # Agent definitions
│   ├── builder.agent.md             # Implements tasks with TDD
│   ├── validator.agent.md           # Verifies task completion
│   ├── bug-creator.agent.md         # Writes bug reports
│   ├── bug-router.agent.md          # Classifies bug modules
│   ├── bug-fixer-backend.agent.md   # Plans backend fixes
│   ├── bug-fixer-frontend.agent.md  # Plans frontend fixes
│   ├── bug-fixer-java.agent.md      # Plans Java fixes
│   ├── bug-fixer-go.agent.md        # Plans Go fixes
│   ├── bug-reviewer.agent.md        # Adversarial code reviewer
│   └── deploy-reviewer.agent.md     # Adversarial CI/deploy reviewer (3 roles)
│
├── adapters/                        # Provider-agnostic CI/CD interface
│   ├── ci-adapter.sh                # Jenkins stub/curl/MCP (trigger, status, logs)
│   └── deploy-adapter.sh            # Spinnaker stub/curl/MCP (trigger, status, logs, rollback)
│
├── hooks/
│   ├── hooks.json                   # Hook configuration
│   ├── setup.sh                     # sessionStart: install deps
│   └── validators/
│       └── post_tool_validator.py   # postToolUse: lint, typecheck, section validation
│                                    # (reads project.json for commands)
│
├── instructions/
│   └── team-orchestration.instructions.md  # Always-on planning rules
│
├── prompts/
│   ├── plan_to_build.prompt.md      # Pipeline 1: planning
│   ├── build.prompt.md              # Pipeline 2: execution
│   ├── bug_to_pr.prompt.md          # Pipeline 3: end-to-end bug fix
│   └── pr_to_cicd.prompt.md         # Pipeline 4: CI/CD deployment
│
├── bug-modules.json                 # Module -> agent routing (derived from project.json)
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
ci-results/                          # Generated deployment artifacts
└── DEPLOY-NNN/
    ├── jenkins.log                  # CI build log
    ├── ci-summary.md                # Extracted CI summary for reviewers
    ├── spinnaker.log                # Deployment execution log
    ├── health-check.md              # Health check results
    ├── pipeline-state.json          # Crash recovery checkpoint
    └── reviews/
        ├── alpha.md                 # CI reviewer alpha verdict
        ├── beta.md                  # CI reviewer beta verdict
        └── post-deploy.md           # Post-deploy reviewer verdict
```

---

## FAQ

### How do I use these pipelines?

In VS Code with Copilot Chat in **Agent mode**:

| To do this...          | Type this...                                                          |
| ---------------------- | --------------------------------------------------------------------- |
| Plan a feature         | `/plan_to_build "add metric history endpoint"`                        |
| Execute a plan         | `execute the plan in specs/add-metric-history.md` (uses build prompt) |
| Fix a bug end-to-end   | `/bug_to_pr "alerts panel flickers when metrics refresh"`             |
| Deploy a merged PR     | `/pr_to_cicd PR #5`                                                   |
| Deploy to specific env | `/pr_to_cicd PR #5 to staging`                                        |

### Can agents talk to each other?

No. All sub-agents are stateless and communicate only with the orchestrator. The filesystem is their shared state — one agent's file writes are visible to the next agent dispatched.

### What happens if an agent fails?

The orchestrator handles it:
1. **Builder fails validation** → re-dispatched with failure context (up to 2 fix cycles)
2. **Fix cycles exhausted** → `git checkout` rollback, task skipped, pipeline continues
3. **Reviewer rejects** → pipeline can re-enter fix phase with feedback (up to 2 cycles)
4. **Pipeline crashes** → `pipeline-state.json` preserves progress; resume from last checkpoint
5. **CI build fails** → hard stop in `pr_to_cicd`; pipeline will not proceed to deployment
6. **Deployment fails** → user is asked whether to rollback (never automatic)

### Why two reviewers?

Adversarial review catches issues a single reviewer might miss. The isolation protocol ensures independent judgment — neither reviewer can see the other's verdict until both are done.

### What's the difference from Claude Code's version?

This system was ported from Claude Code slash commands. Key differences:

| Capability          | Claude Code                | Copilot                    |
| ------------------- | -------------------------- | -------------------------- |
| Agent communication | `SendMessage` (direct)     | Orchestrator mediates all  |
| Parallel execution  | `run_in_background`        | Sequential only            |
| Tool restrictions   | `disallowedTools` (system) | Prompt-enforced            |
| Review isolation    | `PreToolUse` hook (system) | Structural + prompt        |
| Session persistence | Built-in resume            | `pipeline-state.json` file |
| Sub-agent nesting   | Agents call Skills         | Orchestrator bridges       |

The Copilot version achieves equivalent outcomes through different mechanisms — structural design and protocol discipline replace system-level enforcement.

### How do I add a new module?

1. Add an entry to `.github/project.json` under `modules` with `tech`, `paths`, `test`, `lint`, and `fixer_agent`
2. Add a matching entry to `.github/bug-modules.json` (or keep it in sync with project.json)
3. Create `.github/agents/bug-fixer-<module>.agent.md` following the existing fixer pattern
4. The bug-router, builder, validator, and post_tool_validator.py all read from `project.json` automatically

### How do I adapt these pipelines to a completely different project?

Edit **one file**: `.github/project.json`. It is the single source of truth for:
- Module names and tech stacks
- Directory paths
- Run, test, lint, format, and typecheck commands per module
- Fixer agent mapping

All agents, prompts, and hooks read from `project.json` at runtime.
No hardcoded tech stack names, directory paths, or tool commands exist in the pipeline files.

If your project has modules not covered by the existing fixer agents (backend, frontend, java, go),
create a new `bug-fixer-<module>.agent.md` following the existing pattern and add the module to both
`project.json` and `bug-modules.json`.

### How do I connect real CI/CD systems?

The `pr_to_cicd` pipeline runs in **stub mode** by default — no external services needed. To connect real systems:

1. **Jenkins**: Set `ci.job_url` in `.github/project.json` to your Jenkins job URL. Set `JENKINS_TOKEN` env var.
2. **Spinnaker**: Set `deploy.pipeline_url`, `deploy.application`, and `deploy.pipeline_name`. Set `SPINNAKER_TOKEN` env var.
3. **Other providers**: Replace `.github/adapters/ci-adapter.sh` or `deploy-adapter.sh` with your own implementation. The adapter contract is simple — `trigger`, `status`, `logs` (and `rollback` for deploy).

The pipeline prompt is provider-agnostic. Only the adapter scripts know about specific CI/CD tools.
