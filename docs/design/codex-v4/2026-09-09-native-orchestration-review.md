---
title: Codex v4 Native Orchestration Plan Review
description: Implementation-readiness review of the controller, recovery, enforcement, and validation contracts.
---

# Codex v4 Native Orchestration Plan Review

## Executive Summary

The acceptance baseline is behavioral equivalence to the user's Claude
`/plan_to_build_v4` and `/build_v4` commands, not a general orchestration platform.
The controller and App Server split is a plausible implementation of that
contract, not a requirement imposed by the source commands. Revise the recovery,
scope, permission, and test-evidence details without dropping the source workflow.
This review does not change the plan or certify either harness at runtime.

## Scope and Evidence

Reviewed the entire [proposed plan](../codex-v4-native-orchestration-plan.md),
the local Claude planner and builder command definitions, the v4 validator's
structural checks, and the current official
[App Server documentation](https://learn.chatgpt.com/docs/app-server).
The follow-up source study read both complete home-directory commands, both
planner Stop-hook validators, all four referenced home-directory team agent
definitions, and the complete routing ledger. Repository-local agent definitions
and hooks can alter deployed behavior; this study does not certify those
overrides. The referenced local Codex profile, catalog, and LiteLLM configuration
files exist. This review did not inspect credentials or run provider requests.

The intended data flow is requirements -> manifest -> controller-owned DAG ->
worker result and repository delta -> checks -> integration -> evidence and
routing events. In the proposed Codex controller, a worker response never
constitutes completion by itself. The Claude source instead lets builders mark
tasks completed and then relies on the independent validator for acceptance.

## Source Contract Study

### Planner Contract

| Source behavior | Required equivalence or explicit adaptation |
|---|---|
| Planning only; never deploy builders | Keep planning and execution as distinct user operations. |
| Author reads and verifies repository pins directly, without research subagents | The Codex plan's repository-study fan-out changes this rule; preserve author verification or explicitly justify the change. |
| Study first when grounding is absent; otherwise reuse locked design | Preserve conditional study and publication of needed design decisions before the spec. |
| One staged, self-contained spec with code baseline | Preserve recoverable authoring, full type shapes, target locations, failure inventories, named tests, exhaustive tasks, and acceptance criteria. A JSON manifest supplements this material, not replaces it. |
| Each nontrivial failure bullet maps to a named test | Preserve traceability from design to type to failure to test to task to result. |
| RED-GREEN-REFACTOR walkthrough is optional | Do not describe universal RED-before-GREEN evidence as an existing command-level hard gate. |
| Simple specs skip critics unless panel: on; medium/complex run unless panel: off | An unconditional four-critic panel is a changed cost and interaction contract. |
| Critics FSA/GRD/OMS/RTG use REASONING/MECHANICAL/REASONING/STANDARD respectively | The Codex plan changes three critic floors. Record those as routing changes, not a literal port. |
| Single author accepts or rejects each critic finding with reasons | Preserve recorded adjudication and consistency checks after revisions. |
| Classify task shape before partitioning agents | Preserve homogeneous agent assignments and scoreable routing rationales. |
| Read binding-specific RL lessons on every plan | The cross-build learning loop is core v4 behavior, not optional platform scope. |

### Builder Contract

| Source behavior | Required equivalence or explicit adaptation |
|---|---|
| Leader coordinates and does not implement | Keep implementation in workers. An external controller can replace leader bookkeeping. |
| Visible tmux agents by default; explicit consent for headless mode | Define visible worker progress and inspection. Generic logs alone do not establish presentation equivalence. |
| Deploy concurrent, persistent builders once; each claims only its assigned work | A fresh thread per task and a serial writer are deliberate runtime changes. Explain effects on context reuse, concurrency, and visibility. |
| Resolve abstract classes through launch-time bindings | Do not bake physical models into specs or require mixed backends for every valid run. The source permits single-backend bindings. |
| Probe teammates and recheck the first report's actual model | Preserve observed worker identity, not just announced route or lead environment. |
| Promote on unavailable slots, respecting per-spec caps | Preserve capped fallback and user escalation when no permitted live route remains. |
| Validator checks every command, acceptance criterion, type signature/annotation, and named test outcome | Whole-suite success alone is not equivalent. This is an existing source obligation, not a new feature request. |
| Validator creates assigned fixes and revalidation, with a two-cycle limit | Preserve the repair loop. Explicit controller transitions may improve the source's ambiguous completed-versus-passed state. |
| Wave two starts after successful validate-all | Defer actual deployment of evidence/design agents, not merely their writes. |
| Spec updater independently reruns commands and acceptance checks | Canonical evidence from cached run state alone omits the source's second verification pass. |
| Design updater rewrites Current Design and appends code-evidenced decisions | Append-only decision proposals alone omit living-design maintenance. |
| Lead judges routing; updater transcribes verbatim and appends RL lessons | Preserve the retrospective and planner-readable lessons even if automatic policy optimization waits. |
| Liveness monitoring, context re-anchoring, and owned-agent shutdown | Preserve operational continuity without copying Claude-specific team-file or pane manipulation. |
| Updater failure is best-effort and appears in the report | A mandatory evidence-completion gate strengthens the source contract; distinguish code success from evidence failure. |

### What the Hooks Actually Enforce

The planner's `validate_new_file` hook checks for a matching file modified in the
last 30 minutes. The `validate_v4_spec` hook selects the most recently modified
matching file and checks heading/field structure, Rust signature blocks, test
table rows, failure-category presence, and per-agent task-class homogeneity.

The 30% failure-path ratio is a warning, not a blocking threshold. The validator
requires at least one failure-inventory block when signals exist, rather than
proving a block for every type. It checks category presence globally rather than
proving every failure bullet maps to a test. It does not run promised tests or
mechanically verify the critic panel and every grounding pin. The author,
critics, and build validator carry those richer semantic obligations.

Consequently, the Codex plan's fail-closed schema and routing policy are stronger
enforcement proposals. Keep their benefits, but label them as changes rather than
claiming the Claude hooks already implement those guarantees.

### Source Inconsistencies to Resolve, Not Copy

- The home builder/validator definitions contain five-retry idle rules, while
  v4 deployment prompts require indefinite waiting and mailbox handling.
- The generic validator's fix-task template omits Assigned To, while the v4
  command requires assignment and builders filter strictly by their names.
- The generic spec-updater permits only spec edits, while the v4 deployment
  explicitly adds ledger append permission. Role scope needs one authority.
- The command marks validation completed even on failure, but its lost-message
  fallback can launch wave two after observing completed alone. Completion is
  not sufficient proof of a successful gate.
- A successful fix revalidation has a different task ID, while the normal
  wave-two trigger recognizes only validate-all. The controller must make a
  repaired validation satisfy the logical final gate explicitly.
- Home agent files default to opus, but v4 supplies the resolved model slot on
  deployment. File defaults alone do not describe the intended routing.

These are source-level tensions, not reproduced runtime failures. Do not change
the home commands as part of this study. The port should preserve their intended
contract while making precedence and success states explicit.

## Findings

### High: Repair Tasks Have No Runnable Dependency State

[Section 8.6](../codex-v4-native-orchestration-plan.md#L782) makes a fix task
depend on the failed task's integrated state. However, the
[scheduler](../codex-v4-native-orchestration-plan.md#L704) releases only PASSED
dependencies and integrates only passing work. If P1 fails its tests before
integration, repair F1 cannot depend on P1 without remaining blocked. The plan
also does not say how a successful F1 satisfies downstream dependencies on P1.

Keep the logical task separate from its attempts. A repair attempt should use
the failed attempt's retained tree, not a PASSED-only dependency edge. After a
repair passes the original gates, integrate it and mark the logical task PASSED.
Test P1 failure -> repair success -> P2 dispatch, including a crash at each step.
Define whether one fix cycle covers a batch of findings or each generated task.

### High: Security Promises Need Concrete Permission Profiles

The [role matrix](../codex-v4-native-orchestration-plan.md#L859) and security
section promise secret-read denial and artifact-only check writes. They do not
specify the App Server read restrictions, approval policy, or check-runner API
that implements those promises. Official documentation says readOnly and
workspaceWrite default to full read access unless restricted explicitly.
Read-only therefore does not, by itself, prevent credential reads.

Specify restricted readable roots, writable roots, environment isolation, and
approval-denial behavior for every role. Use sandboxed command/exec or a defined
external sandbox for checks; thread/shellCommand and process/spawn explicitly
run outside the Codex sandbox. Handle server-initiated approval and input
requests, including unattended rejection and cancellation. Treat Python, npm,
and other allowlisted programs as arbitrary-code execution, not a security
boundary. Certify these controls before the assisted-build rollout with tests
for credential reads, state-descriptor modification, and test-process writes.

### Medium: Scope Validation Rejects Legitimate Sequential Edits

The [static validator](../codex-v4-native-orchestration-plan.md#L475) rejects a
task that can write another task's scope. Yet
[worktree scheduling](../codex-v4-native-orchestration-plan.md#L759) serializes
overlapping scopes through generated dependencies. Under the former rule,
two dependent tasks that both edit the same source file never reach scheduling.

Distinguish permanently protected paths from concurrent ownership. Permit
ordered overlap; reject or serialize unordered overlap; revalidate the DAG after
adding edges. Test sequential overlap, concurrent overlap, and repair-task scope
inheritance. Do not make task scopes globally disjoint.

### Medium: Test Promises Lack Execution-Level Reconciliation

The [manifest](../codex-v4-native-orchestration-plan.md#L420) maps a named test
promise to a command ID. A whole-suite command can exit successfully while a
promised test is missing, skipped, renamed, or excluded. Counting declared
failure-path promises does not establish that those tests ran. Semantic review
helps, but cannot supply the claimed deterministic guarantee.

The full Claude build command already requires its validator to verify each
promised test exists, runs, and passes. The port needs to retain this obligation;
structured result reconciliation is a proposed enforcement mechanism for it.

Define framework-specific test identities and consume machine-readable results.
Require every promised identity to exist and produce an allowed outcome; make
skip and expected-failure exceptions explicit. Preserve adequacy review because
a test name or category cannot prove its assertions are meaningful. Include
missing, skipped, filtered, duplicate, and renamed-test fixtures. State whether
the port guarantees RED-before-GREEN evidence or only final validation.

## Strong Controller Recommendations

Strongly recommend adopting R1-R8 in the implementation design. These are
review recommendations, not implemented or runtime-certified capabilities.
Several already appear in the proposed plan; the recommendation is to make
their behavior and acceptance checks explicit, not add a second mechanism.
Resolve R2-R7 before autonomous repository writes. Include R1 and R8 in the
delivered workflow so reliability does not sacrifice efficiency or visibility.

Preserve the division of responsibility: models design, build, critique, and
make semantic assessments; the controller schedules work, enforces boundaries,
collects evidence, and applies gate policy. A model's verdict remains an input
to that policy, never an unrestricted state-transition command.

### R1: Event-Driven Scheduling with Persistent Workers

**Strong recommendation:** retain a conversation per logical worker and
dispatch turns when assigned work becomes ready. Let controller code track
dependencies, inactivity, deadlines, and process health. Do not invoke a model
to poll a task list or generate idle heartbeats. Preserve parallel execution
for independent workers; removing polling does not require serializing them.

**Preserves:** stable worker identity, context across assigned tasks,
model-homogeneous assignments, and reactive repair work.

**Acceptance:** a blocked worker receives no inference requests solely for
waiting. Dependency completion releases its task once; duplicate notifications
do not cause duplicate dispatch. Consecutive tasks reuse the worker's recorded
thread. Explicit recovery or promotion records any replacement and handoff.

### R2: Distinct Completion and Acceptance States

**Strong recommendation:** distinguish attempt completion, check results,
semantic approval, task acceptance, and final build validation. Release wave
two only from an explicit successful final gate. Never infer success from a
generic completed status, missing messages, or elapsed time. Keep code outcome
and evidence-write outcome separate in the final report.

**Preserves:** independent validation, delayed updater deployment, and honest
reporting of best-effort evidence failures.

**Acceptance:** a worker that finishes with failing checks cannot release a
dependent gated task or either updater. Losing the success notification still
allows recovery from persisted gate evidence. A failed evidence write leaves
the code result intact but reports incomplete evidence, not full completion.

### R3: Repair Attempts Bound to the Original Task

**Strong recommendation:** represent repairs as attempts against a stable
logical task and its original acceptance contract. Preserve the failed tree as
repair input without depending on the failed task becoming PASSED first. A
successful revalidation must satisfy the original gate, including validate-all.
Persist the two-cycle budget and define whether a cycle covers a batch of
findings; newly generated task IDs must not reset that budget.

**Preserves:** assigned builders, actionable validator findings, bounded fixes,
and escalation after exhaustion.

**Acceptance:** initial failure -> repair -> revalidation success releases the
original task's dependents. Two unsuccessful repair cycles stop further fixes.
Restarting between repair creation and dispatch neither resets the budget nor
duplicates the repair. Exhaustion never deploys wave two.

### R4: Durable Coordination with Conservative Recovery

**Strong recommendation:** persist assignments, thread/turn identities, attempt
state, repository/spec hashes, check evidence, and integration records before
depending on them. Reconcile actual runtime and repository state after restart.
Treat external effects as potentially ambiguous: do not promise exactly-once
execution merely because SQLite transactions protect controller state.

**Preserves:** the lead's context re-anchoring and continuity across long builds,
without requiring a model to reconstruct coordination from memory.

**Acceptance:** inject crashes before and after dispatch, worker completion,
checks, integration, and evidence writes. Each restart either reconciles safely
or stops with an explicit disposition request. It must not blindly rerun a
possibly active worker, reintegrate a commit, or adopt user-modified work.

### R5: Reconcile Promised Tests with Actual Results

**Strong recommendation:** bind each promised test to a framework-specific
identity and compare it with machine-readable execution results on the recorded
validation tree. Missing, filtered, skipped, and expected-failure results need
explicit policy; suite exit code zero is insufficient. Retain semantic review
of assertions and type-surface checks. Preserve the updater's second verification
pass, with the controller executing commands and supplying fresh evidence.

**Preserves:** the source validator's test-name-to-outcome obligation and the
spec updater's independent recheck; this does not impose universal RGR evidence.

**Acceptance:** fixtures containing a missing, skipped, filtered, renamed, or
duplicate promised test cannot silently pass. Every accepted promise maps to a
recorded result and tree. A second-pass failure prevents a COMPLETE evidence
claim. Unsupported test adapters report unverified coverage rather than success.

### R6: Enforce Role Boundaries Outside Prompts

**Strong recommendation:** define effective filesystem, network, environment,
and approval permissions for each worker and the deterministic check runner.
Protect controller state, hook definitions, task descriptors, and credentials.
Use hooks as supplementary checks and validate actual deltas before integration.
Account for scripts and test processes executing arbitrary code. Permit ordered
file overlap while preventing conflicting concurrent ownership.

**Preserves:** a non-building lead, read-only reviewers, scoped builders,
spec-and-ledger updater permissions, and design-document-only write-back.

**Acceptance:** direct edits, shell/interpreter writes, test subprocesses,
symlink escapes, credential reads, and approval escalation attempts cannot
bypass role policy. Out-of-scope changes cannot integrate. Sequential tasks may
edit the same file; conflicting writers cannot run concurrently without an
explicit isolation/integration policy. Test on each supported operating system.

### R7: Verify Actual Routes Across Models and Providers

**Strong recommendation:** record requested and observed model/provider
identities for every worker attempt and correlate upstream requests, retries,
and fallbacks with that attempt. Treat a canary as capability evidence with a
bounded lifetime, not proof of all later routing. Respect model-specific tool,
streaming, output-schema, effort, and context support. Preserve binding-specific
lessons and promote-only fallback, including per-spec caps.

**Preserves:** abstract model classes, launch-time backend selection, routing
transparency, and the existing retrospective learning loop. Both local/on-prem
and frontier models are explicitly in scope.

**Acceptance:** one coordinated run executes concurrent multi-step tool work
across a local/on-prem route and a frontier route with attributable identities.
Exercise a wrong binding, unavailable route, expired credentials, and unsupported
tool/schema behavior. No fallback silently violates the task floor or cap, and
unverified identities never produce trusted capability lessons. Also verify a
single-backend run, which remains valid under the source contract.

### R8: Visible Progress from Runtime Evidence

**Strong recommendation:** provide a live view of each worker's identity,
assigned task, requested/observed model, activity, gate results, and blockers,
with access to retained output. Drive it from controller and runtime events,
not model-authored progress summaries. Make headless execution an explicit
choice. Record any presentation difference from the source's visible tmux panes.

**Preserves:** the user's ability to watch concurrent agents, inspect stalls,
understand routing decisions, and distinguish waiting from active execution.

**Acceptance:** show concurrent workers, dependency waiting, approval waiting,
validation failures, promotion, cancellation, and recovery distinctly. A
disconnected viewer can reconstruct current state without starting new model
turns. Missing telemetry displays unknown/stale rather than inferred success.
Retained output and views must redact secrets.

## Open Decisions

- Resolved on 2026-09-09: the user explicitly superseded the old Bedrock-only
  instruction. Codex should support both local/on-prem models and frontier
  models, including mixed-provider orchestration. This removes the policy
  conflict, not the requirement to certify runtime compatibility.
- Planning can identify new design decisions, but tasks must reference decisions
  already resolvable in the repository. Define staged decision publication and
  atomic spec/decision lineage; wave-two updates happen too late for this case.
- Define a sealed validation tree and separate post-validation documentation
  tree so final-commit evidence remains truthful after wave-two edits.

## Architecture Assessment

### Correctness and Maintainability

Controller ownership is stronger than the source Claude workflow's worker
self-claiming and self-reported completion. Keep structured manifests, immutable
findings, independent review, and fail-closed recovery. Recovery coverage is
already extensive; the missing repair semantics need precision, not more generic
instructions to add crash tests.

### Performance and Scalability

Parallel readers with a serial writer provide a useful first baseline. No
measurements support a throughput or cost improvement claim yet. Measure queue
time, worker time, validation time, critic cost, and integration overhead before
enabling parallel writers. Add aggregate run/token budgets alongside per-command
deadlines. A two-fix cap alone does not bound total runtime or cost.

### Observability and Testing

Requested-versus-observed routing, immutable raw events, deterministic reducers,
and the no-counterfactual-no-demotion rule are strong choices. The proposed fault
matrix covers meaningful failure boundaries. Add the focused fixtures in the
findings and bind check evidence to an exact tree and policy version. These are
proposed tests; no controller implementation or live-provider test ran here.

## Industry Comparison

Compared with the existing Claude v4 commands, this design deliberately replaces
model-led coordination with application-owned transitions. That is the right
place to enforce mandatory workflow rules, without reproducing Agent Teams.

OpenAI documents App Server for deep integrations with approvals, history, and
streaming, while recommending the SDK for ordinary automation. App Server is
defensible here because the plan needs lifecycle control and inspection; record
that decision explicitly. Its documented per-turn model, effort, outputSchema,
and sandbox fields support the proposed abstraction. Documentation does not prove
custom-provider compatibility; retain Phase 0 certification.

## Recommended Actions

1. Use the source contract tables as a parity checklist. Mark each capability
  preserved, adapted with rationale, or explicitly deferred with user approval.
2. Resolve source precedence tensions and the four plan findings before
  implementing their affected paths. The provider-policy question is resolved:
  both local/on-prem and frontier models are in scope.
3. An internal prototype may use a hand-authored spec and serial worker to prove
  repairs and recovery. Do not present that prototype as the delivered command
  equivalent: automated planning, the conditional panel, builder execution,
  validation, wave-two write-back, and routing lessons remain in scope.
4. Keep binding-aware learning and persistent-worker/parallel behavior in the
  parity discussion. Defer automated demotion and broader policy machinery,
  which are additions beyond the source's prose-led retrospective loop.
5. Review R1-R8 explicitly: record adopt, adapt, or decline with rationale and
  map accepted recommendations to implementation tasks and acceptance tests.
  Do not claim workflow parity or runtime guarantees before those checks pass.

The highest-leverage simplification is separating the existing v4 workflow from
new platform machinery, not removing capabilities that make v4 useful. No
quantified speedup is claimed.