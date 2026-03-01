# Adapt Pipelines to Your Project — Just Ask Copilot

No manual file editing required. Open VS Code with Copilot Chat in **Agent mode** and paste these prompts in order.

> **Time**: ~5 minutes  
> **Prerequisites**: VS Code + GitHub Copilot Chat  
> **You provide**: Your project's language, framework, directory structure, and toolchain

---

## Before You Start

Copy the `.github/` folder from this repository into your project root:

```bash
cp -r .github /path/to/your-project/.github
```

Then open your project in VS Code and start Copilot Chat in Agent mode.

---

## Step 1: Generate Your project.json

Paste this prompt (fill in the blanks first):

```
Read .github/project.json to understand the format.

Now create a new .github/project.json for MY project with these modules:

Module 1:
- Name: ___________  (e.g., "api", "backend", "service")
- Tech: ___________  (e.g., "Python / Django", "Go / Gin", "Java / Spring Boot")
- Source directory: ___________  (e.g., "src/", "api/", "server/")
- Run command: ___________  (e.g., "python manage.py runserver")
- Test command: ___________  (e.g., "pytest", "go test ./...", "npm test")
- Lint command: ___________  (e.g., "ruff check .", "golangci-lint run")
- Format command: ___________  (optional)
- Typecheck command: ___________  (optional)

Module 2 (if you have one):
- Name: ___________
- Tech: ___________
- Source directory: ___________
- Test/lint/run commands: ___________

Use "bug-fixer-backend" for server-side modules,
"bug-fixer-frontend" for UI modules,
"bug-fixer-java" for Java/Kotlin,
"bug-fixer-go" for Go.

Set the default_fixer to whichever module is primary.
Write the file to .github/project.json.
```

---

## Step 2: Generate Your bug-modules.json

```
Read the .github/project.json you just created.
Now update .github/bug-modules.json to match — same modules,
same paths, same test commands, same fixer agents.
Keep the _note field that says it's derived from project.json.
```

---

## Step 3: Update copilot-instructions.md

```
Read .github/copilot-instructions.md to understand the format.
Read .github/project.json to understand my project.

Now rewrite .github/copilot-instructions.md for MY project.
Keep the same section structure (Code Style, Architecture,
Build and Test, API contract, Test patterns, Agent workflow,
Conventions, Dependency Management) but replace all
aigile specifics with my project's details.

For sections you can't fill in from project.json alone,
add a TODO comment so I know to fill those in later.
```

---

## Step 4: Verify

```
Read .github/project.json and .github/bug-modules.json.
Verify:
1. project.json is valid JSON
2. bug-modules.json is valid JSON
3. Every module in project.json has a matching entry in bug-modules.json
4. Every fixer_agent referenced exists as a .github/agents/bug-fixer-*.agent.md file
5. All paths end with /

Report any issues found.
```

---

## Step 5: Smoke Test

```
/plan_to_build "add a health check endpoint"
```

If it produces a plan file in `specs/`, everything is working.

---

## That's It

You now have fully adapted pipelines. Use them:

| What you want to do  | Prompt                                                       |
| -------------------- | ------------------------------------------------------------ |
| Plan a feature       | `/plan_to_build "your feature description"`                  |
| Execute a plan       | `execute the plan in specs/<name>.md using the build prompt` |
| Fix a bug end-to-end | `/bug_to_pr "describe the bug"`                              |

---

## One-Module Shortcut

If your project is a single-language codebase, paste this single prompt:

```
Read .github/project.json to understand the format.

My project is a single _________ (language/framework) codebase.
Source code is in _________ (directory).
Test command: _________
Lint command: _________

Create .github/project.json with one module called "app"
using bug-fixer-backend as the fixer agent.
Then update .github/bug-modules.json to match.
Then update .github/copilot-instructions.md with a basic
description of my project, marking sections you can't determine
as TODO.
```

---

## Adding a New Language Later

```
Read .github/project.json.

Add a new module:
- Name: ___________
- Tech: ___________
- Directory: ___________
- Test/lint commands: ___________

Update both .github/project.json and .github/bug-modules.json.
If no existing bug-fixer agent fits this language, create a new one
at .github/agents/bug-fixer-<name>.agent.md by copying
bug-fixer-backend.agent.md and adapting the module name
and language-specific hints.
```
