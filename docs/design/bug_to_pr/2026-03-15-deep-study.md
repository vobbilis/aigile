# Design Study: `/bug_to_pr` Pipeline
**Date**: 2026-03-15
**Scope**: Full end-to-end pipeline — orchestrator command, all agent definitions, all enforcement hooks
**Method**: Static analysis of all source files + runtime evidence from BUG-001 through BUG-005

---

## Executive Summary

`/bug_to_pr` is a 6-phase sequential agent pipeline that takes a bug description and produces a reviewed, merged GitHub PR as its artifact. The architecture is sound and the design decisions are well-reasoned. The command has been validated against 5 real bugs with confirmed merges.

**However, a critical gap exists**: three enforcement hooks (`enforce_test_evidence.py`, `enforce_review_isolation.py`, and `merge_gate.py`) all read from `~/.claude/.bug_pipeline_state` — a global state file that **the orchestrator command never writes**. As a result:

- The fixer agent's test-evidence gate **blocks every run** (or was bypassed on earlier runs before the hook was installed)
- Review isolation enforcement is **silently disabled** (session IDs never registered)
- The merge gate **fails-open** (allows merge without dual approval) when state is missing

Additionally, the `bug-modules.json` default fixer (`bug-fixer-backend`) references an agent file that **does not exist**, and the routing validator's module registry path is **wrong**, silently skipping module cross-checks.

**Priority**: Fix the `.bug_pipeline_state` lifecycle first — it unblocks all three hooks simultaneously.

---

## Scope

### Files Analyzed

| File | Role |
|------|------|
| `~/.claude/commands/bug_to_pr.md` | Orchestrator — 6-phase pipeline definition |
| `~/.claude/agents/team/bug-creator.md` | Phase 1a: investigation + report |
| `~/.claude/agents/team/bug-router.md` | Phase 1b: classification + routing |
| `~/.claude/agents/team/bug-fixer-frontend.md` | Phase 2: frontend fixes |
| `~/.claude/agents/team/bug-fixer-api.md` | Phase 2: API fixes |
| `~/.claude/agents/team/bug-fixer-database.md` | Phase 2: database fixes (not read — similar pattern) |
| `~/.claude/agents/team/bug-reviewer.md` | Phase 4: adversarial review (alpha + beta) |
| `~/.claude/agents/team/pr-agent.md` | Phase 3: PR creation |
| `~/.claude/hooks/validate_bug_report.py` | Stop hook on bug-creator |
| `~/.claude/hooks/validate_bug_routing.py` | Stop hook on bug-router |
| `~/.claude/hooks/enforce_test_evidence.py` | Stop hook on bug-fixers |
| `~/.claude/hooks/validate_pr_test_evidence.py` | Stop hook on pr-agent |
| `~/.claude/hooks/enforce_review_isolation.py` | PreToolUse hook on bug-reviewer + global |
| `~/.claude/hooks/merge_gate.py` | PreToolUse hook on `gh pr merge` commands |
| `.github/bug-modules.json` | Per-repo module registry |
| `bugs/BUG-001` through `bugs/BUG-005` | Runtime evidence from real pipeline runs |

### Pipeline Architecture (Data Flow)

