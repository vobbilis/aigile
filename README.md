# Metrics Dashboard

A full-stack metrics dashboard testbed for GitHub Copilot coding agent workflows.

**Stack:** React + TypeScript (frontend) · FastAPI Python (backend)

---

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the frontend proxies API calls to port 8000.

---

## Testing Copilot Coding Agent — Step by Step

### Prerequisites

**GitHub repo settings** (Settings → Copilot):
- ✅ Enable Copilot coding agent for this repo
- ✅ Allow Copilot to create and approve pull requests

**GitHub Actions settings** (Settings → Actions → General):
- ✅ Allow GitHub Actions to create and approve pull requests

**VS Code settings** (`.vscode/settings.json` — already configured):
- `chat.agent.enabled: true`
- `chat.hooks.enabled: true`
- `chat.useAgentSkills: true`
- `chat.customAgentInSubagent.enabled: true`

---

### Test 1: VS Code Copilot (interactive, local)

1. Open this repo in VS Code
2. Open Copilot Chat → switch to **Agent mode** (not Chat mode)
3. Type `/plan_to_build` — verify it appears as a command
4. Run: `/plan_to_build "add a sparkline chart component to MetricCard showing last 10 values"`
5. Verify a `specs/` file is created
6. Tell Copilot: `execute the plan in specs/<filename>.md`
7. Verify builder + validator subagents run sequentially
8. Verify hooks fire — check post_tool_validator.py runs on file writes

**What to observe:**
- Subagents are sequential (builder → validator → builder → validator)
- No peer messaging between subagents
- Hooks run silently after each file write

---

### Test 2: GitHub Copilot Coding Agent (async, cloud)

1. Push this repo to GitHub
2. Verify `.github/workflows/copilot-setup-steps.yml` passes in Actions
3. Open a new GitHub Issue:
   ```
   Title: Add metric history endpoint
   Body: Add GET /metrics/{name}/history that returns the last N values
         for a metric. Default N=10, configurable via query param.
         Include tests.
   ```
4. Assign the issue to **Copilot** (right sidebar → Assignees → @copilot)
5. Wait 2–5 minutes → a PR should appear

**What to observe:**
- Copilot spins up in GitHub Actions (watch the Actions tab)
- Copilot opens a draft PR
- You see **"Approve and run workflows"** button — this is the mandatory human CI gate
- Click it to approve CI
- CI runs backend tests + frontend typecheck
- If CI passes → review and merge

**The seam to notice:**
When you click "Approve and run workflows" you are manually bridging
the seam between the async cloud agent and the CI system.
This cannot be automated — it is a GitHub security policy.

---

### Test 3: Failure Recovery (the interesting one)

1. Open an issue that will intentionally cause a CI failure:
   ```
   Title: Add metric aggregation endpoint
   Body: Add GET /metrics/aggregate that returns min/max/avg per metric name.
         The response shape must be: { name: str, min: float, max: float, avg: float }
         Tests must cover empty state, single value, and multiple values.
   ```
2. Assign to @copilot
3. When the PR appears, **do not** approve CI immediately
4. Read the PR diff — note what Copilot produced
5. Approve CI — watch if it passes or fails
6. **If CI fails:** notice that Copilot leaves a comment but does NOT automatically
   re-trigger. You must either:
   - Comment `@copilot fix the failing tests` to start a new cloud session
   - OR check out the branch locally and run Claude Code to fix:
     ```bash
     git checkout copilot/issue-N
     # in VS Code: tell Copilot/Claude Code to fix the CI failure
     ```

This is the cross-platform seam in action.

---

### Test 4: Bug-to-PR Pipeline (the star of the show)

The `/bug_to_pr` pipeline takes a plain-English bug description and fully automates the fix lifecycle — from investigation to merged PR — orchestrating 7 agents across 6 phases.

1. Open this repo in VS Code, Copilot Chat in **Agent mode**
2. Run:
   ```
   /bug_to_pr "the alerts panel polling interval conflicts with the metrics polling interval, causing UI flicker"
   ```
3. Watch the pipeline unfold:

