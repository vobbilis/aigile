---
applyTo: "specs/**/*.md"
description: "Enforces planning-only behaviour when generating specs for the metrics-dashboard project."
---

# Metrics Dashboard — Planning Standards

When creating or editing files in `specs/`:

- **Never write implementation code** in a plan document
- **Never edit** `backend/` or `frontend/` source files as part of producing a plan
- Every task must have: Task ID, Depends On, Assigned To (builder or validator), Parallel flag
- Every builder task must be followed by a validator task
- Final task must always be `validate-all`

## Project-specific task types

- `backend-task` — changes to `backend/` Python files
- `frontend-task` — changes to `frontend/src/` TypeScript/React files
- `test-task` — adds or updates tests
- `config-task` — CI, tooling, config files
