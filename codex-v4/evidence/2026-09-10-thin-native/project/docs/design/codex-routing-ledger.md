# Codex Routing Ledger

## 2026-09-09 — Double v4 smoke build

### Observed routing

- The four planning critics actually used native default roles with copied
  checked-in instructions due failed custom-role discovery at planning time.
  Their native IDs are recorded in `specs/double-v4.md` and the planning
  evidence. This limitation must not be rewritten as registered
  `v4-plan-critic` execution.
- After planning, `.codex/config.toml` was added as an explained workflow-only
  baseline addition. It registered the already checked-in v4 role TOMLs and
  fixed native role discovery for execution without changing product
  requirements, implementation scope, tests, commands, or routing policy.
- All execution roles were spawned from registered v4 types with
  `fork_context=false`. No model override was used, so they inherited current
  Sol. Class labels remained reasoning-needs labels rather than distinct
  physical model bindings.
- Native execution exposed role types and agent IDs. It did not expose
  authenticated physical backend identity. Physical backend identity therefore
  remains **UNKNOWN**; an agent's self-report is not routing proof.
- The parent JSONL trace is externally captured by the caller and unavailable
  to this updater. No trace-authentication claim is made.

### Grounded lessons

- Repository-local role files are not sufficient evidence that native custom
  role discovery is active; successful registered-role spawning after the
  registry addition is the observed workflow boundary.
- Planning fallback work and later registered execution must be recorded as
  separate routing facts. A later discovery fix does not retroactively change
  the planning bindings.
- Inherited repair or completion work cannot establish model superiority. This
  build required no repair, and its successful checks and approvals establish
  task outcomes only, not comparative model quality.
- Agent IDs support role continuity and distinct-thread accounting, but without
  authenticated runtime backend evidence they do not identify the physical
  model serving those roles.