```
User: /bug_to_pr "description"
      │
      ▼
Phase 0: SETUP (orchestrator only)
  - Generate BUG-ID, create branch fix/<bug-id>
  - TeamCreate, write bugs/<BUG-ID>/pipeline-state.json
      │
      ▼
Phase 1a: TRIAGE — bug-creator
  - Investigates codebase, writes bugs/<BUG-ID>/report.md
  - Stop hook: validate_bug_report.py checks 8 required sections
      │
      ▼
Phase 1b: ROUTING — bug-router (skip if module hint given)
  - Reads report + .github/bug-modules.json
  - Outputs routing.json: {module, fixer_agent, confidence, rationale}
  - Stop hook: validate_bug_routing.py checks fixer exists + confidence ≥ medium
      │
      ▼
Phase 2: FIX — bug-fixer-<module>
  - Reads report, runs /plan_to_build_v2, /build_v2
  - Writes bugs/<BUG-ID>/test-results.md
  - Stop hook: enforce_test_evidence.py checks test output patterns
      │
      ▼
Phase 3: PR CREATION — pr-agent
  - git add + commit + push, gh pr create
  - Stop hook: validate_pr_test_evidence.py checks PR body has ## Test Evidence
      │
      ▼
Phase 4: ADVERSARIAL REVIEW — reviewer-alpha + reviewer-beta (PARALLEL)
  - Both deployed simultaneously (run_in_background: true)
  - Read report, diff, test results; produce APPROVE/REJECT verdict
  - PreToolUse hook: enforce_review_isolation.py blocks cross-reading
  - Orchestrator writes reviews/alpha.md + reviews/beta.md after both complete
      │
      ▼
Phase 5: MERGE GATE
  - AskUserQuestion for confirmation
  - PreToolUse hook: merge_gate.py blocks gh pr merge unless both APPROVEd
  - Writes bugs/<BUG-ID>/verdict.json, then gh pr merge --squash
      │
      ▼
Phase 6: SHUTDOWN
  - TaskList verification, parallel shutdown_request, TeamDelete
  - Kill tmux panes from bugs/<BUG-ID>/panes.txt
  - Print pipeline report
```

---

## Analysis

---

### 🔒 Security

#### S1: No input sanitization on BUG_DESCRIPTION
**Severity**: Medium
**Location**: `bug_to_pr.md`, Phase 0, pipeline-state.json write

The bug description is interpolated directly into shell heredocs:
```bash
echo '{"bug_id":"<BUG-ID>","phase":"setup",...}' > bugs/<BUG-ID>/pipeline-state.json
```
If BUG_DESCRIPTION contains single quotes, backslashes, or newlines, this corrupts the JSON or causes shell errors. Similarly, the `git commit -m "fix: <brief description>"` interpolation could break on special characters.

**Fix**: Use Python or `jq` to write JSON files rather than shell echo-with-interpolation.

#### S2: Review isolation relies on session IDs that are never registered
**Severity**: High (security control bypassed)
**Location**: `enforce_review_isolation.py:84-86`, `bug_to_pr.md` Phase 4

`enforce_review_isolation.py` reads reviewer session IDs from `~/.claude/.bug_pipeline_state`:
```python
alpha_session = reviewers.get("alpha", {}).get("session_id", "")
beta_session  = reviewers.get("beta",  {}).get("session_id", "")
```
The orchestrator command never writes reviewer session IDs to any state file. The hook's `reviewers` dict will always be empty, so `session_id == alpha_session` is always `False`, and the hook exits 0 (allow) for all reads. **Review isolation is silently not enforced at the hook level.**

The isolation relies entirely on the prompt instruction ("Do NOT read..."), which is an honor system.

**Fix**: Write reviewer session IDs to `~/.claude/.bug_pipeline_state` when deploying each reviewer.

#### S3: merge_gate.py fails-open when pipeline state is missing
**Severity**: High (safety control bypassed)
**Location**: `merge_gate.py:93-95`
```python
if not os.path.exists(PIPELINE_STATE):
    logger.warning("No pipeline state, allowing merge (fail-open)")
    sys.exit(0)
```
Since `~/.claude/.bug_pipeline_state` is never written by the orchestrator, **every `gh pr merge` command is allowed through without dual-reviewer verification**. The user confirmation in Phase 5 provides a human gate, but the automated enforcement is inactive.

**Fix**: Write the global state file in Phase 0 and keep it updated — or change merge_gate.py to read from `bugs/*/pipeline-state.json` directly.

---

### ✅ Correctness

#### C1: `~/.claude/.bug_pipeline_state` is never written (CRITICAL)
**Severity**: Critical
**Location**: All three enforcement hooks

Three hooks share a dependency on `~/.claude/.bug_pipeline_state`:

| Hook | Behavior when state missing |
|------|-----------------------------|
| `enforce_test_evidence.py` | **BLOCKS** (exit 1) — fixer agent cannot stop |
| `enforce_review_isolation.py` | **Allows** (exit 0, fail-open) |
| `merge_gate.py` | **Allows** (exit 0, fail-open) |

