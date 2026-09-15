---
title: Codex Runtime Notes
description: The Python client, the permission error we misread, and the tests that passed.
---

# Codex runtime notes

**9 September 2026.** Notes from building the first Codex runtime check: the
Python client, the permission error we misread, and the tests that passed.

## Why we started here

We set out to adapt the Claude planning and building workflow to Codex. The
first piece we built was a runtime check.

The [Aigile playbook](../../index.html) puts most of the preparation into the
spec. Builders get detailed tasks, validators run the checks, and the final
report includes command output. The later Claude `/plan_to_build_v4` and
`/build_v4` commands were the source for this work; they are separate from the
February version described in the playbook.

Before we could use Codex for that workflow, we needed to check how its installed
runtime behaved. Could we load our configuration, exchange requests, and restrict
a command's file access? Reading the API schema answered only part of that.

The package contains an App Server client and a `doctor` command. It does not
yet plan or build software. We ran no model inference and changed no Claude
commands or home configuration.

## The client

The Python client starts Codex App Server as a child process and exchanges
newline-delimited JSON through standard input and output. It handles the
connection, requests, timeouts, and shutdown.

One difference showed up at startup: Codex 0.144.1 rejected `--profile` for App
Server. The launcher now passes selected settings as explicit `-c` overrides.

| Part | What the code does | How we checked it |
|---|---|---|
| Connection | Sends `initialize`, then `initialized` | Live handshake and a test server that checks the order |
| Requests | Matches each response to its request ID | The test server replies out of order |
| Server prompts | Rejects requests for approval, permissions, or input | Six request types, including an unknown method |
| Timeouts | Limits request time and closes its child process on exit | A test server that hangs |
| Model list | Reads catalog pages and compares names with the expected list | All five expected aliases appeared in the live run |
| File access | Runs two reads under the same named permission profile | The inside file was readable; the outside file was not |
| Partial results | Keeps discovery results if the read check cannot run | A test server that rejects the read command |

### What the launcher allows

The [launcher](../../../codex-v4/src/codex_v4/runtime.py) accepts a local HTTP
Responses endpoint without credentials in its URL. It rejects unsupported
provider settings, including secret fields, before putting configuration into
process arguments. It disables configured MCP servers, plugins, and multi-agent
features for the check.

The CLI passes only selected environment variables to the child. The
[client](../../../codex-v4/src/codex_v4/app_server.py) rejects responses it cannot
match to a request and keeps notification names rather than full message bodies.
It reports generic errors instead of forwarding server error text.

## Less work for the prompt

The feedback challenged how much procedure we were asking the model to carry.

The old playbook puts critical rules directly into prompts so the model sees
them on every task. That explains the repeated instructions to wait, validate,
count attempts, and report results. But a request timeout or a permission
decision does not need to depend on the model following a paragraph.

In this client, Python matches replies to requests, applies deadlines, rejects
server prompts, and records check results. File access goes through a Codex
permission profile. None of that requires an inference call.

The tests are similarly direct. A parameterized test tries six server-request
methods; another tries four transport failures. Each case checks the client's
response. We have not implemented a new planning or testing policy for builders,
so this is the extent of that change in the code.

## The check we got wrong

Our first read check used `readOnly.access`. The generated schema did not contain
that field, and Codex rejected the request. We reported that the installed
version lacked the permission support we needed.

We were wrong. When we inspected the actual error, Codex told us what to change:

> Invalid request: readOnly.access is no longer supported; use permissionProfile for restricted reads

That was App Server error `-32600`. The
[fix](../../../codex-v4/src/codex_v4/certification.py) was to select
`permissionProfile` on `command/exec` and remove the command's legacy
`sandboxPolicy` field. It worked on the same Codex 0.144.1 binary. No upgrade
was needed.

The profile denies reads from the root filesystem except for the minimal runtime
files and workspace roots it allows. It also sets networking off. We pass it to
the App Server process without saving it to home configuration.

The launcher still sets its legacy read-only default. These commands explicitly
select the named profile; we did not test other combinations of those settings.

### One file inside, one outside

The check creates two temporary files with identical contents. One sits inside
the allowed directory and the other outside it. We try to read both using the
same profile and working directory.

| Check | Observed result |
|---|---|
| Inside file | Read succeeded and returned the expected contents |
| Outside file | Nonzero exit code; contents not returned |
| Read check | PASSED on Codex 0.144.1 |

The inside read is important. If both reads fail, the command itself might be
broken. The doctor reports `UNVERIFIED` when it cannot run the check and keeps
any discovery results it already has.

The temporary files are removed afterward. We did not use real credentials as
test files, refresh credentials, or restart the proxy.

Our error handling also contributed to the mistake. The client hid the useful
server message behind a generic rejection. We found it through a separate
diagnostic request. That generic error handling is still in the client.

## Results

We ran the live check on macOS with Codex CLI **0.144.1**. The contract tests used
Python **3.13.7**.

| Result | Meaning |
|---|---|
| Handshake: `PASSED` | The client connected and initialized |
| Five aliases visible | All expected names appeared in the catalog |
| Read boundary: `PASSED` | The inside read succeeded and the outside read failed |
| `inference_executed: false` | No model inference ran |
| `certified: false` | These checks do not cover the full runtime |
| Phase 0: `INCOMPLETE` | The permission error is fixed; certification is incomplete |

The catalog listed `openai.gpt-5.6-sol`, `openai.gpt-5.6-terra`,
`openai.gpt-5.6-luna`, `deepseek-v4-flash`, and `glm-5.3-flash`. We checked that
the names appeared. We did not send work to those models or verify the providers
behind them.

**31 tests passed.** Ruff lint and formatting checks also passed. The tests use a
child process acting as a test server. They cover connection handling, launch
restrictions, partial results, CLI errors, and the captured command schema. The
[checkpoint](2026-09-09-implementation-checkpoint.md) records the live run
separately from those tests.

### What a passing check means here

The doctor returns exit code **2** even when these checks pass, because
certification is incomplete. We have not tested network denial, write
restrictions, path escapes, or worker lifecycle behavior against the live
runtime. Nor have we measured model quality, speed, or cost.

The work so far is a working runtime probe, with the launch and permission
changes needed for this Codex version. It is not a completed port of the Claude
workflow.

## Code and test records

- [Aigile engineering playbook](../../index.html): the February workflow.
- [Source-command review](2026-09-09-native-orchestration-review.md): what the Claude v4 commands and hooks do.
- [Package README](../../../codex-v4/README.md): how to run the doctor and tests.
- [Doctor code](../../../codex-v4/src/codex_v4/cli.py): discovery, file checks, and reporting.
- [Transport tests](../../../codex-v4/tests/contract/test_app_server.py) and [permission tests](../../../codex-v4/tests/contract/test_certification.py).
- [Checkpoint](2026-09-09-implementation-checkpoint.md): the live results and corrected diagnosis.