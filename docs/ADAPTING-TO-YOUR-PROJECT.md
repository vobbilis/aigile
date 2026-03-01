# Adapting the Pipelines to Your Project

A step-by-step guide for adapting the agent pipelines (`/plan_to_build`, `/build`, `/bug_to_pr`) to work with **your** codebase — regardless of language or framework.

> **Time required**: ~15 minutes  
> **Prerequisites**: VS Code with GitHub Copilot Chat (Agent mode)  
> **Skill level**: Beginner-friendly — no prior agent experience needed

---

## Table of Contents

1. [How It Works](#1-how-it-works)
2. [Copy the Pipeline Files](#2-copy-the-pipeline-files)
3. [Edit project.json](#3-edit-projectjson)
4. [Edit bug-modules.json](#4-edit-bug-modulesjson)
5. [Choose Your Fixer Agents](#5-choose-your-fixer-agents)
6. [Customize a Fixer Agent (Optional)](#6-customize-a-fixer-agent-optional)
7. [Update copilot-instructions.md](#7-update-copilot-instructionsmd)
8. [Verify Everything Works](#8-verify-everything-works)
9. [Examples for Common Tech Stacks](#9-examples-for-common-tech-stacks)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. How It Works

Every agent, prompt, and hook in the pipeline reads from **one file** to learn about your project:

```
.github/project.json   <-- You edit this
       |
       ├── builder agent        reads it to discover paths and commands
       ├── validator agent      reads it to know what lint/test to run
       ├── bug-creator agent    reads it to understand your modules
       ├── bug-fixer-* agents   reads it to find their module's commands
       └── post_tool_validator  reads it to auto-lint on file save
```

**Nothing else is hardcoded.** The pipeline files (prompts, agents, hooks) are generic. All project-specific knowledge lives in `project.json`.

---

## 2. Copy the Pipeline Files

Copy the entire `.github/` directory from this repository into your project:

```bash
# From this repo's root
cp -r .github /path/to/your-project/.github
```

This gives you:

| Directory / File                     | What It Does                                |
| ------------------------------------ | ------------------------------------------- |
| `.github/project.json`              | Your project config (the file you'll edit)  |
| `.github/bug-modules.json`          | Module-to-agent routing                     |
| `.github/agents/*.agent.md`         | Agent definitions (builder, validator, etc.) |
| `.github/prompts/*.prompt.md`       | Pipeline prompts (plan, build, bug_to_pr)   |
| `.github/hooks/`                    | Auto-lint on save, dependency install       |
| `.github/instructions/`             | Always-on planning rules                    |

---

## 3. Edit project.json

This is the **only required step**. Open `.github/project.json` and replace it with your project's information.

### The Structure

```jsonc
{
    "name": "your-project-name",
    "description": "A short description of your project",
    "modules": {
        "module-name": {           // A logical part of your codebase
            "tech": "Language / Framework",
            "paths": ["src/"],     // Directories this module owns
            "description": "What this module contains",
            "run": "command to start the dev server",
            "test": "command to run tests",
            "lint": "command to run the linter",
            "format": "command to check formatting",    // optional
            "typecheck": "command to check types",      // optional
            "fixer_agent": "bug-fixer-module-name"
        }
    },
    "default_fixer": "bug-fixer-module-name"
}
```

### Field Reference

| Field          | Required? | What It Does                                                      |
| -------------- | --------- | ----------------------------------------------------------------- |
| `name`         | Yes       | Your project name (used in descriptions only)                     |
| `description`  | Yes       | What the project is (helps agents understand context)             |
| `modules`      | Yes       | Object with one entry per logical module (see below)              |
| `default_fixer`| Yes       | Which fixer agent to use when the module can't be determined      |

### Module Fields

| Field          | Required? | What It Does                                                      |
| -------------- | --------- | ----------------------------------------------------------------- |
| `tech`         | Yes       | Language and framework (e.g., "Python / Django")                  |
| `paths`        | Yes       | Array of directory prefixes this module owns (e.g., `["api/"]`)   |
| `description`  | Yes       | What's in this module — file names, structure                     |
| `run`          | No        | Command to start the dev server                                   |
| `test`         | Yes       | Command to run the test suite                                     |
| `lint`         | Yes       | Command to run the linter                                         |
| `format`       | No        | Command to check code formatting                                  |
| `typecheck`    | No        | Command to check types (e.g., `tsc --noEmit`, `mypy`)            |
| `fixer_agent`  | Yes       | Which bug-fixer agent handles this module                         |

### Rules

- **Every command should work from the project root.** Use `cd <dir> && <command>` patterns.
- **Paths must end with `/`** — they are used as prefix matching.
- **You need at least one module.** Most projects have 1–3.

---

## 4. Edit bug-modules.json

Open `.github/bug-modules.json` and update it to match your `project.json` modules.

This file is a **simpler routing view** used by the `bug-router` agent to classify bugs:

```jsonc
{
    "_note": "Derived from .github/project.json — edit project.json as the single source of truth.",
    "modules": {
        "module-name": {
            "fixer": "bug-fixer-module-name",      // must match fixer_agent in project.json
            "paths": ["src/"],                      // must match paths in project.json
            "test_command": "cd src && npm test"    // must match test in project.json
        }
    },
    "default_fixer": "bug-fixer-module-name"       // must match default_fixer in project.json
}
```

> **Keep it in sync** with `project.json`. They should list the same modules, paths, and test commands.

---

## 5. Choose Your Fixer Agents

The pipeline ships with four fixer agents:

| Agent                   | Best For                                      |
| ----------------------- | --------------------------------------------- |
| `bug-fixer-backend`     | Python, Ruby, PHP, or any server-side code    |
| `bug-fixer-frontend`    | TypeScript, JavaScript, CSS, React, Vue, etc. |
| `bug-fixer-java`        | Java, Kotlin, Spring Boot, Maven/Gradle       |
| `bug-fixer-go`          | Go services, CLI tools                        |

**For most projects, the existing agents work as-is** — they read `project.json` for paths and commands, so they adapt automatically.

### Mapping Your Modules to Fixers

Set the `fixer_agent` field in `project.json` to point to the closest match:

| Your tech stack        | Use this fixer_agent   |
| ---------------------- | ---------------------- |
| Python / Django        | `bug-fixer-backend`    |
| Python / FastAPI       | `bug-fixer-backend`    |
| Node.js / Express      | `bug-fixer-backend`    |
| Ruby / Rails           | `bug-fixer-backend`    |
| React / Vue / Angular  | `bug-fixer-frontend`   |
| Java / Spring Boot     | `bug-fixer-java`       |
| Kotlin / Ktor          | `bug-fixer-java`       |
| Go / Gin / Chi         | `bug-fixer-go`         |
| Rust                   | `bug-fixer-backend`    |
| C# / .NET              | `bug-fixer-backend`    |

> The fixer agents don't contain language-specific logic. They are **planning agents** — they investigate bugs and write fix plans. The actual coding is done by the `builder` agent, which handles any language.

---

## 6. Customize a Fixer Agent (Optional)

If your project uses a language not well served by the existing fixers, you can create a new one.

### Step 1: Copy an Existing Fixer

```bash
cp .github/agents/bug-fixer-backend.agent.md .github/agents/bug-fixer-rust.agent.md
```

### Step 2: Edit the New File

Change three things:

1. **The frontmatter** at the top:
   ```yaml
   ---
   name: bug-fixer-rust
   description: Analyzes Rust bugs and creates fix plans. Reads bug reports, investigates Rust code, and produces specs/fix-<bug-id>.md.
   model: Claude Sonnet 4
   user-invokable: true
   ---
   ```

2. **The module name** in the "Module Ownership" section:
   ```markdown
   Read `.github/project.json` and look up the `"rust-service"` module to discover:
   ```

3. **The language-specific hints** in the "Instructions" or "Key Behaviors" section:
   ```markdown
   - For Rust bugs, consider: ownership/borrowing, lifetime annotations, trait implementations, unsafe blocks.
   ```

### Step 3: Register It

In `project.json`, set the module's `fixer_agent`:
```json
"rust-service": {
    "fixer_agent": "bug-fixer-rust"
}
```

In `bug-modules.json`, add a matching entry:
```json
"rust-service": {
    "fixer": "bug-fixer-rust",
    "paths": ["rust-service/"],
    "test_command": "cd rust-service && cargo test"
}
```

That's it. The orchestrator will automatically dispatch your new fixer for bugs in that module.

---

## 7. Update copilot-instructions.md

Open `.github/copilot-instructions.md` and update it to describe **your** project. This file is the "general knowledge" that Copilot Chat always has access to.

Key sections to update:

- **Project description** — what your project does
- **Code style** — your coding conventions per language
- **Architecture** — how your modules connect
- **Build and test** — commands to build, test, lint each module
- **API contract** — your API endpoints (if applicable)
- **Test patterns** — how you write tests

> You can use the existing file as a template. Replace the metrics-dashboard specifics with your own.

---

## 8. Verify Everything Works

### Quick Check: Validate project.json

Open a terminal in your project root and run:

```bash
# Verify JSON is valid
python3 -c "import json; json.load(open('.github/project.json')); print('OK')"

# Verify bug-modules.json is valid
python3 -c "import json; json.load(open('.github/bug-modules.json')); print('OK')"
```

### Quick Check: Test the Hook

The `post_tool_validator.py` hook reads `project.json` to know which lint/typecheck commands to run. Test it:

```bash
python3 -c "
import json
cfg = json.load(open('.github/project.json'))
for name, mod in cfg['modules'].items():
    print(f'{name}:')
    print(f'  lint:      {mod.get(\"lint\", \"(none)\")}')
    print(f'  test:      {mod.get(\"test\", \"(none)\")}')
    print(f'  typecheck: {mod.get(\"typecheck\", \"(none)\")}')
    print(f'  fixer:     {mod.get(\"fixer_agent\", \"(none)\")}')
"
```

### Full Check: Run Each Pipeline

1. **Plan a feature**:
   ```
   /plan_to_build "add a health check endpoint"
   ```
   Expect: A plan file appears in `specs/`.

2. **Execute the plan**:
   ```
   execute the plan in specs/<plan-name>.md using the build prompt
   ```
   Expect: Builder and validator agents run your test/lint commands.

3. **Fix a bug**:
   ```
   /bug_to_pr "the health check returns wrong status code"
   ```
   Expect: Full pipeline runs — report, route, fix, review, PR.

---

## 9. Examples for Common Tech Stacks

### Python / Django

```json
{
    "name": "my-django-app",
    "description": "Django web application with REST API",
    "modules": {
        "backend": {
            "tech": "Python / Django",
            "paths": ["myapp/", "api/"],
            "description": "Django models, views, serializers, and tests",
            "run": "python manage.py runserver",
            "test": "python manage.py test --verbosity=2",
            "lint": "ruff check .",
            "format": "ruff format --check .",
            "typecheck": "mypy myapp/",
            "fixer_agent": "bug-fixer-backend"
        }
    },
    "default_fixer": "bug-fixer-backend"
}
```

### Node.js / Express + React

```json
{
    "name": "my-fullstack-app",
    "description": "Express API with React frontend",
    "modules": {
        "api": {
            "tech": "Node.js / Express",
            "paths": ["server/"],
            "description": "Express routes, middleware, models, tests",
            "run": "cd server && npm run dev",
            "test": "cd server && npm test",
            "lint": "cd server && npm run lint",
            "fixer_agent": "bug-fixer-backend"
        },
        "web": {
            "tech": "TypeScript / React",
            "paths": ["client/src/"],
            "description": "React components, hooks, pages, tests",
            "run": "cd client && npm run dev",
            "test": "cd client && npm test",
            "lint": "cd client && npm run lint",
            "typecheck": "cd client && npm run typecheck",
            "fixer_agent": "bug-fixer-frontend"
        }
    },
    "default_fixer": "bug-fixer-backend"
}
```

### Go Monorepo

```json
{
    "name": "my-go-services",
    "description": "Go microservices monorepo",
    "modules": {
        "gateway": {
            "tech": "Go / Chi",
            "paths": ["cmd/gateway/", "internal/gateway/"],
            "description": "API gateway — HTTP handlers, middleware, routing",
            "run": "go run ./cmd/gateway",
            "test": "go test ./cmd/gateway/... ./internal/gateway/...",
            "lint": "golangci-lint run ./cmd/gateway/... ./internal/gateway/...",
            "format": "gofmt -l cmd/gateway/ internal/gateway/",
            "fixer_agent": "bug-fixer-go"
        },
        "worker": {
            "tech": "Go",
            "paths": ["cmd/worker/", "internal/worker/"],
            "description": "Background job processor — queue consumer, task handlers",
            "run": "go run ./cmd/worker",
            "test": "go test ./cmd/worker/... ./internal/worker/...",
            "lint": "golangci-lint run ./cmd/worker/... ./internal/worker/...",
            "format": "gofmt -l cmd/worker/ internal/worker/",
            "fixer_agent": "bug-fixer-go"
        }
    },
    "default_fixer": "bug-fixer-go"
}
```

### Java / Spring Boot + Vue

```json
{
    "name": "my-spring-vue-app",
    "description": "Spring Boot API with Vue.js frontend",
    "modules": {
        "api": {
            "tech": "Java / Spring Boot",
            "paths": ["src/main/java/", "src/test/java/"],
            "description": "Spring Boot controllers, services, repositories, tests",
            "run": "./mvnw spring-boot:run",
            "test": "./mvnw test",
            "lint": "./mvnw checkstyle:check",
            "format": "./mvnw spotless:check",
            "fixer_agent": "bug-fixer-java"
        },
        "web": {
            "tech": "TypeScript / Vue 3",
            "paths": ["frontend/src/"],
            "description": "Vue components, composables, Pinia stores, tests",
            "run": "cd frontend && npm run dev",
            "test": "cd frontend && npm run test:unit",
            "lint": "cd frontend && npm run lint",
            "typecheck": "cd frontend && npx vue-tsc --noEmit",
            "fixer_agent": "bug-fixer-frontend"
        }
    },
    "default_fixer": "bug-fixer-java"
}
```

### Rust

```json
{
    "name": "my-rust-service",
    "description": "Rust HTTP service with Axum",
    "modules": {
        "service": {
            "tech": "Rust / Axum",
            "paths": ["src/"],
            "description": "Axum handlers, middleware, domain models, tests",
            "run": "cargo run",
            "test": "cargo test",
            "lint": "cargo clippy -- -D warnings",
            "format": "cargo fmt --check",
            "fixer_agent": "bug-fixer-backend"
        }
    },
    "default_fixer": "bug-fixer-backend"
}
```

---

## 10. Troubleshooting

### "The agent doesn't know my project's commands"

The agent probably isn't reading `project.json`. Check:
- Is the file at exactly `.github/project.json`? (Not `project.json` in the root.)
- Is the JSON valid? Run: `python3 -c "import json; json.load(open('.github/project.json'))"`

### "Lint doesn't run when I save a file"

The `post_tool_validator.py` hook matches files to modules using path prefixes. Check:
- Does your `paths` array match where your source files actually live?
- Do paths end with `/`?
- Does the directory in your `cd` command actually exist?

### "The bug-router picks the wrong module"

The router matches file paths from the bug report against `bug-modules.json` paths. Check:
- Are your `paths` arrays specific enough? (e.g., `["src/api/"]` not just `["src/"]` if multiple modules share `src/`)
- Do affected files in the bug report actually fall under the expected module's paths?

### "I get 'command not found' errors"

The commands in `project.json` must be installed and available on your machine:
- For Python: `pip install ruff pytest` (or whatever your lint/test tools are)
- For Node.js: `npm install` in each module directory
- For Java: `./mvnw` wrapper should be committed to the repo
- For Go: `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest`

### "I only have one module — do I still need all this?"

Yes, but it's simpler. Just define one module in `project.json` and set it as the `default_fixer`. You can use `bug-fixer-backend` for any language.

---

## Quick Reference: Minimum Viable Setup

If you just want to get started fast, here's the absolute minimum:

1. Copy `.github/` to your project
2. Replace `.github/project.json` with:

```json
{
    "name": "my-project",
    "description": "What my project does",
    "modules": {
        "app": {
            "tech": "Your Language / Your Framework",
            "paths": ["src/"],
            "description": "What's in src/",
            "test": "your test command here",
            "lint": "your lint command here",
            "fixer_agent": "bug-fixer-backend"
        }
    },
    "default_fixer": "bug-fixer-backend"
}
```

3. Replace `.github/bug-modules.json` with:

```json
{
    "modules": {
        "app": {
            "fixer": "bug-fixer-backend",
            "paths": ["src/"],
            "test_command": "your test command here"
        }
    },
    "default_fixer": "bug-fixer-backend"
}
```

4. Update `.github/copilot-instructions.md` to describe your project
5. Open VS Code, start Copilot Chat in Agent mode, and try `/plan_to_build "add a feature"`

That's it. You're running.