The orchestrator writes `bugs/<BUG-ID>/pipeline-state.json` (local, per-bug) but never `~/.claude/.bug_pipeline_state` (global, per-session). `enforce_test_evidence.py` will block every fixer agent unless the global state exists from another mechanism.

**Evidence**: BUG-003, BUG-004, BUG-005 all succeeded — either the hook was installed after those runs, or a mechanism outside this command writes the file. **Needs verification.**

**Fix**: Add Phase 0 step to write `~/.claude/.bug_pipeline_state`:
```bash
echo '{"bug_id":"<BUG-ID>","branch":"fix/<bug-id>","phase":"setup"}' \
  > ~/.claude/.bug_pipeline_state
```
And update it at each phase transition. Clean it up in Phase 6.

#### C2: `bug-fixer-backend` agent does not exist
**Severity**: High
**Location**: `.github/bug-modules.json:6`, `~/.claude/agents/team/`

`bug-modules.json` specifies:
```json
"backend": { "fixer": "bug-fixer-backend", ... }
"default_fixer": "bug-fixer-backend"
```
The agent `~/.claude/agents/team/bug-fixer-backend.md` **does not exist**. The deployed agents are:
- `bug-fixer-frontend.md` ✅
- `bug-fixer-api.md` ✅
- `bug-fixer-database.md` ✅
- `bug-fixer-backend.md` ❌ MISSING

`validate_bug_routing.py` checks:
```python
agent_path = os.path.join(AGENTS_DIR, f"{fixer_agent}.md")
if not os.path.exists(agent_path):
    result = {"result": "block", ...}  # BLOCKS
```
Any bug routed to the `backend` module (or via the default fixer) will be **blocked by the routing validator**. BUG-005 was routed to `bug-fixer-backend` — it succeeded, suggesting this agent existed at run time or the hook wasn't installed yet.

**Fix**: Create `~/.claude/agents/team/bug-fixer-backend.md`, or change `bug-modules.json` to route `backend` to `bug-fixer-api`.

#### C3: `validate_bug_routing.py` reads the wrong path for `bug-modules.json`
**Severity**: Medium
**Location**: `validate_bug_routing.py:48`
```python
BUG_MODULES_FILE = ".claude/bug-modules.json"  # ← WRONG
```
The actual registry is at `.github/bug-modules.json`. The hook reads a relative path from CWD, resolving to `<project>/.claude/bug-modules.json` which does not exist. The hook silently skips module validation (line 200-201: "No bug-modules.json found, skipping module cross-check"). **Module cross-checking is completely inactive.**

**Fix**: Change to `".github/bug-modules.json"`.

#### C4: `validate_bug_report.py` uses mtime heuristic instead of pipeline state
**Severity**: Medium
**Location**: `validate_bug_report.py:69-95`

The hook finds "the newest report.md in bugs/" by modification time:
```python
reports = list(target.rglob("report.md"))
newest = max(reports, key=lambda p: p.stat().st_mtime)
```
If a user views (touches) an old bug's report during a new pipeline run, the hook validates the **wrong report**. It should use `~/.claude/.bug_pipeline_state` to look up the current `bug_id` and validate `bugs/<bug_id>/report.md` directly.

**Fix**: Read `bug_id` from `~/.claude/.bug_pipeline_state` first, fall back to mtime only if state is unavailable.

#### C5: Pipeline state schema drift between BUG-002 and later bugs
**Severity**: Low
**Location**: `bugs/BUG-002/pipeline-state.json`
```json
{"bug_id":"BUG-002", "fix_cycle":1, ...}  ← BUG-002
{"bug_id":"BUG-005", "fix_review_cycle":0, ...}  ← BUG-005
```
Field was renamed from `fix_cycle` to `fix_review_cycle`. The crash recovery logic reads `fix_review_cycle` — resuming BUG-002 would start with cycle 0 instead of 1. No schema version field exists.

**Fix**: Add `"schema_version": 2` to pipeline-state.json and handle migration in resume logic.

