---
name: build-v4
description: "Use when asked to execute a v4 spec using native Codex subagents. Coordinate persistent builders, validation, two independent reviews, evidence and design updates, then a final audit. Do not substitute test results for review."
---

# Build v4

## Invocation And Help

Check the current invocation before any workflow step. With no arguments, or
with only `help`, `-h`, or `--help`, display the usage below and STOP. Do not use
earlier conversation context to supply missing arguments. Do not use tools after
loading this skill, explore the repository, ask follow-up questions, edit files,
run tests, or spawn agents in help mode.

```text
Usage: $build-v4 <spec-path>

Execute an existing v4 spec using native builders, validation, two independent
reviews, specification and design updates, and a final audit.

Example: $build-v4 specs/csv-export-v4.md
Create a spec first: $plan-to-build-v4 <requirements> [design: <path>]
```

## Preflight

1. Read the provided spec and project instructions. Ask if no spec is supplied.
   Check all planner sections, task ownership, dependencies, model classes,
   validation commands, test identities and current source baseline. Resolve
   drift before building. Preserve existing dirty work.
2. You coordinate; only builders change source and tests. Never modify Claude
   files, home configuration or credentials. No commits, branches or service
   restarts without explicit user approval.
3. Confirm native agent spawning is available. If unavailable, STOP with BLOCKED;
   do not impersonate agents in a single conversation. Announce the agent roles,
   requested model binding and native thread presentation. Do not claim tmux panes.
   Use registered roles with `fork_context=false`. Do not substitute default agents
   when a required role fails to load; report BLOCKED with the runtime error.
   Do not infer effective permissions from role TOMLs. On Codex 0.144.1 native
   v1 children inherit the parent's permission profile even when their role says
   `read-only`. Disclose that validators/reviewers/auditors are instructed not to
   write but lack separate filesystem enforcement in a workspace-write session.
   If the caller requires enforced per-role read-only access, report BLOCKED;
   do not silently weaken that requirement or bypass the sandbox.
4. Use supplied class-to-model bindings on spawn when supported. Otherwise announce
   a single-model run and record inherited settings. Confirm requested versus
   runtime-reported models where the native trace exposes them. A model's own
   assertion is not routing evidence. Unknown physical backend stays UNKNOWN.
   A dead route permits only a documented promotion under the spec's policy;
   no live REASONING route or an unsupported explicit binding means BLOCKED.
5. Create a build record in `specs/<spec-name>-run.md`: task status, agent IDs,
   attempts, reports, commands and final outcome. Record actual native thread IDs
   from spawn results, not invented IDs. Use the native plan/task display for
   progress. This record supports inspection; it is not a crash-safe scheduler.

## Builders And Validation

Spawn `v4-builder` once per assigned builder. Keep the returned IDs. Send complete
task instructions, design constraints, allowed files and test identities. Dispatch
only dependency-ready work; parallelize disjoint tasks. Serialize overlapping files.
Do not delegate ownership of the same task to multiple builders.

Use `send_input` to give an existing builder its next task or repair. Use `wait`
for completion; do not generate idle heartbeat or sleep loops. Retain builders
until review finishes. If native limits prevent retaining a worker, record the
loss of continuity and ask before substituting a new worker.

After implementation, ask a separate `v4-validator` to execute the specified
commands and reconcile every promised test with actual results. The validator
reports PASS, FAIL or BLOCKED and does not review design or approve the build.
Missing, skipped and failing promised tests are not passes. Verify all acceptance
criteria, including manual checks explicitly listed in the spec.

Send failures to the original builder with evidence and the affected task ID.
Allow at most two repair cycles per logical task, including review-driven repairs;
retain previous attempts. Work from the current tree, not an old pre-integration
copy. Re-run affected tests and dependent checks after every repair. When the
budget is exhausted report FAILED. For a conflicting requirement, stop with
NEEDS_DECISION: evidence, affected task, proposed resolution. Do not change the
requirement or quietly increase the budget.

## Two Independent Reviews

After validate-all passes, spawn TWO distinct `v4-reviewer` agents in parallel:
`reviewer-alpha` and `reviewer-beta`. Give both the spec, changed-file list,
baseline and validation evidence. Do not include either reviewer's findings in
the other's initial prompt. Neither reviewer is the builder or validator.

Both independently review correctness, security, compatibility, design compliance,
failure handling and test adequacy. Each returns APPROVE or REJECT, with concrete
findings. Wait for both. Record both thread IDs and unedited verdicts.
Do not write one review to a shared file until both initial reviews return.
Separate threads avoid initial report sharing; they do not prove filesystem isolation.

Any unresolved rejection blocks approval. Send repairs to the original builder,
then repeat affected validation and obtain both reviewers' approval on the updated
tree. A passed command or completed thread never substitutes for either review.

## Evidence And Design Updates

Only after validation and both reviews approve:

- Spawn `v4-spec-updater` to re-run validation commands and replace Build Evidence
  with actual outcomes, acceptance evidence, changed files, deviations and routing
  observations. Record failures honestly. Status remains pending final audit.
- Spawn `v4-design-updater` to update the named design document from actual source
  and current build changes, not `HEAD~1` assumptions. Every implementation claim
  needs a file reference. Run these two agents concurrently only for disjoint files.
- Spec-updater appends evidence-based lessons to the repository-local
  `docs/design/codex-routing-ledger.md`. Record model identity uncertainty and
  inherited partial work; a successful repair alone does not prove model superiority.

Wait for both. Missing or failed updates mean INCOMPLETE, not COMPLETE.
Do not allow documentation agents to change code or tests.

## Final Audit And Report

Before spawning the auditor, close finished documentation agents and reviewers
after preserving their complete reports. Retain the builder until review and
validation finish. Account for the runtime's active-thread limit before each spawn;
do not count a failed spawn as an executed role or discard a required stage.

Spawn a fresh `v4-auditor` after both updaters finish. Provide the spec, build record,
two review reports, validation output and updated design. The auditor checks that
every required role ran, findings have dispositions, evidence matches current code,
the second command pass happened, and documentation reflects the implementation.
Ask it to flag missing reports rather than infer success. It returns PASS or FAIL.
The auditor can inspect supplied artifacts; it cannot authenticate a fabricated
report without an independent runtime trace. Preserve that trace during experiments.

Report COMPLETE only after audit PASS and no unresolved decisions. Otherwise name
the failing or missing stage. Append the audit outcome to the build record, close
completed native agents, and list changed files, checks, both review verdicts,
updater outcomes, audit verdict, repair counts and known routing limitations.