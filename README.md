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

## Agent Infrastructure Summary

This project implements a full Copilot-native multi-agent orchestration system — ported and adapted from Claude Code slash commands. **[Full Architecture Guide with Mermaid diagrams →](.github/PIPELINES.md)**

### Pipelines (`.github/prompts/`)

| Prompt | Invoke | Purpose |
|--------|--------|---------|
| `plan_to_build` | `/plan_to_build` | Interactive spec creation — turns a feature request into a detailed, agent-executable plan in `specs/` |
| `build` | Reference a spec file | Execution engine — reads a spec, dispatches builder+validator agents per task, handles fix cycles and rollbacks |
| `bug_to_pr` | `/bug_to_pr` | End-to-end bug pipeline — 6 phases from bug report to merged PR with adversarial review |

### Agents (`.github/agents/`)

| Agent | Type | Used By |
|-------|------|---------|
| **builder** | Read-write | `build`, `bug_to_pr` — implements tasks with TDD (RED → GREEN → REFACTOR) |
| **validator** | Read-only | `build`, `bug_to_pr` — verifies task completion, shows actual command output |
| **bug-creator** | Read-write | `bug_to_pr` — investigates bugs, writes JIRA-format reports (8 required sections) |
| **bug-router** | Read-only | `bug_to_pr` — classifies which module owns the bug, outputs JSON routing |
| **bug-fixer-backend** | Read-write | `bug_to_pr` — creates fix plans for `backend/` bugs |
| **bug-fixer-frontend** | Read-write | `bug_to_pr` — creates fix plans for `frontend/src/` bugs |
| **bug-reviewer** | Read-only | `bug_to_pr` — adversarial 5-point reviewer (APPROVE/REJECT) |

### Hooks & Validators (`.github/hooks/`)

| Hook | Trigger | What It Does |
|------|---------|-------------|
| `setup.sh` | Session start | Installs Python + Node dependencies automatically |
| `post_tool_validator.py` | Every file write | Runs `ruff check` on `.py`, `tsc --noEmit` on `.ts/.tsx`, validates 7 required sections in `specs/*.md`, validates 8 required sections in `bugs/*/report.md`, enforces intermediate validator frequency for large plans |

### Supporting Files

| File | Purpose |
|------|---------|
| `.github/bug-modules.json` | Maps modules → fixer agents, paths, and test commands |
| `.github/instructions/team-orchestration.instructions.md` | Always-on rules for `specs/` files — enforces planning-only behavior |
| `.github/copilot-instructions.md` | Global project conventions (code style, API contract, test patterns) |
| `bugs/<BUG-ID>/pipeline-state.json` | Crash recovery checkpoints — resume from last completed phase |
