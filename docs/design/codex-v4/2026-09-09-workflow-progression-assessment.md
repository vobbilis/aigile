---
title: Codex v4 Workflow Progression Assessment
description: Distinguish architectural progress, tested runtime behavior, and pending instruction-policy changes.
---

# Workflow Progression Assessment

## Executive Summary

The work has progressed from model-managed coordination toward a code-owned
workflow that delegates reasoning and tool work to Codex. This preserves the
hardening in the Claude v4 flows without assuming native orchestration supplies
their acceptance semantics. The runtime implementation remains Phase 0.

Two changes need separate judgments: moving enforcement out of prompts has
substantially landed in the design; relaxing unnecessary implementation and
skill prescriptions has only partially landed. The latter is not a prerequisite
for the former and should not weaken failure coverage.

## Scope and Evidence

This assessment compares the home-directory Claude planner/builder and team
builder/validator definitions read in this conversation with the current
[Codex plan](../codex-v4-native-orchestration-plan.md),
[first review](2026-09-09-native-orchestration-review.md),
[follow-up review](2026-09-09-revised-plan-review.md),
[checkpoint](2026-09-09-implementation-checkpoint.md), and
[runtime package](../../../codex-v4/README.md).

The v4 package and design documents are untracked in Git. This is a comparison
of documented states, not a reconstructed commit history. It is not a full
security audit or a live-provider certification. No command or implementation
file was changed for this assessment.

Proposed flow: requirements -> grounded spec and manifest -> controller-owned
dependencies and attempts -> workers -> executable and semantic checks ->
integration -> final gate -> separate documentation and routing evidence.

Implemented flow: configuration -> schema inspection -> owned App Server ->
handshake and catalog discovery -> optional synthetic read probe -> incomplete
certification report. The CLI exposes only `doctor`.

## Progression by Responsibility

| Concern | Claude v4 baseline | Current Codex direction | Status |
|---|---|---|---|
| Planning authority | Author verifies grounding and adjudicates critics | Retains direct pin verification, conditional panel, and recorded adjudication | Designed |
| Coordination | Agents discover and claim tasks; lead interprets messages | Controller owns dependency graph, dispatch, and acceptance | Designed |
| Worker continuity | Persistent teammates with idle polling and heartbeats | Persistent root threads receive turns only when work is ready | Designed |
| Completion | Completed status can also represent failure | Separates logical task, attempt, final gate, and evidence outcomes | Designed |
| Repair | Generated fix and revalidation tasks | Stable task identity, retained failed attempt, persisted two-cycle budget | Designed; final-gate correction remains unresolved |
| Test guarantees | Named promises checked by validator | Framework-qualified identities reconciled with actual results | Designed; Rust support missing from initial adapter scope |
| Evidence | Updaters rerun checks and write reports | Fresh second pass on sealed code; separate documentation tree | Designed |
| Routing lessons | Lead assessment and binding-specific prose ledger | Attributed raw events and deterministic policy reduction | Designed; matched-baseline comparisons unresolved |
| Permissions | Tool restrictions and role instructions | Explicit runtime permission profiles plus independent checks | One read boundary reported verified; full suite pending |
| Runtime protocol | Harness-specific team primitives | JSONL client with request correlation, deadlines, denial, cleanup | Implemented and contract-tested |

Native worker-spawned descendants remain disabled in the proposed initial
implementation. This is deliberate: the application owns orchestration rather
than allowing two independent schedulers to manage the same work.

## Remaining Findings

### High: Final-Gate Correction Still Lacks Complete State Semantics

Plan sections 8.2 and 8.7 still make `PASSED` terminal while sending final-gate
failures back through retained failed-attempt repair. Once P1 and its consumer
P2 have integrated, fixing P1 from its old tree can omit P2. Prior acceptance
evidence may no longer describe the corrected code.

The follow-up review correctly requests correction from the current integration
tree, explicit evidence invalidation, affected rechecks/reviews, and crash
recovery. That contract remains pending, not implemented.

### Medium: The New Plan Hardens a Test-Count Heuristic

Sections 3.1 and 6.4 promote the Claude warning about fewer than 30% failure-path
tests into a hard gate with a maintainer exception. This is explicitly labeled,
but it moves opposite to the discussed risk-based policy. Ratios depend on how
tests are split, parameterized, and classified; they do not establish adequacy.

Keep stable failure IDs, expected outcomes, executed-test reconciliation, and
semantic adequacy review. Decide separately whether the percentage remains a
warning. Do not weaken boundary, adversarial, concurrency, or recovery tests
where the behavior requires them.

### Medium: Source-Workflow Language Parity Remains Incomplete

Section 6.4 initially supports Python/TypeScript source checks and pytest/Vitest
results, while the source planner specifies Rust/Cargo workloads. The runtime
prototype need not support Rust yet, but the delivered equivalence claim needs
a Rust adapter or an explicit scope exception.

### Medium: Successful Repair Does Not Establish Relative Model Capability