| Phase | What Happens | Agent(s) |
|-------|-------------|----------|
| **0. Setup** | Creates `bugs/BUG-XXX/`, branch `fix/bug-xxx`, initializes state checkpoint | — |
| **1. Triage** | Investigates bug, writes JIRA-format report, classifies module | `bug-creator`, `bug-router` |
| **2. Fix** | Creates fix plan, executes with TDD (builder+validator per task) | `bug-fixer-*`, `builder`, `validator` |
| **3. PR** | Commits, pushes, creates GitHub PR, posts bug report as comment | — |
| **4. Review** | Two independent adversarial reviewers (5-point checklist each) | `bug-reviewer` × 2 |
| **5. Merge** | If both approve → asks you to confirm → merges PR | — |

**What to observe:**
- **Nested orchestration**: Phase 2 runs `plan_to_build` + `build` *inside* the bug pipeline
- **Review isolation**: Reviewer files are written only after BOTH complete — neither sees the other's verdict
- **Crash recovery**: `bugs/BUG-XXX/pipeline-state.json` checkpoints after each phase — say "resume" to continue
- **Artifacts on PR**: Bug report posted as comment, review verdicts posted as PR reviews
- **Fix-review cycles**: If a reviewer rejects, the pipeline re-enters the fix phase with feedback (max 2 cycles)
- **User stays in control**: The pipeline asks before merging — you can inspect everything first

**Tip:** If the pipeline crashes mid-run (terminal timeout, context limit), just tell Copilot:
```
resume the bug_to_pr pipeline
```
It reads the last checkpoint and picks up where it left off.

---

## Agent Infrastructure Summary

This project implements a full Copilot-native multi-agent orchestration system — ported and adapted from Claude Code slash commands. **[Full Architecture Guide with Mermaid diagrams →](.github/PIPELINES.md)**

### Pipelines (`.github/prompts/`)

| Prompt          | Invoke                | Purpose                                                                                                         |
| --------------- | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| `plan_to_build` | `/plan_to_build`      | Interactive spec creation — turns a feature request into a detailed, agent-executable plan in `specs/`          |
| `build`         | Reference a spec file | Execution engine — reads a spec, dispatches builder+validator agents per task, handles fix cycles and rollbacks |
| `bug_to_pr`     | `/bug_to_pr`          | End-to-end bug pipeline — 6 phases from bug report to merged PR with adversarial review                         |

### Agents (`.github/agents/`)

| Agent                  | Type       | Used By                                                                           |
| ---------------------- | ---------- | --------------------------------------------------------------------------------- |
| **builder**            | Read-write | `build`, `bug_to_pr` — implements tasks with TDD (RED → GREEN → REFACTOR)         |
| **validator**          | Read-only  | `build`, `bug_to_pr` — verifies task completion, shows actual command output      |
| **bug-creator**        | Read-write | `bug_to_pr` — investigates bugs, writes JIRA-format reports (8 required sections) |
| **bug-router**         | Read-only  | `bug_to_pr` — classifies which module owns the bug, outputs JSON routing          |
| **bug-fixer-backend**  | Read-write | `bug_to_pr` — creates fix plans for `backend/` bugs                               |
| **bug-fixer-frontend** | Read-write | `bug_to_pr` — creates fix plans for `frontend/src/` bugs                          |
| **bug-reviewer**       | Read-only  | `bug_to_pr` — adversarial 5-point reviewer (APPROVE/REJECT)                       |

### Hooks & Validators (`.github/hooks/`)

| Hook                     | Trigger          | What It Does                                                                                                                                                                                                            |
| ------------------------ | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `setup.sh`               | Session start    | Installs Python + Node dependencies automatically                                                                                                                                                                       |
| `post_tool_validator.py` | Every file write | Runs `ruff check` on `.py`, `tsc --noEmit` on `.ts/.tsx`, validates 7 required sections in `specs/*.md`, validates 8 required sections in `bugs/*/report.md`, enforces intermediate validator frequency for large plans |

### Supporting Files

| File                                                      | Purpose                                                              |
| --------------------------------------------------------- | -------------------------------------------------------------------- |
| `.github/bug-modules.json`                                | Maps modules → fixer agents, paths, and test commands                |
| `.github/instructions/team-orchestration.instructions.md` | Always-on rules for `specs/` files — enforces planning-only behavior |
| `.github/copilot-instructions.md`                         | Global project conventions (code style, API contract, test patterns) |
| `bugs/<BUG-ID>/pipeline-state.json`                       | Crash recovery checkpoints — resume from last completed phase        |