#### C6: BUG-ID generation uses `grep -P` (macOS incompatible)
**Severity**: Medium
**Location**: `bug_to_pr.md`, Phase 0
```bash
ls bugs/ 2>/dev/null | grep -oP 'BUG-\d+' | sort -t- -k2 -n | tail -1
```
macOS ships BSD grep which does **not support `-P` (Perl-compatible regex)**. This fails silently, returning no matches, causing the orchestrator to always generate BUG-001 regardless of existing bugs — colliding with real BUG-001 artifacts.

**Fix**: Replace with:
```bash
ls bugs/ 2>/dev/null | grep -oE 'BUG-[0-9]+' | sort -t- -k2 -n | tail -1
```
Or use Python (already a dependency via `uv`).

#### C7: No guard for pre-existing fix branch
**Severity**: Low
**Location**: `bug_to_pr.md`, Phase 0, step 6
```bash
git checkout -b fix/<bug-id-lowercase> main
```
If a previous interrupted run already created this branch, the command fails with "branch already exists" and the pipeline halts in Phase 0. There is no `--force` or existence check.

**Fix**: Check `git branch --list fix/<bug-id>` first; if exists, `git checkout fix/<bug-id>` instead.

#### C8: Fixer agent skill names reference non-existent skills
**Severity**: Medium
**Location**: `bug-fixer-frontend.md:37`, `bug-fixer-api.md:37`
```
Skill("plan_w_team", ...)  ← agent definition
```
The available skills are `plan_to_build_v2` and `build_v2` (or `plan_to_build` / `build`). `plan_w_team` does not exist. The orchestrator prompt correctly overrides with `/plan_to_build_v2` + `/build_v2`, but the agent DEFINITION is wrong — if the agent falls back to its own instructions, it will fail.

**Fix**: Update agent definitions to `Skill("plan_to_build_v2")` / `Skill("build_v2")`.

#### C9: Phase 3 git add uses hardcoded paths
**Severity**: Low
**Location**: `bug_to_pr.md`, Phase 3, step 1
```bash
git add bugs/<BUG-ID>/ specs/ backend/ frontend/ src/
```
If none of `specs/`, `backend/`, `frontend/`, `src/` exist (project has different layout), `git add` on non-existent paths prints warnings but exits 0. Unstaged changes get missed. `git add -A` is blocked by hook (correct), but the alternative should be `git status --porcelain` + targeted staging.

**Fix**: Check `git status --porcelain` first and stage only the actual changed paths.

---

### ⚡ Performance

#### P1: `validate_pr_test_evidence.py` makes a GitHub API call on every pr-agent stop
**Location**: `validate_pr_test_evidence.py:99-116`
```python
result = subprocess.run(
    ["gh", "pr", "list", "--state", "open", "--json", "number,body", "--limit", "1"],
    timeout=15
)
```
15-second timeout on a network call that runs every time pr-agent stops. On slow connections or during GitHub API rate limiting, this blocks the pipeline for up to 15 seconds. The hook also gets the **most recent open PR** rather than the specific BUG's PR — if another PR is open from a different branch, it validates the wrong one.

**Fix**: Pass the PR number via environment variable or pipeline state, then use `gh pr view <PR#>` to target the correct PR specifically.

#### P2: Parallel reviewer pane capture has a 2-second race condition
**Location**: `bug_to_pr.md`, Phase 4, step 3
```bash
sleep 2 && tmux list-panes ...
```
After deploying both background reviewers, a fixed `sleep 2` is used before capturing their pane IDs. If a reviewer agent takes >2 seconds to open its pane (model loading, API latency), the pane isn't tracked and won't be cleaned up in Phase 6. Leaking panes accumulate across runs.

**Fix**: Poll for exactly N new panes to appear (up to a timeout) rather than sleeping a fixed duration.

#### P3: Cold-start overhead for 6 sequential agent deployments
Each phase deploys a fresh agent: bug-creator → bug-router → bug-fixer → pr-agent → 2×reviewer. Each deployment requires API round-trips and model initialization. Total latency per pipeline run is dominated by agent startup time multiplied by 5+ deployments. The parallel reviewers (Phase 4) are the only phase that amortizes this.

---

### 📈 Scalability

#### SC1: Single-bug global state prevents concurrent pipeline runs
**Location**: `~/.claude/.bug_pipeline_state` (single file, not namespaced)

