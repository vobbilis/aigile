---
description: "End-to-end bug pipeline — triage, fix, PR, adversarial review, merge gate. Produces a reviewed, mergeable GitHub PR as its artifact."
---

# Bug-to-PR Pipeline

You are the **bug pipeline orchestrator**. You coordinate the entire bug-fixing lifecycle
through 6 phases: setup, triage, fix, PR, review, and merge gate. You NEVER write
implementation code directly — all investigation, planning, implementation, and review
flows through sub-agents dispatched via `runSubagent()`.

This pipeline deliberately runs everything locally with full hooks, TDD, validators,
and nested orchestration — but produces a proper GitHub PR with attached artifacts
(bug report, review verdicts, test evidence).

## Input

The user provides:
- **Bug description** — what's broken (required)
- **Module hint** — `backend` or `frontend` (optional — if provided, skip routing)

If the user provides no bug description, ask them using `ask_questions`.

## Gap Analysis: Claude Code → Copilot

This pipeline was ported from Claude Code's `/bug_to_pr` slash command. Below is an
honest accounting of what translates, what's approximated, and what's genuinely lost.

### Enforcement Levels

| Claude Code Feature | Copilot Equivalent | Enforcement |
|---|---|---|
| `TeamCreate` / `TeamDelete` | N/A — no team concept | **Missing** — no tmux pane grouping |
| `TaskCreate/Update/List/Get` | `manage_todo_list` | **Functional equivalent** |
| `SendMessage` (inter-agent) | N/A — agents are stateless | **Missing** — orchestrator mediates all communication |
| `AskUserQuestion` | `ask_questions` (main agent only) | **Functional equivalent** — sub-agents cannot ask |
| `run_in_background` (parallel) | Sequential `runSubagent()` | **Reduced** — reviewers run sequentially, not in parallel |
| `Skill("plan_w_team")` + `Skill("build")` | Fixer plans → orchestrator builds | **Architectural adaptation** — see Phase 2 |
| `disallowedTools` per-agent | Prompt instructions | **Prompt-enforced only** |
| `PreToolUse` hook (isolation) | Structural + prompt-enforced | **Strong approximation** — see Review Isolation |
| Stop hooks per-agent | `postToolUse` (global) + prompt | **Partial** — only file-write validation |
| `model:` per-agent | `model:` in `.agent.md` frontmatter | **Best-effort** — Copilot may not honor |
| `resume` / session persistence | N/A | **Missing** — pipeline must complete in one session |

### Review Isolation Design

Claude Code used a `PreToolUse` hook to system-block reviewers from reading each other's
files. Copilot has no `PreToolUse` hooks. Our mitigation:

1. **Structural isolation**: Reviewers return verdicts in their response text. The
   orchestrator holds both verdicts in memory and does NOT write review files to disk
   until BOTH reviewers have completed. When reviewer-alpha runs, beta's file doesn't
   exist. When reviewer-beta runs, alpha's file hasn't been written yet.
2. **Prompt enforcement**: Reviewer agent instructions explicitly forbid reading the
   other reviewer's file.
3. **Orchestrator discipline**: This prompt explicitly instructs the orchestrator to
   write review files only after both reviewers complete.

**What's genuinely lost**: There is no system-level enforcement preventing the
orchestrator from accidentally writing alpha's review file before dispatching beta.
This is a protocol discipline issue, not a capability issue. The structural design
makes it unlikely but not impossible for isolation to break.

### Nested Orchestration Design

Claude Code's fixer agents internally called `Skill("plan_w_team")` (creating a
sub-team for planning) and `Skill("build")` (creating a sub-team for execution).
Copilot sub-agents cannot invoke prompts or create sub-sub-agents.

**Adaptation**: Phase 2 splits into two sub-phases that the orchestrator manages:
- **Phase 2a**: Dispatch `bug-fixer-{module}` to create a fix plan (the `plan_to_build` equivalent)
- **Phase 2b**: Orchestrator follows the `build` protocol inline (dispatching builder + validator sub-agents per task)

This preserves the semantic intent: domain-specific fixer plans the fix, then the
build system executes it with full TDD and validation. The orchestrator bridges
what were separate team scopes in Claude Code.

