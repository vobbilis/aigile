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

**Claude AgentTeam Parallel Plan and Build Support** — a portable `~/.claude` configuration package that gives any Claude Code CLI user the full `/plan_to_build` → `/build` pipeline with self-organizing agent teams running in parallel tmux panes.

The tarball (`claude-team-setup.tar.gz`) includes the `/plan_to_build` command, the `/build` orchestrator, all team agents (builder, validator, spec-updater, bug pipeline), Python lifecycle hooks, 48 skills, and a pre-configured `settings.json` with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and tmux split-pane support. Untar into `~/` and the full pipeline is immediately available in any project.

Key capabilities over GitHub Copilot local mode: parallel agent execution (`run_in_background: true`), a shared on-disk task board (`TaskCreate/List/Update`), peer-to-peer agent messaging (`SendMessage`), dependency-ordered task graphs (`addBlockedBy`), and a spec-updater that writes verified build evidence back into the plan file.

**[Claude Local Detail →](https://vobbilis.github.io/aigile/arch/claude-local-architecture.html)**

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

The best way to learn how the pipelines work is to **run them against this project**. Open the repo in VS Code, switch Copilot Chat to Agent mode, and try these prompts:

### Feature Prompts (`/plan_to_build` → `/build`)

`/plan_to_build` produces a spec file in `specs/` — it plans the work but doesn't write any code. To execute the plan, run `/build` and point it at the spec:

```
/plan_to_build "add a sparkline chart to MetricCard showing the last 10 values"
```
Then:
```
/build specs/<the-generated-spec>.md
```

More prompts to try:
```
/plan_to_build "add a metric history endpoint GET /metrics/{name}/history with pagination"
```
```
/plan_to_build "add a dark mode toggle that persists to localStorage"
```
```
/plan_to_build "add metric tags filtering — let users filter the dashboard by tag key/value"
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

- **`/plan_to_build`** creates a spec in `specs/` — then run **`/build specs/<filename>.md`** to execute it. Builder + validator agents take turns implementing each task with TDD
- **`/bug_to_pr`** runs the full 6-phase lifecycle — triage, plan, build, PR, adversarial review, merge — all from a single prompt
- **`/pr_to_cicd`** promotes a merged PR through CI → adversarial review → deploy → health checks — with human gates before every destructive action
- **Hooks fire automatically** — every file write triggers lint/typecheck validation in real time
- **Crash recovery works** — if a pipeline stops mid-run, say `resume` and it picks up from the last checkpoint
