---
title: Native Codex v4 Workflows
description: Use the native planning and build skills, with measured results and limitations.
---

# Native Codex v4 Workflows

The repository now supplies `$plan-to-build-v4` and `$build-v4` as Codex skills.
Stock Codex coordinates the agents. These skills do not use the Python
controller or App Server adapter in this directory. Claude commands and settings
remain unchanged. The user-wide installation adds only v4 agent registrations
and native-agent feature flags to the existing Codex user configuration.

## Use

The entry points are installed for this user across repositories and workspaces:

- [Planning skill source](native/.agents/skills/plan-to-build-v4/SKILL.md): design grounding,
  one Markdown spec, conditional four-critic panel, and model classes.
- [Build skill source](native/.agents/skills/build-v4/SKILL.md): persistent builders,
  validation, two independent reviews, specification and design updates, audit.
- [Role registry source](native/.codex/config.toml): seven native role definitions.

Installed skills live under `~/.agents/skills/`; installed roles live under
`~/.codex/agents/`, registered in `~/.codex/config.toml`. They are standalone
copies, not links to this checkout. The source bundle lives under `codex-v4/native`
outside repository discovery folders, avoiding duplicate entries here. Changes
to the source bundle require updating the installed copies.

Restart Codex after installation. Start `codex-multi` from the repository you
want to work on; `/skills` lists both v4 skills. Empty invocations and `help`,
`-h`, or `--help` now instruct the skills to display usage and stop after loading
the skill, without repository exploration, edits, tests, or agent spawning.

Verified on 2026-09-10 with Codex's `skills/list` API: `/tmp`,
`itom-portal-prototype`, and `metrics-dashboard` each discover exactly one enabled
user-level copy of each skill. The installation preserved all pre-existing Codex
settings. This discovery check ran no inference; help-only behavior has static
instruction tests, not a new live model test.

In a Codex session that has loaded these skills and registered roles, invoke
`$plan-to-build-v4` with requirements and a design reference. Build the resulting
spec with `$build-v4 specs/<name>-v4.md`. The coordinator must report BLOCKED if
required roles are unavailable, rather than impersonating them.

The tested route used the existing Codex-only LiteLLM bridge at
`http://127.0.0.1:4113/v1`, Codex 0.144.1, and Sol for every role. No upgrades,
credential refreshes, commits, or Claude configuration changes were necessary.
The bridge must already be running with usable provider credentials.

### Tested Launch Settings

The live experiments invoked `codex exec` directly, without a custom controller.
These details mattered on the installed version:

| Setting | Observed behavior |
| --- | --- |
| `--enable multi_agent --disable multi_agent_v2` | Provides native `spawn_agent`, `send_input`, `wait`, and `close_agent`. |
| `-c 'model="openai.gpt-5.6-sol"'` | Survives custom-role configuration loading. `-m` alone failed child model resolution. |
| `-c 'sandbox_mode="workspace-write"'` | Sets the parent permission profile used by build agents. See the permission limitation below. |
| `fork_context=false` | Required when selecting a custom role; full-history forks rejected role/model overrides. |
| `agents.<role>.config_file` | Explicit process overrides loaded roles when project discovery failed in the non-Git temporary fixture. |
| `agents.max_concurrent_threads_per_session` | Invalid in 0.144.1. The experiment used the default limit. |

For the non-Git smoke fixture, each role used this override form:

```text
-c 'agents.v4-validator={description="Execute checks without reviewing",config_file="/tmp/codex-thin-cAlReHYM/project/.codex/agents/v4-validator.toml"}'
```

The provider settings were explicit process overrides, not edits to home files:

```toml
model = "openai.gpt-5.6-sol"
model_provider = "codex-multi-local"
model_reasoning_effort = "medium"
model_catalog_json = "/Users/vobbilis/.codex/codex-multi-model-catalog.json"

[model_providers.codex-multi-local]
name = "Codex Multi (LiteLLM)"
base_url = "http://127.0.0.1:4113/v1"
wire_api = "responses"
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
```

Do not assume `--ignore-user-config -p codex-multi` selects this route: that
combination contacted the default OpenAI endpoint in an earlier canary. Verify
the actual endpoint and child model before a build. The GLM canary failed because
the lab hostname did not resolve; mixed local/frontier execution remains untested.

## Measured Results

Evidence directory: [2026-09-10-thin-native](evidence/2026-09-10-thin-native).
The fixture implements `double(value: int) -> int` and one test covering positive,
zero, and negative inputs. This is a workflow smoke test, not a production-scale
evaluation.

