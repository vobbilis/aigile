---
title: Codex v4 Workflows And Runtime Experiments
description: Use the thin native workflow or inspect the earlier runtime experiment.
---

# Codex v4 Workflows And Runtime Experiments

Start with the [native workflow guide](NATIVE_WORKFLOW.md). The active approach
uses user-wide Codex skills and native agents, with a complete smoke build,
two independent reviews, documentation updates, final audit, and a separate repair
test. The guide records the actual results and a demonstrated child-permission
limitation on Codex 0.144.1.

The Python package below remains an earlier controller experiment. It now has
experimental `plan`, `build`, and `status` commands alongside `doctor`, but no
successful live controller build has been established. The native skills do not
depend on this package. The following certification notes describe the original
doctor checks, not certification of either complete workflow.

The installed Codex 0.144.1 passes handshake, five-model discovery, and a
synthetic read-isolation check using named permission profiles. The earlier
blocker was an obsolete API representation, not a missing sandbox capability.
The [implementation plan](../docs/design/codex-v4-native-orchestration-plan.md)
now uses `permissionProfile` for commands. Phase 0 is **incomplete**, not
certified. See the
[execution checkpoint](../docs/design/codex-v4/2026-09-09-implementation-checkpoint.md).

## Run

From the repository root, using its existing virtual environment:

```bash
venv/bin/python -m pip install -e './codex-v4[test]'
venv/bin/python -m codex_v4 --help
venv/bin/python -m codex_v4 doctor --probe-read-boundary
```

The doctor exports schemas from the installed binary, starts an owned App
Server, enumerates model aliases, and checks the supported permission interface. The
optional boundary probe creates synthetic control/sentinel files under a
temporary home-directory folder and removes them afterward. It never reads real
credentials or sends an inference turn. A rejected control command is
`UNVERIFIED`, not proof of successful isolation.

The read probe selects a process-local named profile with `:root = deny`,
`:minimal = read`, `:workspace_roots = read`, and networking disabled. The
allowed control file must be readable; the existing outside sentinel must
remain unreadable. This verifies that read boundary only, not the full security
suite. Neither the named profile nor its rules are saved to home configuration.

The command returns exit code **2** while certification remains incomplete or
blocked, including when model discovery succeeds. It does not restart LiteLLM,
refresh credentials, alter home configuration, or upgrade Codex.

## Test

```bash
venv/bin/python -m pytest -c codex-v4/pyproject.toml codex-v4/tests/contract -q
venv/bin/ruff check codex-v4
venv/bin/ruff format --check codex-v4
```

The deterministic suite uses a real child-process JSONL fixture server. It
covers handshake ordering, concurrent response correlation, server-request
rejection, malformed responses, EOF, deadlines, cleanup, launcher restrictions,
partial evidence, CLI errors, and the captured 0.144.1 schema. Tests do not need
live providers. Verification used Python 3.13.7 on macOS; Python 3.11 is the
package minimum, not yet a separately tested interpreter target.

## Safety And Limits

- The launcher uses explicit allowlisted profile overrides because App Server
  0.144.1 rejects `--profile`; it does not invoke shell aliases.
- The bridge must be a local, credential-free Responses URL. Provider secret
  fields are rejected rather than copied into process arguments.
- The doctor disables inherited MCP servers, plugins, and worker subagents,
  and starts no model turns or repository-writing workers.
- The transport rejects all server-initiated requests. It retains notification
  method names only; it is not yet a full worker event store.
- Error summaries omit upstream text. The package does not initialize Sentry
  or configure an external telemetry destination.
- Discovery proves catalog visibility, not provider health or physical identity.
- Do not reuse the probe launcher as a production worker sandbox. Its filesystem
  policy has not passed the required certification.

## Continue

No Codex upgrade is required for the verified named-profile read boundary.
Complete write, network, symlink, and worker-role enforcement checks plus
canaries, physical-route attestation, concurrency, and lifecycle checks before
enabling planner/build execution. See the official
[permissions documentation](https://learn.chatgpt.com/docs/permissions).