Two simultaneous `/bug_to_pr` invocations would overwrite each other's global state. The `enforce_test_evidence.py` and `merge_gate.py` hooks would each see the last writer's `bug_id`, potentially validating artifacts for the wrong bug.

**Fix**: Namespace the state file by bug_id: `~/.claude/.bug_pipeline_state.<BUG-ID>` and clean up on Phase 6.

#### SC2: tmux dependency breaks in non-tmux terminals
**Location**: `bug_to_pr.md`, Phases 1a/1b/2/3/4 (pane capture steps)
```bash
tmux list-panes -a -F "#{pane_id}"
```
In VS Code integrated terminal, macOS Terminal.app, iTerm2 (without tmux), or CI environments, this command fails or returns empty. Pane tracking silently writes empty files; cleanup in Phase 6 is a no-op. This is cosmetic (no functional impact) but Phase 6 incorrectly reports "N panes killed."

**Fix**: Wrap in a tmux availability check: `command -v tmux >/dev/null 2>&1 && tmux list-panes ...`.

#### SC3: Module registry hardcodes `bug-fixer-backend` as default for all unknown modules
**Location**: `.github/bug-modules.json:32`
```json
"default_fixer": "bug-fixer-backend"
```
Any bug that doesn't match `backend`, `frontend`, `java`, or `go` routes to `bug-fixer-backend` — an agent that doesn't exist. The routing validator blocks this. There's no "generic fixer" fallback that could handle cross-cutting or infrastructure bugs.

---

### 🔧 Maintainability

#### M1: Agent module ownership is hardcoded and drifts from project structure
**Location**: `bug-fixer-frontend.md:18-23` (owns `src/components/`, `src/pages/`, `src/hooks/`)
Actual project structure has `frontend/src/` (from bug-modules.json). The fixer agent's hardcoded paths don't match. If a fixer agent is reused across projects, its `## Module Ownership` section is a lie.

**Better design**: One generic `bug-fixer.md` agent that reads module config from `.github/bug-modules.json` at runtime. Eliminates the N-agent maintenance burden.

#### M2: No single source of truth for test commands
Test commands appear in three places:
1. `bug-modules.json`: `"test_command": "cd frontend && npm test -- --run"`
2. `bug-fixer-frontend.md`: `npm test -- --grep component`
3. Orchestrator Phase 2 prompt: defers to fixer agent

All three can drift independently. If the test command changes (e.g., migrating from Jest to Vitest), three files need updating.

**Fix**: Fixer agents should read `test_command` from `.github/bug-modules.json` rather than hardcoding it.

#### M3: v1 fixes are documented inline in the command but not in a changelog
**Location**: `bug_to_pr.md:33-41` ("V1 Issues Fixed in This Version")

This section documents 6 v1 failure modes inline. As v3 improvements are made, this will grow stale. Better to have a `CHANGELOG.md` or commit history for this.

#### M4: No schema for pipeline-state.json
The `pipeline-state.json` format is documented only by example (inline in the command). There's no JSON Schema or TypeScript type. The BUG-002 drift (C5) demonstrates the risk. Adding a schema would catch future regressions.

---

### 👁️ Observability

#### O1: Hook log files are excellent — but not surfaced to user
**Location**: `~/.claude/hooks/*.log`

Every hook writes structured logs (`validate_bug_report.log`, `enforce_review_isolation.log`, etc.). These are invaluable for debugging but are never shown to the user or included in the pipeline report. When a hook blocks an agent, the user must manually find the log.

**Fix**: Phase 6 report should include: "Hook events: see `~/.claude/hooks/*.log`" with a summary of any blocks that occurred.

#### O2: No timing metrics in the pipeline report
The final Phase 6 report lists phase status but not how long each phase took. A 45-minute pipeline that hangs in Phase 2 looks identical to a fast one.

**Fix**: Record `phase_start_time` / `phase_end_time` in pipeline-state.json at each transition.

#### O3: Stale `validate_bug_routing.log` and `enforce_review_isolation.log` exist from prior runs
**Evidence**: Log files exist at `~/.claude/hooks/validate_bug_routing.log` — runtime evidence of the system working. But logs accumulate indefinitely with no rotation or cleanup.

