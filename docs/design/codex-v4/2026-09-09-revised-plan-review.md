---
title: Codex v4 Revised Plan Review
description: Follow-up assessment of workflow parity and the integration of recommendations R1-R8.
---

# Codex v4 Revised Plan Review

## Assessment

The revision substantially incorporates the first review. R1-R8 now map to
implementation phases and acceptance scenarios, and the parity table makes
intentional adaptations visible. Keep the architecture. Address the three
remaining issues below before implementing their affected paths; Phase 0
runtime certification remains a reasonable next step.

This is a source-level design review, not a runtime certification. No provider
requests, controller tests, or workflow executions ran. The proposed plan and
the user's Claude commands remain unchanged by this review.

## Remaining Findings

### High: Final-Gate Repairs Need a Post-Integration Contract

[Section 8.7](../codex-v4-native-orchestration-plan.md#L1071) maps final
validate-all failures back to affected logical tasks, but
[section 8.2](../codex-v4-native-orchestration-plan.md#L871) makes PASSED terminal.
The repair rules describe an unintegrated failed attempt tree. At final
validation, however, all original tasks have already passed and integrated;
there may be no failed task tree to retain. Downstream tasks may also have
passed against the original implementation.

For example, P1 introduces an API, P2 consumes it, and final validation discovers
that the API needs correction. Reusing P1's original tree omits P2. Reopening P1
without invalidating acceptance evidence leaves P2 marked passed against an
outdated prerequisite. The promise to rerun validate-all helps, but does not
define legal task transitions, repair baselines, or the validity of prior
task-level checks and semantic approvals.

**Recommendation:** distinguish pre-integration retry from post-integration
correction. For final-gate repairs, start from the current integration tree,
create a recorded corrective attempt/owner with explicit scope, and invalidate
the affected acceptance evidence. Define which task checks and reviews rerun,
how accepted corrective commits relate to original tasks, and which states
permit the correction without rewriting history. Preserve the shared repair
budget and rerun the final gate before wave two.

**Acceptance:** P1 and P2 pass and integrate; final validation fails; a repair
changes P1's API; P2's affected checks/review run again; final validation passes.
Crashes before and after corrective integration must preserve both the original
history and the outstanding invalidation state. Also cover final-only failures
that map to an integration owner rather than one original task.

### Medium: Initial Adapters Exclude the Source Workflow's Rust Specs

[Section 6.4](../codex-v4-native-orchestration-plan.md#L622) initially supports
pytest/Vitest results and Python/TypeScript symbol verification. The same
section rejects promises without supported adapters. The reviewed Claude
planner explicitly produces Rust type signatures and Cargo validation commands;
its Stop hook even requires a Rust signature block.

Consequently, the first implementation could satisfy its Python/TypeScript
fixtures while rejecting the Rust/Cargo workload represented by the source
commands. The normative parity table and definition of done do not identify
this language restriction as a deferred capability.

**Recommendation:** include Rust source verification and a supported Cargo-test
result path in the initial equivalence target, with explicit toolchain and
report-format versions. Alternatively, obtain an explicit scope decision and
label Python/TypeScript delivery a partial port. Do not require the Rust adapter
to exist in the first internal prototype, but make it a gate for the claimed
source-workflow equivalent.

**Acceptance:** a representative source-style Rust spec can be expressed in the
new manifest and built end to end. Verify promised signatures and named test
outcomes, including failed, ignored, filtered, and duplicate identities. State
how Cargo unit, integration, documentation, compile-fail, and other promised
test categories are supported or explicitly excluded.

### Medium: Promotion Lessons Need Equivalent Starting Conditions

[Section 11.4](../codex-v4-native-orchestration-plan.md#L1469) permits an
UNDER_PROVISIONED verdict when a lower route fails and a promoted route passes
the unchanged task. However, [section 8.7](../codex-v4-native-orchestration-plan.md#L1051)
deliberately gives a repair the previous attempt's partial implementation and
finding evidence. An unchanged task definition is not an unchanged experiment:
the second model may only need to finish the first model's work.

This does not undermine promotion as a practical recovery action. It weakens
the inference that the first model lacked capability and the second model's
tier was necessary. One such pair can currently generate a narrow automatic
promotion rule under section 11.5.

**Recommendation:** record starting-tree, handoff, findings, and tool/prompt
contract digests for every compared attempt. Separate successful assisted
recovery from evidence of relative capability. Require a same-baseline replay
or other explicitly justified matched comparison before deriving a capability
rule; retain ordinary repair outcomes as observations without that inference.

**Acceptance:** lower-model partial work followed by higher-model repair does
not by itself create an UNDER_PROVISIONED rule. A matched replay can qualify
under the recorded policy. Environmental, prompt, and inherited-work differences
remain visible as confounders rather than disappearing behind one task ID.

## Prior Recommendations

| Recommendation | Revision assessment |
|---|---|
| R1 Persistent event-driven workers | Incorporated: retained threads, no idle inference, explicit replacement and handoff. |
| R2 Distinct completion and acceptance | Incorporated: separate task, attempt, final-gate, code, and evidence outcomes. |
| R3 Stable repairs | Pre-integration path corrected; final-gate corrective work still needs the contract above. |
| R4 Durable conservative recovery | Incorporated: ambiguity handling and expanded crash boundaries; extend them to final-gate corrections. |
| R5 Promise reconciliation | Incorporated: stable identities, result/source adapters, outcome policy, and independent second pass; Rust parity remains open. |
| R6 Enforced role boundaries | Incorporated at design level: restricted reads, denied approvals, sandboxed checks, and attack tests; still requires runtime proof. |
| R7 Actual route verification | Incorporated: per-attempt identity, TTL, fallback ceilings, and mixed/single-backend tests; capability learning needs matched baselines. |
| R8 Runtime-evidence visibility | Incorporated: live projection, reconnect, explicit headless mode, and stale-state handling. |

The original ordered-scope contradiction is resolved. Conditional critics,
source critic classes, direct pin verification, the second verification pass,
and living Current Design write-back are now explicit. The 30% hard threshold
is correctly labeled as a strengthening, and the provider-policy question is
resolved in favor of both local/on-prem and frontier models.

## Recommendation

Proceed with runtime certification, then close the affected design contracts
before builder and learning implementation. This is refinement of a viable
workflow, not a reason to redesign it or expand it into a larger platform.