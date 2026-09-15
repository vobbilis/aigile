---
name: plan-to-build-v4
description: "Use when asked to create a design-grounded v4 implementation plan for native Codex agents. Planning only; do not implement. Includes conditional critics, model classes, named tests, and distinct validation, double review, documentation, and audit stages."
---

# Plan To Build v4

## Invocation And Help

Check the current invocation before any workflow step. With no arguments, or
with only `help`, `-h`, or `--help`, display the usage below and STOP. Do not use
earlier conversation context to supply missing arguments. Do not use tools after
loading this skill, explore the repository, ask follow-up questions, edit files,
run tests, or spawn agents in help mode.

```text
Usage: $plan-to-build-v4 <requirements> [design: <path>] [panel: auto|on|off]

Create a design-grounded implementation spec without implementing it.
Provide the feature requirements and an existing design path when available.
panel: auto uses four critics for medium/complex work; on always runs them;
off skips the panel. Default: auto.

Example: $plan-to-build-v4 Add CSV export. design: docs/design/export.md panel: on
Next: $build-v4 specs/<generated-name>-v4.md
```

## Inputs And Boundaries

Read the user's requirements and grounding pointer. Ask for missing inputs.
Work in the current repository. Do not modify Claude commands, home settings,
credentials, source code, or tests. Do not commit or create branches.
Use native Codex subagents only for the critics below. You remain the plan author.

## Grounding

1. Read the cited design, ADRs, relevant source, project instructions, and tests
   yourself. Verify references at the current working tree, including dirty work.
2. If no design exists, write a bounded design document before the spec. State
   assumptions and ask about unresolved public behavior. Do not invent APIs.
3. Read `docs/design/codex-routing-ledger.md` when present. Apply only lessons
   matching the recorded model binding and task conditions; otherwise label them
   conditional. Missing ledger means no prior evidence, not permission to invent it.
4. Separate locked requirements and public interfaces from private implementation
   discretion. Record when a builder must ask for a decision. Literal MECHANICAL
   tasks allow no design choices; STANDARD and REASONING tasks allow bounded choices.

## Write One Spec

Save `specs/<name>-v4.md` in small sections. Include:

- Status DRAFT, date, complexity simple/medium/complex, baseline commit and dirty
  file summary. State which source files the baseline covers.
- `## Design Grounding`: verified references, locked decisions, amendments,
  implementation discretion, and escalation conditions.
- `## Scope`: what is built and what is explicitly deferred.
- `## Type Surface`: required public interfaces, compatibility and proposed file
  locations. Do not prescribe private details without a design reason.
- `## Test Promises`: stable test identities, commands, expected results, failure
  conditions covered. Parameterized/property tests are valid. Cover material
  failures; do not substitute a fixed failure-test percentage for coverage.
- `## Step by Step Tasks`: stable IDs, assigned agents, dependencies, write paths,
  acceptance criteria, test promises, model class, and decision boundaries.
- `## Model Routing`: each agent's MECHANICAL/STANDARD/REASONING class and task-based
  rationale. One class per persistent builder. Models are supplied at execution.
  Promotions require recorded evidence; never silently demote or invent a binding.
- `## Acceptance Criteria` and `## Validation Commands`: exact commands, working
  directories, necessary dependencies and manual checks. Use the installed project
  toolchain, not assumed global tools.
- `## Team Orchestration`: builders, validator, reviewer-alpha, reviewer-beta,
  spec-updater, design-updater, auditor. Include a final validate-all task.
  Both reviews follow validation, repairs repeat affected validation and reviews,
  documentation follows approval, and the auditor checks the final artifacts.
- `## Plan Review Panel`: critic results and author decisions, or explicit skip.
- `## Build Evidence`: empty until execution. Never mark it complete at plan time.

Require regression reproduction before a bug fix. Use RED/GREEN evidence where it
tests a meaningful requirement; do not add ceremony for trivial literal edits.
Verify all task dependencies, ownership, interfaces and promised tests agree.

## Conditional Critic Panel

For medium/complex work, spawn four `v4-plan-critic` agents in parallel; also run
them for simple work when the user specifies `panel: on`. Skip only for simple
work or explicit `panel: off`, recording the reason.

Use registered custom roles with `fork_context=false`. A full-history fork cannot
select a different role on Codex 0.144.1. Do not substitute default agents when a
required role fails to load; report BLOCKED with the actual runtime error.
On Codex 0.144.1 native v1 children inherit parent filesystem permissions even
when a role declares `read-only`. Do not claim enforced critic write protection
inside a workspace-write planning session. If such protection is required, stop
with BLOCKED instead of treating a prompt instruction as a filesystem restriction.

Give each critic the saved draft, grounding paths and exactly one charter:
failure-surface (REASONING), grounding (MECHANICAL), omissions (REASONING), or
routing (STANDARD). Use supplied class bindings when supported; otherwise report
that the run inherits the session model. Do not call inherited routing mixed-model.
Wait for all four. Each returns numbered findings with severity, reference,
evidence and suggested correction. Accept and fix or reject with reasons; account
for every finding. Recheck consistency after edits. Close completed critics.

## Completion

Report the spec path, verified grounding, panel outcome and unresolved decisions.
The next command is `$build-v4 specs/<name>-v4.md`. Do not start building.