---

### 🧪 Testing

The pipeline has been validated against 5 real bugs:

| Bug | Module | Outcome | Reviewers |
|-----|--------|---------|-----------|
| BUG-001 | — | Merged | alpha+beta |
| BUG-002 | backend | PR created (phase: pr) | alpha+beta |
| BUG-003 | frontend | Fixed | alpha+beta |
| BUG-004 | frontend | Merged | alpha+beta |
| BUG-005 | backend | Merged (both APPROVE) | alpha+beta |

**Untested scenarios**:
- [ ] REJECT → re-fix cycle (MAX_FIX_REVIEW_CYCLES path)
- [ ] Mixed verdict (one APPROVE, one REJECT)
- [ ] Pipeline crash during Phase 2 → resume from state file
- [ ] Module hint provided (routing skip path)
- [ ] Backend bug on current system (bug-fixer-backend missing)
- [ ] Concurrent runs (two bugs simultaneously)
- [ ] Non-tmux environment
- [ ] Interrupted shutdown (agents don't respond within 60s)

---

## Industry Comparison

| Aspect | `/bug_to_pr` | GitHub Copilot Workspace | Devin AI | Assessment |
|--------|-------------|--------------------------|----------|------------|
| Investigation agent | bug-creator (sonnet) | Inline LLM | Devin agent | Comparable |
| Fix agent | fixer (opus) | Inline LLM | Devin agent | Comparable |
| Review | 2× parallel agents (opus) | None | None | **Superior** |
| Merge gate | Dual approval + user confirm | N/A | User confirm | **Superior** |
| State persistence | pipeline-state.json | None | Session state | Comparable |
| Crash recovery | Phase resume from state | None | None | **Superior** |
| Hook enforcement | Python hooks on every gate | None | None | **Superior** |
| Module routing | bug-modules.json registry | N/A | N/A | Novel |
| Test evidence enforcement | Pattern matching on output | None | None | **Superior** |

The dual adversarial review pattern (parallel, isolated, hook-enforced) is the most distinctive and differentiated capability. No comparable open-source tool does this.

---

## 10x Improvement Opportunities

### 1. Write `~/.claude/.bug_pipeline_state` to activate all dormant hooks
**Impact**: Activates 3 currently-inactive enforcement hooks simultaneously.
**Cost**: 5 lines added to Phase 0 + 1 line per phase transition.
This single change unlocks enforce_test_evidence, enforce_review_isolation, and merge_gate as intended.

```bash
# Phase 0, after pipeline-state.json is written:
cat > ~/.claude/.bug_pipeline_state << 'EOF'
{"bug_id":"<BUG-ID>","phase":"setup","branch":"fix/<bug-id>","fix_review_cycle":0}
EOF
```
Update `phase` field at each transition. Remove in Phase 6.

### 2. One generic `bug-fixer.md` that reads config from the registry
**Impact**: Eliminates N-agent maintenance burden; enables unlimited modules without new agent files.
**Cost**: Rewrite 3 agent files into 1 parameterized one.

```markdown
## Module Ownership (read at runtime)
Read `.github/bug-modules.json` for your module's paths and test command.
Your module is provided in your task prompt as MODULE=<module>.
```

### 3. Fix the 4 incorrect/stale config values identified above
In one commit:
- `validate_bug_routing.py:48`: `.claude/bug-modules.json` → `.github/bug-modules.json`
- `bug-fixer-frontend.md:37`: `plan_w_team` → `plan_to_build_v2`, `build` → `build_v2`
- `bug-fixer-api.md:37`: same
- `bug-modules.json`: add `bug-fixer-backend.md` or remap `backend` → `bug-fixer-api`

### 4. Write reviewer session IDs to global state before deploying reviewers
**Impact**: Enables real hardware-level review isolation enforcement.
**Cost**: The orchestrator would need the session IDs of the deployed reviewers. Claude Code `Task` tool returns an agent ID — write that to `~/.claude/.bug_pipeline_state.reviewers`.

### 5. Replace tmux pane tracking with a process-based cleanup
**Impact**: Works in all terminal environments.
**Cost**: Medium — requires tracking agent process IDs instead of tmux panes.

---

## Recommended Actions (Prioritized)

| Priority | Action | Risk | Effort |
|----------|--------|------|--------|
| P0 | Write `~/.claude/.bug_pipeline_state` in Phase 0, update per phase, delete in Phase 6 | Low | Small |
| P0 | Create `~/.claude/agents/team/bug-fixer-backend.md` (copy from api, adjust paths) | Low | Small |
| P0 | Fix `validate_bug_routing.py` path: `.claude/` → `.github/` | Zero | Trivial |
| P1 | Fix `validate_bug_report.py` to use pipeline state bug_id instead of mtime | Low | Small |
| P1 | Fix `grep -oP` → `grep -oE` in Phase 0 BUG-ID generation | Zero | Trivial |
| P1 | Fix fixer agent skill names: `plan_w_team` → `plan_to_build_v2` | Low | Trivial |
| P1 | Add branch existence check in Phase 0 (`git checkout` vs `git checkout -b`) | Low | Small |
| P2 | Add pipeline state schema version field | Zero | Trivial |
| P2 | Replace tmux pane capture sleep with a polling loop | Low | Small |
| P3 | One generic `bug-fixer.md` reading config from registry | Medium | Medium |
| P3 | Add phase timestamps to pipeline state | Zero | Small |
| P3 | Surface hook log paths in Phase 6 report | Zero | Trivial |

---

## Evidence Appendix

### Real pipeline runs confirming the system works end-to-end

```
BUG-005/pipeline-state.json:
  {"bug_id":"BUG-005","phase":"review","branch":"fix/bug-005",
   "fix_review_cycle":0,"module":"backend","fixer_agent":"bug-fixer-backend",
   "pr_number":11,"pr_url":"...","alpha_verdict":"APPROVE","beta_verdict":"APPROVE"}

BUG-005/verdict.json:
  {"merge_allowed":true,"alpha":"APPROVE","beta":"APPROVE","merged":true}

BUG-005/reviews/alpha.md (excerpt):
  ## Verdict: APPROVE
  Root cause addressed: YES — both backend and frontend fixed.
  Test evidence: YES — 5 backend + 4 frontend new tests, all pass.
  ## Test Evidence Reviewed: YES
```

### Confirmed agent file inventory

```
~/.claude/agents/team/
  bug-creator.md       ✅ (model: sonnet, Stop: validate_bug_report.py)
  bug-router.md        ✅ (model: haiku, Stop: validate_bug_routing.py)
  bug-fixer-frontend.md ✅ (model: opus, Stop: enforce_test_evidence.py)
  bug-fixer-api.md     ✅ (model: opus, Stop: enforce_test_evidence.py)
  bug-fixer-database.md ✅ (model: opus, Stop: enforce_test_evidence.py)
  bug-fixer-backend.md ❌ MISSING — blocks routing validator
  bug-reviewer.md      ✅ (model: opus, PreToolUse: enforce_review_isolation.py)
  pr-agent.md          ✅ (model: sonnet, Stop: validate_pr_test_evidence.py)
```

### Global state file lifecycle gap (CRITICAL)

```
Hooks that READ ~/.claude/.bug_pipeline_state:
  enforce_test_evidence.py   → blocks (exit 1) if missing
  enforce_review_isolation.py → allows (exit 0) if missing
  merge_gate.py              → allows (exit 0) if missing

Who WRITES ~/.claude/.bug_pipeline_state:
  bug_to_pr.md               → DOES NOT WRITE THIS FILE
  team_state_tracker.py      → writes ~/.claude/.team_lead_session (different file)
  subagent_start.py          → writes TTS debug logs (different file)

Result: enforce_test_evidence blocks every fixer, or was installed after the test bugs ran.
```

### Bug-modules.json path inconsistency

```
validate_bug_routing.py line 48:
  BUG_MODULES_FILE = ".claude/bug-modules.json"   ← does not exist

Actual file location:
  .github/bug-modules.json                         ← exists

Effect: module cross-check silently skipped for every routing decision
```
