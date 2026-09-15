---
title: Codex v4 Implementation Checkpoint
description: Tested Phase 0 implementation and resolution of the permission API mismatch.
---

# Implementation Checkpoint

## Status

**Permission API mismatch resolved; Phase 0 remains incomplete.** The initial implementation lives in
[codex-v4](../../../codex-v4/README.md). No planner/build workers, real model
turns, proxy changes, credential changes, commits, or branches were created.
Existing user changes remain intact.

## Implemented And Verified

- Python package with a `doctor` CLI and an asynchronous JSONL App Server client.
- Handshake, concurrent request/response correlation, deadlines, owned-child
  cleanup, sanitized failures, and rejection of server-initiated requests.
- Explicit nonsecret configuration overrides from the existing multi-model
  configuration; no shell-alias dependency.
- Live handshake and catalog discovery of Sol, Terra, Luna, GLM, and DeepSeek.
- Generated-schema compatibility checks and an opt-in synthetic read-boundary
  probe with an allowed control file.
- Thirty-one deterministic tests, including negative cases and a captured-schema
  regression. Tests passed after observed RED failures.

## Runtime Evidence

| Check | Result |
|---|---|
| Installed CLI | `codex-cli 0.144.1` |
| Python used for tests | 3.13.7 |
| `--profile` with `app-server` | Rejected by CLI; explicit overrides work |
| Handshake | PASSED |
| Five expected model aliases | All visible; no missing aliases |
| Legacy `readOnly.access` request | Rejected with -32600; server explicitly directs client to `permissionProfile` |
| Named `permissionProfile` in generated command schema | Supported |
| Named-profile allowed control read | PASSED |
| Named-profile outside sentinel read | Denied; read-boundary probe PASSED |
| Inference/provider route verification | Not executed |
| Phase 0 | INCOMPLETE, no current schema blockers; doctor exits 2 |

Command schema SHA-256:
`d67efca42dd7671c3102b6bb67ca2cd28aad2767538e182a1d7014d1d4fdcc65`.
The exact generated artifact resides in
[the schema fixture](../../../codex-v4/tests/fixtures/CommandExecParams-0.144.1.json).

The exact original JSON-RPC response was code `-32600` with message:
`Invalid request: readOnly.access is no longer supported; use permissionProfile for restricted reads`.
The first client hid this message behind a generic rejection. Interpreting the
missing legacy fields as a missing runtime capability was incorrect.

The corrected command selects `permissionProfile: codex-v4-read-probe` and omits
`sandboxPolicy`. Process-local overrides define a root-deny, minimal-runtime-read,
workspace-read, network-off profile. On the same 0.144.1 binary, the allowed
control read succeeds and the outside sentinel remains unreadable. No upgrade
or home configuration edit was necessary. These are sandboxed command tests, not
model turns; worker tools, writes, network denial, symlinks, and lifecycle still
require their own certification.

## Plan Progress

| Task | State |
|---|---|
| P0.1 Supported binary version | Installed version recorded; no version certified yet |
| P0.2 Generated protocol schemas | Experimental JSON generated; command schema retained; TypeScript capture pending |
| P0.3 Handshake client | Implemented and contract-tested |
| P0.4 Multi-model launch | Explicit-override adaptation verified; profile flag unavailable |
| P0.5 Model enumeration | Live verification passed |
| P0.6-P0.12 Threads, canaries, attestation, routing failures | Not started; legacy permission-interface blocker resolved |
| P0.13 Permissions | Named-profile command read isolation verified; full role/security suite pending |
| P0.14 Root lifecycle | Not certified |
| Phases 1-7 | Not executed; package/CLI scaffolding exists only for Phase 0 |

## Resume Decision

Keep restricted-read requirements and complete Phase 0 using the supported named
permission interface. Do not treat this single passing read-boundary check as
full certification or enable autonomous writes. No runtime upgrade is currently
required by the evidence gathered here.

Before later builder/ledger work, incorporate the three follow-up review
contracts: post-integration correction and evidence invalidation, Rust/Cargo
equivalence, and matched-baseline capability learning. Those later design
changes remain pending, alongside the user's Codex-only workflow-policy revision.