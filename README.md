# Aigile

Multi-agent orchestration pipelines for GitHub Copilot — plan, build, review, and ship with specialized AI agents working in concert.

**[Live Documentation →](https://vobbilis.github.io/aigile/)**

---

## What Is This?

Aigile is a set of reusable Copilot-native pipelines designed to work in **any IDE** (VS Code, Cursor, Windsurf, JetBrains, Neovim, Emacs) and **any Git-compatible platform** (GitHub, GitLab, Bitbucket, Gitea, Azure DevOps). Describe a feature or a bug in plain English; the system plans the work, implements it with TDD, validates every step, runs adversarial code review, opens a PR, and promotes it through CI/CD — all without leaving your editor.

The pipelines are **project-agnostic**. Edit one config file (`.github/project.json`) to point them at any tech stack — Python, TypeScript, Java, Go, or anything else.

---

## Architecture Overview

**[Pipelines Technical Overview →](.github/PIPELINES.md)** — full architecture with Mermaid diagrams, agent registry, hook system, and data flow.

---

## Claude Code CLI Update

**Claude AgentTeam Parallel Plan and Build Support** — a portable `~/.claude` configuration package that gives any Claude Code CLI user the full `/plan_to_build` → `/build` pipeline with self-organizing agent teams running in parallel tmux panes. The current flow is **v4** (`/plan_to_build_v4` → `/build_v4`): dynamic model routing across Bedrock and local models, a plan-time red team, and a cross-build routing ledger. See **[Claude Local Architecture v4 →](https://vobbilis.github.io/aigile/arch/claude-local-architecture-v4.html)** for the full flow and how it evolved from v1.

The tarball (`claude-team-setup.tar.gz`) includes every generation of the commands (`/plan_to_build` → `/build` through `/plan_to_build_v4` → `/build_v4`), all team agents (builder, validator, spec-updater, design-updater, bug pipeline), Python lifecycle hooks including the v3 and v4 spec validators, the skills library, a starter `model-routing-ledger.md`, and a pre-configured `settings.json` with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and tmux split-pane support. Untar into `~/` and the full pipeline is immediately available in any project. The inner `cl_README.md` documents the v4 flow, model slots, and the ledger.

Key capabilities over GitHub Copilot local mode: parallel agent execution (`run_in_background: true`), a shared on-disk task board (`TaskCreate/List/Update`), peer-to-peer agent messaging (`SendMessage`), dependency-ordered task graphs (`addBlockedBy`), and a spec-updater that writes verified build evidence back into the plan file.

**v2 reliability improvements** (use `/plan_to_build_v2` → `/build_v2`):

- **Assigned To enforcement** — builders only claim tasks explicitly assigned to their name; no more risk of the wrong specialist picking up someone else's work
- **No self-termination** — builders poll indefinitely (every 30s) instead of giving up after 5 retries; fix tasks created by the validator are never left orphaned
- **Targeted wakeup** — when validation fails, the leader immediately notifies the specific builder responsible for the fix rather than waiting for the next poll cycle
- **Collision-safe team names** — teams are named `<plan>-YYYYMMDD-HHMM` so re-running the same plan twice no longer conflicts
- **Liveness detection** — the leader tracks last-heard time per agent; pings any agent silent for 10+ minutes and escalates to the user if there's no response

**v3 unified TDD-grade spec** (use `/plan_to_build_v3` → `/build_v3`):

- **One file, not two** — design grounding, Type Surface, named Test Promises, RED-GREEN-REFACTOR and the task graph live in a single `-v3.md`; the separate TDD plan and build spec that used to drift are gone
- **Failure Surface before tests** — every error, config, stateful or crypto type gets a failure-mode inventory, each bullet maps to a named test row, and the Stop hook blocks specs below 30% failure-path coverage
- **Two-wave deploy** — spec-updater and design-updater deploy only after `validate-all` passes instead of idling through the whole build
- **Leader context resilience** — the lead keeps its context lean, resets with `/clear` at ~75% and re-anchors from git and the task list; `/compact` at the wall is never attempted
- **Staged spec writing** — skeleton first, then one edit per section, so a 50–90 KB spec can never look like a hang

**v4 dynamic model routing + plan-time red team** (use `/plan_to_build_v4` → `/build_v4`):

- **Model Class per task** — every task is classified REASONING / STANDARD / MECHANICAL by its shape; agents are partitioned so each is single-class and deploys on the matching `opus` / `sonnet` / `haiku` slot
- **Classes are abstract, bindings are the launcher's** — under `claude-multi` the slots resolve to Bedrock, a local GLM box and a local DeepSeek box in one build; under `claude-bedrock` they are cost tiers. The same spec runs either way
- **Verified binding, promote-only fallback** — the lead probes each slot with a one-shot teammate and reads the physical model from its transcript (teammates do not inherit the launcher's environment); dead slots promote agents one class up, never down
- **Plan Review Panel** — medium and complex drafts are red-teamed by four parallel read-only critics (failure surface, grounding, omissions, routing) and the author records every adjudication in the spec
- **Routing ledger** — the lead scores each agent RIGHT / OVER- / UNDER-PROVISIONED after the build; the lesson lands in `~/.claude/model-routing-ledger.md` and the next plan reads it first

**[v4 Architecture (current) →](https://vobbilis.github.io/aigile/arch/claude-local-architecture-v4.html)** · **[v2 Architecture →](https://vobbilis.github.io/aigile/arch/claude-local-architecture-v2.html)** · **[v1 Architecture →](https://vobbilis.github.io/aigile/arch/claude-local-architecture.html)**

---

## Codex CLI Update

**The v4 commands are ported to Codex as native skills.** `$plan-to-build-v4` and `$build-v4` run on stock Codex multi-agent support — no Python controller, no App Server adapter. Codex itself coordinates the agents through `spawn_agent`, `send_input`, `wait` and `close_agent`.

The port lives in [`codex-v4/native/`](codex-v4/native/):

- `.agents/skills/plan-to-build-v4/SKILL.md` — design grounding, one Markdown spec, conditional four-critic panel, model classes
- `.agents/skills/build-v4/SKILL.md` — persistent builders, validation, two independent reviews, spec and design updates, a fresh final auditor
- `.codex/agents/*.toml` + `.codex/config.toml` — seven role definitions: `v4-builder`, `v4-validator`, `v4-reviewer`, `v4-spec-updater`, `v4-design-updater`, `v4-auditor`, `v4-plan-critic`

**Install.** There is no tarball for the Codex side; the skills are three small directories you copy once. Skills go to `~/.agents/skills/`, role TOMLs to `~/.codex/agents/`, and the `[agents.v4-*]` entries plus `[features] multi_agent = true` merge into `~/.codex/config.toml`. Restart Codex and `/skills` lists both skills. The installed copies are standalone, not links to the checkout.

```bash
cp -R codex-v4/native/.agents/skills/plan-to-build-v4 codex-v4/native/.agents/skills/build-v4 ~/.agents/skills/
cp codex-v4/native/.codex/agents/v4-*.toml ~/.codex/agents/
# then merge the [features] and [agents.v4-*] tables from codex-v4/native/.codex/config.toml into ~/.codex/config.toml
```

**Run.** From the repository you want to work on:

```
$plan-to-build-v4 "<requirements + design reference>"
$build-v4 specs/<name>-v4.md
```

The coordinator must report BLOCKED if a required role is unavailable rather than impersonating it. On Codex 0.144.1 the flags that mattered were `--enable multi_agent --disable multi_agent_v2`, `-c 'model="<id>"'` (a bare `-m` failed child model resolution), and `fork_context=false` when selecting a custom role.

**Measured (2026-09-10, smoke fixture).** A complete build ran builder → validator → two independent reviewers → spec-updater + design-updater → fresh auditor; both reviews APPROVE, audit PASS. An injected wrong result failed validation and one `send_input` repair to the original builder restored PASS. Two negative audits correctly rejected bundles with a missing review and with failed checks. Evidence is in [`codex-v4/evidence/2026-09-10-thin-native/`](codex-v4/evidence/2026-09-10-thin-native/).

**Known limits.** On 0.144.1, child agents inherit the parent's permission profile even when their role declares `sandbox_mode = "read-only"`, so reviewer and auditor read-only-ness is instruction-only; the skills disclose this or report BLOCKED when the caller needs enforced isolation. Mixed-model routing, physical provider attestation, repeated reliability and restart recovery are untested. The full guide, launch settings and evidence table: **[`codex-v4/NATIVE_WORKFLOW.md`](codex-v4/NATIVE_WORKFLOW.md)**.

---

## Tests

Step-by-step tests to verify each pipeline end-to-end. See **[docs/TESTING.md](docs/TESTING.md)** for full details.

| Test       | What It Validates                                                                 | Link                                                                                         |
| ---------- | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **Test 1** | VS Code Copilot — interactive local agent mode                                    | [Test 1: VS Code Copilot](docs/TESTING.md#test-1-vs-code-copilot-interactive-local)          |
| **Test 2** | GitHub Copilot Coding Agent — async cloud PR flow                                 | [Test 2: Async Cloud Agent](docs/TESTING.md#test-2-github-copilot-coding-agent-async-cloud)  |
| **Test 3** | Failure recovery — CI failures and cross-platform seams                           | [Test 3: Failure Recovery](docs/TESTING.md#test-3-failure-recovery-the-interesting-one)      |
| **Test 4** | Bug-to-PR pipeline — 7 agents, 6 phases, full lifecycle                           | [Test 4: Bug-to-PR Pipeline](docs/TESTING.md#test-4-bug-to-pr-pipeline-the-star-of-the-show) |
| **Test 5** | PR-to-CI/CD pipeline — CI verification, adversarial review, deploy, health checks | [Test 5: PR-to-CI/CD Pipeline](docs/TESTING.md#test-5-pr-to-cicd-pipeline-the-closer)        |

---

## More Documentation

| Document                                                                     | Description                                                   |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------- |
| [Adapting to Your Project](docs/ADAPTING-TO-YOUR-PROJECT.md)                 | Detailed guide to configure the pipelines for any tech stack  |
| [Quick Adapt](docs/QUICK-ADAPT.md)                                           | 5 copy-paste Copilot prompts that generate all config for you |
| [Local vs. Cloud Comparison](docs/TESTING.md#local-vs-cloud-why-both-matter) | Why both agent architectures matter and when to use each      |

---

## Try It Yourself

This repo includes a **working full-stack app** (FastAPI backend + React/TypeScript frontend) built entirely using the aigile pipelines. It's a metrics dashboard — simple enough to understand quickly, complex enough to exercise every pipeline feature.

Clone this repo and use it as a playground to test both the Copilot and Claude Code pipelines against a real codebase:

```bash
git clone https://github.com/vobbilis/aigile.git
cd aigile
```

**For Claude Code CLI users** — install the agent team package first:

```bash
tar -xzf claude-team-setup.tar.gz -C ~/
mkdir -p specs docs/design
tmux new-session -s aigile
claude
```

Then use `/plan_to_build_v4` and `/build_v4` exactly as shown below against this project's codebase. `/build_v4` requires a tmux session so the agents render in visible panes.

**For GitHub Copilot users** — open the repo in VS Code, switch Copilot Chat to Agent mode, and use `/plan_to_build` and `/build` with the same prompts below.

### Feature Prompts (`/plan_to_build_v4` → `/build_v4`)

`/plan_to_build_v4` produces a `-v4.md` spec in `specs/` — it plans the work but doesn't write any code. Point it at a design document when you have one; without one it runs a design study first and writes `docs/design/<domain>.md`. To execute the plan, run `/build_v4` and point it at the spec:

```
/plan_to_build_v4 "add a sparkline chart to MetricCard showing the last 10 values (design: docs/design/metrics.md)"
```
Then:
```
/build_v4 specs/<the-generated-spec>-v4.md
```

More prompts to try:
```
/plan_to_build_v4 "add a metric history endpoint GET /metrics/{name}/history with pagination (design: docs/design/metrics.md)"
```
```
/plan_to_build_v4 "add a dark mode toggle that persists to localStorage"
```
```
/plan_to_build_v4 "add metric tags filtering — let users filter the dashboard by tag key/value (design: docs/design/metrics.md)"
```

### Bug Fix Prompts (`/bug_to_pr`)

```
/bug_to_pr "the delete button returns success but the metric card doesn't disappear until the next poll"
```
```
/bug_to_pr "posting a metric with an empty name returns 500 instead of 422 validation error"
```
```
/bug_to_pr "the frontend polling interval resets when switching between filtered and unfiltered views"
```

### Deployment Prompts (`/pr_to_cicd`)

After a PR is merged, promote it through CI verification and deployment:

```
/pr_to_cicd PR #5
```
```
/pr_to_cicd PR #5 to staging
```

The pipeline runs in **stub mode** by default — no real Jenkins or Spinnaker needed. It simulates the full 6-phase flow (CI trigger → adversarial CI review → deploy gate → health checks → post-deploy review → report) so you can see how it works before connecting real infrastructure.

To connect real CI/CD systems, edit `.github/project.json` — set `ci.job_url` for Jenkins and `deploy.pipeline_url` for Spinnaker. The adapter scripts in `.github/adapters/` handle the rest.

### What to Watch For

- **`/plan_to_build_v4`** creates a `-v4.md` spec in `specs/` and, for medium or complex work, red-teams it with four critics before the Stop hook lets the session end — then run **`/build_v4 specs/<filename>-v4.md`** to execute it. The lead announces which model slot each agent runs on, builders and the validator work the task list in tmux panes, and the spec-updater writes Build Evidence plus a routing lesson back into the spec
- **`/bug_to_pr`** runs the full 6-phase lifecycle — triage, plan, build, PR, adversarial review, merge — all from a single prompt
- **`/pr_to_cicd`** promotes a merged PR through CI → adversarial review → deploy → health checks — with human gates before every destructive action
- **Hooks fire automatically** — every file write triggers lint/typecheck validation in real time
- **Crash recovery works** — if a pipeline stops mid-run, say `resume` and it picks up from the last checkpoint