Sections 11.4 and 11.5 still permit a lower-fail/higher-pass pair on an unchanged
task to generate a promotion rule. The higher route may inherit partial work and
diagnostic findings. Recovery success is useful evidence, but not a controlled
comparison. Record starting-tree and handoff digests and require matched
conditions before deriving a capability rule.

## Instruction and Skill Policy

| Earlier discussion | Current artifact | Assessment |
|---|---|---|
| Keep mandatory gates outside model instructions | Executable controller; wrappers cannot bypass gates | Adopted in design |
| Separate locked constraints from implementation freedom | DESIGN_GROUNDING explicitly names the distinction | Partial: task-level permitted discretion and escalation need a concrete contract |
| Do not prescribe universal RED/GREEN ceremony | Section 8.7 makes RGR evidence optional unless explicitly required | Adopted in design; retains the source planner's conditional approach |
| Keep material failure coverage, not category quotas | Failure-to-test traceability plus a stronger 30% threshold | Mixed; traceability improves, quota gets stricter |
| Load domain skills selectively | Skills appear primarily as optional CLI wrappers | Not yet specified for worker context loading |
| Let workers surface invalid assumptions | Worker output includes `blocking_issue` | Partial: reporting exists, but the approval/replanning path needs definition |
| Replace polling and shutdown prompt recipes | Event-driven lifecycle and durable records | Adopted in design, not yet implemented |

Calling skills advisory does not answer which domain guidance a builder receives.
A later policy should distinguish always-applicable safety rules, task-relevant
knowledge, and optional procedures. Skill file count is not a quality metric.

## Engineering Assessment

### Security

The launcher rejects credential-bearing provider fields and limits the bridge
to a local Responses endpoint. The doctor rejects server requests and uses a
synthetic sentinel rather than real credentials. These are bounded probe
behaviors, not proof of a production worker sandbox. Write/network enforcement,
symlink escape checks, and worker-role isolation remain uncertified.

### Correctness

The largest design improvement is separating execution completion from
acceptance. Persisted task/attempt identities and the final gate remove the need
to interpret prose messages as authority. The remaining post-integration repair
gap is consequential because it affects evidence validity, not just scheduling.

### Performance and Scalability

No-idle-inference dispatch and bounded handoffs target known sources of token
waste and context growth. No workload benchmark establishes savings yet.
Serial writes are a deliberate initial limit; parallel writers remain gated by
conflict and crash tests. Do not describe this as a measured speedup.

### Maintainability

Separating workflow policy from the harness transport permits replacement of
runtime mechanisms without rewriting acceptance rules. The tradeoff is ownership
of a real software system: schemas, adapters, durable state, and protocol upgrades.
Moving a heuristic into deterministic code makes it reliable, not necessarily
correct; policy still requires independent justification.

### Observability

The design records requested/observed routes, tree hashes, outcomes, and evidence
digests. The implementation only retains notification method names and sanitized
failures. Full worker-event persistence and the live status view remain planned.

### Testing and Runtime Evidence

Fresh local verification during this assessment:

- Contract suite: **31 passed in 1.48s**.
- Ruff: **All checks passed!**
- Ruff format: **11 files already formatted**.

The suite exercises a real child-process fixture server, including out-of-order
response correlation, server-request denial, malformed responses, EOF, deadlines,
and owned-child cleanup. The captured 0.144.1 schema regression and synthetic
probe policy tests also pass. These tests do not execute planner/build workflows.

The checkpoint reports live handshake, five-model discovery, and a successful
named-profile read boundary on Codex 0.144.1. This assessment did not rerun those
live checks. The correction from legacy `readOnly.access` to `permissionProfile`
illustrates the intended approach: retain the security obligation, adapt the
mechanism to observed runtime behavior, and avoid treating schema presence alone
as enforcement proof.

## Architecture Comparison and Improvement Opportunity

The Claude flow uses a model lead and team messages to coordinate. The revised
Codex design follows the durable-workflow pattern: application code owns state,
while workers provide proposed results and evidence. Native lifecycle support
supplies mechanisms, not the custom SDLC acceptance contract.

The highest-leverage opportunity is to turn each past hardening incident into a
behavioral acceptance scenario for the controller. That can preserve the reason
for a workaround while permitting a different runtime implementation. No evidence
supports a quantified 10x improvement or cross-vendor capability ranking.

## Recommended Next Decisions

1. Keep Phase 0 certification as the immediate execution boundary; do not enable
   autonomous writes on the strength of catalog discovery or one read check.
2. Resolve final-gate correction before implementing the builder state machine.
3. Decide the 30% ratio policy before implementing static validation, so the new
   controller does not permanently encode an unintended strengthening.
4. Specify locked/discretion/escalate fields and role-specific knowledge loading
   before generating production worker prompts. Preserve literal instructions
   for genuinely mechanical tasks.
5. Include Rust/Cargo in the equivalence target or record an approved restriction.
6. Resolve matched-baseline learning before activating automatic promotion rules.

The direction is not "trust the harness more and test less." It is "ask models
to manage less bookkeeping, preserve engineering judgment, and verify more of
the workflow independently." That architectural change is explicit; the working
implementation and the instruction-policy revision have further steps to go.