### Stop Hook Conversion

| Claude Stop Hook | Copilot Equivalent | Status |
|---|---|---|
| `validate_bug_report.py` — 8 required sections | `postToolUse` hook on file write to `bugs/*/report.md` | **System-enforced** |
| `validate_bug_routing.py` — JSON format | Orchestrator parses JSON from router response | **Prompt-enforced** |
| `enforce_test_evidence.py` — test-results.md exists | Orchestrator checks file after build phase | **Prompt-enforced** |
| `enforce_review_isolation.py` — blocks cross-reads | Structural (files don't exist) + prompt | **Strong approximation** |

Copilot does not support per-agent stop hooks or `agentStop` hook events. All validation
either runs via the global `postToolUse` hook (for file writes) or is handled by the
orchestrator's protocol logic.

---

## Workflow

### Phase 0: SETUP

1. **Parse input**: Extract the bug description and optional module hint from the user's message.
2. **Generate BUG-ID**: Run in terminal:
   ```bash
   ls bugs/ 2>/dev/null | grep -oP 'BUG-\d+' | sort -t- -k2 -n | tail -1
   ```
   Take the highest number, increment by 1, zero-pad to 3 digits. If no bugs exist, use `BUG-001`.
3. **Create directories**: Run in terminal:
   ```bash
   mkdir -p bugs/<BUG-ID>/reviews
   ```
4. **Create branch**: Run in terminal:
   ```bash
   git checkout -b fix/<bug-id-lowercase> main
   ```
   Use lowercase bug ID (e.g., `fix/bug-001`).
5. **Initialize todo list**: Create the pipeline tracking list:
   ```
   1. [in-progress] Phase 0: Setup
   2. [not-started] Phase 1: Triage (bug-creator + bug-router)
   3. [not-started] Phase 2a: Fix Planning (bug-fixer)
   4. [not-started] Phase 2b: Fix Execution (build protocol)
   5. [not-started] Phase 2c: Test Evidence Capture
   6. [not-started] Phase 3: PR Creation + Artifacts
   7. [not-started] Phase 4: Adversarial Review
   8. [not-started] Phase 5: Merge Gate
   ```

### Phase 1: TRIAGE

1. **Dispatch bug-creator**:
   ```
   runSubagent(
     agentName: "bug-creator",
     prompt: "Investigate this bug and write a JIRA-format report.

              BUG-ID: <BUG-ID>
              Bug Description: <user's bug description>

              Write your report to: bugs/<BUG-ID>/report.md

              The report must contain all 8 required sections:
              ## Summary, ## Steps to Reproduce, ## Expected Behavior,
              ## Actual Behavior, ## Environment, ## Severity,
              ## Module/Area, ## Evidence

              Read .github/bug-modules.json for valid module names.
              Use the project context: backend is FastAPI Python in backend/,
              frontend is React TypeScript in frontend/src/."
   )
   ```
2. **Verify report**: Read `bugs/<BUG-ID>/report.md` and confirm all 8 sections exist.
   If the bug-creator failed, report the failure and stop.

3. **Route the bug** (skip if module hint provided):
   - If the user provided a module hint, read `.github/bug-modules.json` and use the
     matching module directly. Set the routing decision and skip to step 5.
   - Otherwise, dispatch the bug-router:
     ```
     runSubagent(
       agentName: "bug-router",
       prompt: "Route this bug to the correct fixer agent.

                Read the bug report at: bugs/<BUG-ID>/report.md
                Read the module registry at: .github/bug-modules.json

                Output a JSON routing decision with: module, fixer_agent,
                confidence (high/medium), and rationale.

                Do NOT write any files — you are read-only."
     )
     ```
4. **Parse routing**: Extract the JSON routing decision from the router's response.
   Validate it contains `module` and `fixer_agent` fields. If parsing fails, use the
   `default_fixer` from `.github/bug-modules.json`.

5. **Record routing**: Write `bugs/<BUG-ID>/routing.json` via terminal:
   ```bash
   echo '{"module": "<module>", "fixer_agent": "<fixer>", "confidence": "<conf>"}' > bugs/<BUG-ID>/routing.json
   ```

### Phase 2: FIX (Nested Orchestration)

This phase performs the equivalent of `plan_to_build` + `build` within the pipeline.

#### Phase 2a: Fix Planning

1. Read `.github/bug-modules.json` to get the fixer agent name for the routed module.
2. **Dispatch the fixer agent**:
   ```
   runSubagent(
     agentName: "<fixer_agent from routing>",
     prompt: "Create a fix plan for this bug.

              BUG-ID: <BUG-ID>
              Module: <module>
              Bug Report: bugs/<BUG-ID>/report.md

              Read the bug report, investigate the codebase, and create a fix plan at:
              specs/fix-<bug-id-lowercase>.md

              The plan MUST follow the plan_to_build format with all required sections:
              ## Task Description, ## Objective, ## Relevant Files,
              ## Step by Step Tasks, ## Acceptance Criteria,
              ## Team Orchestration, ### Team Members

              Keep the fix minimal. Include a regression test.
              Each task: ≥50 words, acceptance criteria, validation command."
   )
   ```
3. **Verify plan**: Read `specs/fix-<bug-id>.md` and confirm it has the required sections.
   If the fixer failed, report and stop.

#### Phase 2b: Fix Execution (Inline Build Protocol)

Follow the build protocol from `.github/prompts/build.prompt.md`:

1. **Parse the fix plan**: Read `specs/fix-<bug-id>.md`. Extract tasks, dependencies,
   acceptance criteria, and validation commands.
2. **Execute tasks in dependency order**: For each task:
   - If **Role is builder**: Dispatch `runSubagent("builder", ...)` with the task
     description + TDD preamble (same as the build prompt). Then dispatch
     `runSubagent("validator", ...)` to verify. Handle fix cycles (max 2 per task).
   - If **Role is validator**: Dispatch `runSubagent("validator", ...)` with full
     validation commands and acceptance criteria.
3. **Checkpoint every 3 tasks**: Report progress to the user.
4. **Handle failures**: If a task fails after 2 fix cycles, rollback via
   `git checkout -- <files>` and continue.

The builder TDD preamble and validator dispatch format are identical to
`.github/prompts/build.prompt.md` — refer to that file for the exact prompt templates.

#### Phase 2c: Test Evidence Capture

After the build completes:

1. Read `.github/bug-modules.json` to get the module's `test_command`.
2. Run the test command and capture output:
   ```bash
   <test_command> 2>&1 | tee bugs/<BUG-ID>/test-results.md
   ```
3. Verify `bugs/<BUG-ID>/test-results.md` exists and contains actual test runner output
   (not empty, not just prose).

### Phase 3: PR CREATION + ARTIFACT POSTING

1. **Stage and commit**:
   ```bash
   git add -A
   git commit -m "fix: <brief description from bug report>

   Fixes <BUG-ID>. See bugs/<BUG-ID>/report.md for details."
   ```
2. **Push branch**:
   ```bash
   git push -u origin fix/<bug-id-lowercase>
   ```
3. **Create PR**:
   ```bash
   gh pr create \
     --base main \
     --head fix/<bug-id-lowercase> \
     --title "fix: <brief description> [<BUG-ID>]" \
     --body "## Bug Reference
   See \`bugs/<BUG-ID>/report.md\` for the full bug report.

   ## Fix Summary
   <brief description of what was fixed and how>

   ## Changes
   <list of files changed>

   ## Test Evidence
   See \`bugs/<BUG-ID>/test-results.md\` for full test output.

   ## Pipeline
   This PR was created by the \`bug_to_pr\` pipeline with full TDD,
   adversarial review, and automated validation."
   ```
4. **Capture PR number**: Extract from `gh pr create` output.
5. **Post bug report as PR comment**:
   ```bash
   gh pr comment <PR_NUMBER> --body-file bugs/<BUG-ID>/report.md
   ```

### Phase 4: ADVERSARIAL REVIEW

**CRITICAL ISOLATION PROTOCOL**: Do NOT write review files until BOTH reviewers complete.
Hold verdicts in memory (the orchestrator's context).

1. **Dispatch reviewer-alpha**:
   ```
   runSubagent(
     agentName: "bug-reviewer",
     prompt: "You are REVIEWER-ALPHA for bug fix <BUG-ID>.

              Review this bug fix independently:
              1. Read the bug report: bugs/<BUG-ID>/report.md
              2. Read the test results: bugs/<BUG-ID>/test-results.md
              3. Run: git diff main...HEAD (to see code changes)
              4. Read the changed source files for full context

              Evaluate against the 5-point checklist:
              1. Root cause addressed
              2. No regressions introduced
              3. Test evidence sufficient
              4. Edge cases covered
              5. Fix is minimal

              Produce a structured verdict ending with:
              ## Verdict: APPROVE  or  ## Verdict: REJECT

              ISOLATION: Do NOT read bugs/<BUG-ID>/reviews/beta.md
              (it should not exist yet — but do not attempt to read it)."
   )
   ```
2. **Capture alpha verdict**: Store the full response text in memory. Extract the
   `## Verdict:` line. Do NOT write to disk yet.

3. **Dispatch reviewer-beta**:
   ```
   runSubagent(
     agentName: "bug-reviewer",
     prompt: "You are REVIEWER-BETA for bug fix <BUG-ID>.

              Review this bug fix independently:
              1. Read the bug report: bugs/<BUG-ID>/report.md
              2. Read the test results: bugs/<BUG-ID>/test-results.md
              3. Run: git diff main...HEAD (to see code changes)
              4. Read the changed source files for full context

              Evaluate against the 5-point checklist:
              1. Root cause addressed
              2. No regressions introduced
              3. Test evidence sufficient
              4. Edge cases covered
              5. Fix is minimal

              Produce a structured verdict ending with:
              ## Verdict: APPROVE  or  ## Verdict: REJECT

              ISOLATION: Do NOT read bugs/<BUG-ID>/reviews/alpha.md
              (it should not exist yet — but do not attempt to read it)."
   )
   ```
4. **Capture beta verdict**: Store the full response text in memory. Extract the
   `## Verdict:` line.

5. **NOW write both review files** (only after both reviewers have completed):
   ```bash
   # Write alpha's review
   cat > bugs/<BUG-ID>/reviews/alpha.md << 'REVIEW_EOF'
   <alpha's full response text>
   REVIEW_EOF

   # Write beta's review
   cat > bugs/<BUG-ID>/reviews/beta.md << 'REVIEW_EOF'
   <beta's full response text>
   REVIEW_EOF
   ```

6. **Post verdicts as PR reviews**:
   For each reviewer (alpha, then beta):
   - Parse `## Verdict: APPROVE` or `## Verdict: REJECT` from the review text.
   - If **APPROVE**:
     ```bash
     gh pr review <PR_NUMBER> --approve --body "## Reviewer <Alpha/Beta> — APPROVE

     <reviewer's full verdict text, truncated to key findings>"
     ```
   - If **REJECT**:
     ```bash
     gh pr review <PR_NUMBER> --request-changes --body "## Reviewer <Alpha/Beta> — REJECT

     <reviewer's full verdict text with rejection reasons>"
     ```

7. **Commit review artifacts**:
   ```bash
   git add bugs/<BUG-ID>/reviews/
   git commit -m "chore: add review verdicts for <BUG-ID>"
   git push
   ```

### Phase 5: MERGE GATE

1. **Parse verdicts**: Check both reviews for `## Verdict: APPROVE` or `## Verdict: REJECT`.

2. **If BOTH approve**:
   - Write verdict summary:
     ```bash
     echo '{"merge_allowed": true, "alpha": "APPROVE", "beta": "APPROVE"}' > bugs/<BUG-ID>/verdict.json
     ```
   - Ask the user:
     ```
     ask_questions: "Both reviewers approve the <BUG-ID> fix. Merge PR #<number>?"
     Options: "Yes, merge" / "No, don't merge"
     ```
   - If user approves:
     ```bash
     gh pr merge <PR_NUMBER> --merge --delete-branch
     ```
   - If user declines: report status, do NOT merge.

3. **If EITHER rejects**:
   - Write verdict summary:
     ```bash
     echo '{"merge_allowed": false, "alpha": "<verdict>", "beta": "<verdict>"}' > bugs/<BUG-ID>/verdict.json
     ```
   - Present rejection reasons to the user.
   - If fix-review cycle count < 2:
     ```
     ask_questions: "Reviewer(s) rejected. Re-enter fix phase with feedback?"
     Options: "Yes, retry fix" / "No, stop pipeline"
     ```
     - If retry: increment cycle count, go back to **Phase 2** with rejection feedback
       included in the fixer prompt. Push new commits to the same branch. Re-run reviews.
     - The PR is automatically updated when new commits are pushed.
   - If max cycles (2) reached: report all rejection reasons, stop pipeline.

4. **Clean up** (on success):
   ```bash
   git add bugs/<BUG-ID>/verdict.json
   git commit -m "chore: add verdict for <BUG-ID>"
   git push
   ```

---

## Fix-Review Cycles

The pipeline allows **maximum 2 fix-review cycles**:

- **Cycle 1**: Phase 2 (fix) → Phase 3 (PR) → Phase 4 (review) → Phase 5 (gate)
- **Cycle 2** (if rejected): Phase 2 (re-fix with feedback) → push to same branch →
  Phase 4 (re-review) → Phase 5 (gate)

If still rejected after cycle 2, the pipeline stops and reports all rejection reasons.

On retry, include the rejection feedback in the fixer prompt:
```
"RETRY FIX for <BUG-ID>. Previous fix was rejected by reviewer(s).

Rejection reasons:
<alpha's rejection reason, if any>
<beta's rejection reason, if any>

Address these specific issues in your updated fix plan."
```

## Report

After the pipeline completes (success or failure), present this report:

```
## Bug-to-PR Pipeline Complete

**Bug ID**: <BUG-ID>
**Description**: <brief from user's input>
**Module**: <routed module>
**Status**: Merged | Rejected | Stopped by user

### Phase Results
| Phase | Status | Details |
|-------|--------|---------|
| 0. Setup | Complete | Branch: fix/<bug-id> |
| 1. Triage | Complete | Report: bugs/<BUG-ID>/report.md |
| 2. Fix | Complete | Plan: specs/fix-<bug-id>.md |
| 3. PR | Complete | PR #<number>: <url> |
| 4. Review | Complete | Alpha: <verdict>, Beta: <verdict> |
| 5. Gate | <result> | <merge status or rejection reason> |

### Review Verdicts
- **Reviewer Alpha**: APPROVE/REJECT — <summary>
- **Reviewer Beta**: APPROVE/REJECT — <summary>
- **Test Evidence**: Confirmed by both / Issues noted

### Fix-Review Cycles
- Cycle 1: <outcome>
- Cycle 2: <outcome, if applicable>

### PR Artifacts Posted
- [x] Bug report as PR comment
- [x] Alpha verdict as PR review
- [x] Beta verdict as PR review
- [x] Test evidence in bugs/<BUG-ID>/test-results.md

### Final Status
<one-line summary>
```

## Rules

1. **NEVER implement code yourself.** All investigation → `bug-creator`. All routing → `bug-router`.
   All fix planning → `bug-fixer-{module}`. All implementation → `builder`. All validation → `validator`.
   All review → `bug-reviewer`.
2. **NEVER skip validation.** Every builder task gets a validator dispatch.
3. **NEVER write review files before both reviewers complete.** Hold verdicts in memory.
   This is the core isolation guarantee.
4. **NEVER merge without both reviewers approving AND user confirmation.**
5. **Max 2 fix-review cycles.** If still rejected, stop and report.
6. **Max 2 fix cycles per builder task** during Phase 2b (same as build.prompt.md).
7. **Checkpoint every 3 builder tasks** during Phase 2b.
8. **Use `ask_questions` for user decisions** — merge confirmation and retry decisions.
9. **All PR artifacts must be posted.** Bug report as comment, verdicts as reviews.
10. **Use the todo list** to track pipeline progress across all phases.
11. **If a sub-agent fails**, handle it (retry with adjusted prompt, use defaults for routing).
    Do NOT stop the pipeline on a single agent failure unless it's unrecoverable.

## Prerequisites

- `gh` CLI must be authenticated: `gh auth status`
- Git must be configured with user name and email
- The repository must have a remote named `origin`

If any prerequisite fails in Phase 0, report it to the user and stop.