| Experiment | Result | Evidence |
| --- | --- | --- |
| Planning panel | Four native critics returned findings; author incorporated ten findings. Custom-role discovery failed, so this run used default agents with copied instructions. | [Planning result](evidence/2026-09-10-thin-native/plan-final.txt) |
| Registered role canary | Custom validator spawned, completed, and closed after correcting model configuration. | [Canary](evidence/2026-09-10-thin-native/registry-layer-final.txt) |
| Complete build | Builder, validator, two reviewers, both updaters, and fresh auditor ran. Both reviews APPROVE; audit PASS. | [Native events](evidence/2026-09-10-thin-native/build-events.jsonl) |
| Actual test execution | Builder RED exit 2, GREEN exit 0; validator and spec updater each executed pytest successfully. | [Child tool records](evidence/2026-09-10-thin-native/children) |
| Repair injection | Wrong result produced `assert 5 == 4`; separate validator failed. One `send_input` repair to the original builder restored PASS. | [Repair events](evidence/2026-09-10-thin-native/repair-events.jsonl) |
| Missing beta report | Fresh auditor returned FAIL for a synthetic bundle lacking beta's report and ID. | [Negative results](evidence/2026-09-10-thin-native/negative-final.txt) |
| Failed checks | Another fresh auditor rejected a synthetic bundle with two failed checks despite two review approvals. | [Negative events](evidence/2026-09-10-thin-native/negative-events.jsonl) |

Build reviewer IDs were `01a08a17-bb05-75f3-8709-de8d05887c84` and
`01a08a17-c37e-7e83-8094-f54e146e66f9`. Auditor ID was
`01a08a1f-5a18-7292-930d-9f39e9607006`. The coordinator recovered from one
thread-limit rejection by closing finished agents before retrying the auditor.
The revised skill now instructs that cleanup before the spawn.

## Demonstrated Permission Limitation

Codex 0.144.1 native v1 children inherited the parent's permission profile even
when their role TOML declared `sandbox_mode = "read-only"`.

We tested the same read-only role with one harmless write attempt per parent:

- Read-only parent: exit 1, `operation not permitted`; no sentinel created.
- Workspace-write parent: exit 0; sentinel created.

See the [probe role](evidence/2026-09-10-thin-native/permission-probe/permission-role.toml),
[denied result](evidence/2026-09-10-thin-native/permission-read-only-final.txt), and
[successful write](evidence/2026-09-10-thin-native/permission-workspace-write-final.txt).
The version-tagged implementation confirms the order:
[spawn.rs](https://github.com/openai/codex/blob/rust-v0.144.1/codex-rs/core/src/tools/handlers/multi_agents/spawn.rs)
loads the role, then
[multi_agents_common.rs](https://github.com/openai/codex/blob/rust-v0.144.1/codex-rs/core/src/tools/handlers/multi_agents_common.rs)
sets the child's permission profile from the parent.

Therefore the build's validator, reviewers, and auditor followed no-write
instructions, but their filesystem permissions did not prevent workspace writes.
Separate review threads also do not prevent reading shared files. If enforced
per-role read-only access is a requirement, this configuration is insufficient.
The skills now require that limitation to be disclosed, or BLOCKED when the
caller requires stronger protection. No sandbox bypass was used in these tests.

## What This Does Not Establish

The successful build shows that a thin native workflow can execute the requested
sequence. It does not establish that Codex mechanically prevents skipped stages.
The two negative audits tested model behavior against supplied synthetic records;
they did not test runtime rejection of a skipped review or forged evidence.

Mixed-model routing, physical provider attestation, repeated reliability,
parallel independent implementation tasks, repair-budget exhaustion, and restart
recovery remain untested. The corrected four-custom-critic planning panel has
not been rerun. The archived fixture preserves the exact earlier skill versions;
the later fallback, thread-cleanup, and permission clarifications have static
contract coverage, not another complete live run.

The retained child records include tool calls/results and selected runtime model
and sandbox fields, not credentials or private reasoning. Call IDs correlate
pytest invocations with their actual outputs. These local files support inspection;
they are not cryptographically authenticated records.

Verification after changes: **393 tests passed**, including 15 native packaging
checks; Ruff lint and format checks passed for the seven changed Python files.
The earlier Python controller remains an experiment. These results do not justify
expanding it automatically.