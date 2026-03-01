# Plan: Add CSV Export Endpoint

> **EXECUTION DIRECTIVE**: This is a team-orchestrated plan.
> **FORBIDDEN**: Direct implementation by the main agent. If you are the main conversation agent and a user asks you to implement this plan, you MUST use the `build` prompt with this spec file — do NOT implement it yourself.
> **REQUIRED**: Execute ONLY via the `build` prompt, which orchestrates sub-agents to do the work.

## Task Description
Add a `GET /metrics/export?format=csv` endpoint to the backend that returns all stored metrics as a downloadable CSV file. The response uses `Content-Type: text/csv` and `Content-Disposition: attachment; filename="metrics.csv"` headers so browsers and curl both download it correctly. In the frontend, add a small "Export CSV" button in the dashboard header that links to this endpoint. The button should use a plain `<a>` tag pointing at `/api/metrics/export?format=csv` — no JavaScript fetch needed since the Vite proxy forwards `/api` to the backend.

## Objective
When complete, users can click "Export CSV" in the header (or hit the endpoint directly via curl) to download all current metrics as a CSV file with columns: `id, name, value, tags, timestamp`. The backend generates the CSV using Python's built-in `csv` module. If no metrics exist, the CSV contains only the header row.

## Relevant Files
Use these files to complete the task:

- `backend/main.py` — Add the new `/metrics/export` route here, following the existing route patterns (`@app.get` decorator, type annotations, docstring-free style)
- `backend/store.py` — Read-only reference. The `store.all()` method returns `list[MetricOut]` which is the data source for the CSV
- `backend/models.py` — Read-only reference. `MetricOut` has fields: `id: str`, `name: str`, `value: float`, `tags: dict[str, str]`, `timestamp: datetime`
- `backend/tests/test_api.py` — Add CSV export tests here, following the existing pattern: module-level `client = TestClient(app)`, `autouse` fixture clears store, assertions on status code + body content
- `frontend/src/App.tsx` — Add the Export CSV button in the `<header>` element, next to the existing poll indicator `<span>`
- `.github/project.json` — Read-only reference for validation commands

## Team Orchestration

- The `build` prompt instructs the main agent to act as a **sequential orchestrator**, dispatching sub-agents one task at a time in dependency order.
- The plan is the **single source of truth**. The orchestrator does NOT make decisions. Everything must be specified here: team members, task assignments, dependencies, and exhaustive task descriptions.
- Agents are stateless and cannot ask for clarification. Every task description must be fully self-contained with all context needed for autonomous execution.

### Team Members

- Builder
  - Name: builder-1
  - Role: Implements the backend CSV endpoint, backend tests, and frontend button
  - Agent Type: builder
- Validator
  - Name: validator
  - Role: Validates all acceptance criteria and runs validation commands
  - Agent Type: validator

## Step by Step Tasks

### 1. Add CSV Export Endpoint to Backend
- **Task ID**: add-csv-export-route
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder-1
- **Description**: |
    Add a new route `GET /metrics/export` to `backend/main.py` that returns all metrics as a downloadable CSV file.

    ## What to do
    1. Add `import csv` and `import io` at the top of `backend/main.py` (both are Python stdlib — no new dependencies).
    2. Add `from fastapi.responses import StreamingResponse` to the existing FastAPI imports.
    3. Add a new route **above** the `@app.get("/metrics/{name}/history")` route (to avoid path conflicts — FastAPI matches routes top-down, and `/metrics/export` would match `{name}` if placed after it).
    4. The route function signature: `def export_metrics(format: str = "csv") -> StreamingResponse`.
    5. If `format != "csv"`, raise `HTTPException(status_code=400, detail="Unsupported format. Use format=csv")`.
    6. Call `store.all()` to get all metrics.
    7. Write CSV to a `StringIO` buffer using `csv.writer`. Columns: `id`, `name`, `value`, `tags`, `timestamp`. For the `tags` column, serialize the dict as a JSON string (add `import json` if needed).
    8. Return `StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="metrics.csv"'})`.

    ## Files to modify
    - `backend/main.py` — Add imports (`csv`, `io`, `json`, `StreamingResponse`) and the new route function.

    ## Code patterns to follow
    Existing route pattern in `main.py`:
    ```python
    @app.get("/metrics/summary", response_model=MetricSummary)
    def metrics_summary() -> MetricSummary:
        data = store.summary()
        return MetricSummary(**data)
    ```
    Follow the same style: `@app.get` decorator, type-annotated parameters, explicit return type.

    ## Acceptance criteria
    - `GET /metrics/export?format=csv` with no data returns 200 with CSV header row only: `id,name,value,tags,timestamp\r\n`
    - `GET /metrics/export?format=csv` after posting a metric returns CSV with header + 1 data row containing the metric's id, name, value, tags as JSON, and timestamp
    - `GET /metrics/export?format=json` returns 400 with `{"detail": "Unsupported format. Use format=csv"}`
    - Response `Content-Type` is `text/csv; charset=utf-8`
    - Response has `Content-Disposition: attachment; filename="metrics.csv"` header

    ## Validation command
    ```bash
    cd backend && python -c "from main import app; print('import ok')"
    ```

### 2. Add Backend Tests for CSV Export
- **Task ID**: add-csv-export-tests
- **Role**: builder
- **Depends On**: add-csv-export-route
- **Assigned To**: builder-1
- **Description**: |
    Add tests for the CSV export endpoint in `backend/tests/test_api.py`.

    ## What to do
    1. Add the following test functions to `backend/tests/test_api.py`, following the existing test style (bare functions, `client.get(...)`, assertions on `r.status_code` and `r.text` / `r.headers`).
    2. Tests to add:

    **test_export_csv_empty** — No metrics in store. `GET /metrics/export?format=csv` returns 200. Body is `id,name,value,tags,timestamp\r\n` (header row only). `Content-Type` contains `text/csv`. `Content-Disposition` header contains `metrics.csv`.

    **test_export_csv_with_data** — Post two metrics: `{"name": "cpu", "value": 42.5}` and `{"name": "mem", "value": 75.0, "tags": {"host": "web1"}}`. `GET /metrics/export?format=csv` returns 200. Body has 3 lines (header + 2 data rows). First data row contains `cpu` and `42.5`. Second data row contains `mem`, `75.0`, and `web1`. Parse with `csv.reader` from `io.StringIO(r.text)` to verify field count is 5 per row.

    **test_export_csv_unsupported_format** — `GET /metrics/export?format=json` returns 400. `r.json()["detail"]` contains "Unsupported format".

    ## Files to modify
    - `backend/tests/test_api.py` — Add three test functions at the end of the file.

    ## Code patterns to follow
    Existing test pattern:
    ```python
    def test_health():
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
    ```
    Follow this flat style — no classes, no nested fixtures beyond the autouse `clear_store`.

    ## Acceptance criteria
    - `test_export_csv_empty` passes: verifies header-only CSV on empty store
    - `test_export_csv_with_data` passes: verifies CSV rows match posted metrics, parses with `csv.reader`, checks 5 columns per row
    - `test_export_csv_unsupported_format` passes: verifies 400 status and error message
    - All 47 existing tests still pass (no regressions)

    ## Validation command
    ```bash
    cd backend && pytest tests/ -v -k "export"
    ```

### 3. Add Export CSV Button to Frontend
- **Task ID**: add-export-button-frontend
- **Role**: builder
- **Depends On**: add-csv-export-route
- **Assigned To**: builder-1
- **Description**: |
    Add a small "Export CSV" button in the frontend dashboard header that links to the CSV export endpoint.

    ## What to do
    1. Open `frontend/src/App.tsx`.
    2. In the `<header>` element, after the existing `<span className="poll-indicator">` element, add an `<a>` tag:
       ```tsx
       <a href="/api/metrics/export?format=csv" className="export-btn" download="metrics.csv">
         Export CSV
       </a>
       ```
    3. The `href` uses `/api/` prefix because the Vite proxy strips `/api` before forwarding to the backend.
    4. The `download` attribute ensures the browser downloads instead of navigating.
    5. No new API function in `api.ts` is needed — this is a plain link, not a fetch call.
    6. Add minimal CSS for the button. In the existing CSS file used by App.tsx (check for `import './..css'` statements), add:
       ```css
       .export-btn {
         margin-left: 1rem;
         padding: 0.25rem 0.75rem;
         background: #2563eb;
         color: white;
         border-radius: 4px;
         text-decoration: none;
         font-size: 0.875rem;
       }
       .export-btn:hover {
         background: #1d4ed8;
       }
       ```

    ## Files to modify
    - `frontend/src/App.tsx` — Add the `<a>` tag inside the `<header>` element after the poll indicator span.
    - CSS file imported by App.tsx — Add `.export-btn` styles.

    ## Code patterns to follow
    Existing header in App.tsx:
    ```tsx
    <header>
      <h1>Metrics Dashboard</h1>
      <span className="poll-indicator">
        polling every {POLL_INTERVAL_MS / 1000}s
      </span>
    </header>
    ```
    Add the `<a>` tag after the `</span>` and before `</header>`.

    ## Acceptance criteria
    - The header shows an "Export CSV" link/button next to the poll indicator
    - Clicking it navigates to `/api/metrics/export?format=csv` which triggers a CSV download
    - The link has `className="export-btn"` and `download="metrics.csv"` attributes
    - TypeScript compiles without errors (`npm run typecheck` passes)
    - ESLint passes (`npm run lint` passes)

    ## Validation command
    ```bash
    cd frontend && npm run typecheck && npm run lint
    ```

### 4. Final Validation
- **Task ID**: validate-all
- **Role**: validator
- **Depends On**: add-csv-export-route, add-csv-export-tests, add-export-button-frontend
- **Assigned To**: validator
- **Description**: |
    Run all validation commands and verify all acceptance criteria.

    ## Validation Commands
    Run these commands and verify they all pass:
    ```bash
    cd backend && pytest tests/ -v
    ```
    ```bash
    cd backend && ruff check .
    ```
    ```bash
    cd backend && ruff format --check .
    ```
    ```bash
    cd frontend && npm run typecheck
    ```
    ```bash
    cd frontend && npm run lint
    ```
    ```bash
    cd frontend && npm test -- --run
    ```

    ## Acceptance Criteria
    - Backend: `GET /metrics/export?format=csv` with no data returns 200 with header-only CSV
    - Backend: `GET /metrics/export?format=csv` with data returns CSV with correct columns and rows
    - Backend: `GET /metrics/export?format=json` returns 400 with error detail
    - Backend: Response has `Content-Type: text/csv` and `Content-Disposition: attachment` headers
    - Backend: All 50 tests pass (47 existing + 3 new export tests)
    - Backend: Ruff check and format pass clean
    - Frontend: "Export CSV" link appears in the header
    - Frontend: TypeScript compiles without errors
    - Frontend: ESLint passes with zero warnings
    - Frontend: All 18 existing tests still pass

## Acceptance Criteria
- `GET /metrics/export?format=csv` returns 200 with `Content-Type: text/csv` and `Content-Disposition: attachment; filename="metrics.csv"`
- Empty store returns CSV with header row only: `id,name,value,tags,timestamp`
- Store with metrics returns CSV with header + one row per metric, tags serialized as JSON
- `GET /metrics/export?format=json` returns 400 with descriptive error
- Frontend header contains an "Export CSV" link pointing to `/api/metrics/export?format=csv`
- All backend tests pass (47 existing + 3 new)
- All frontend tests pass (18 existing)
- Ruff, ESLint, and TypeScript typecheck all pass clean

## Validation Commands
Execute these commands to validate the task is complete:

```bash
cd backend && pytest tests/ -v
cd backend && ruff check .
cd backend && ruff format --check .
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm test -- --run
```

## Notes
- **Brainstorming skip**: User chose approach (a) — backend-only CSV — from three options presented. No further exploration needed.
- **Team composition skip**: Simple feature with ≤5 tasks — single builder per the skip rules.
- **Path ordering matters**: The `/metrics/export` route MUST be registered above `/metrics/{name}` in `main.py` to avoid FastAPI matching `export` as a metric name.
- **No new dependencies**: Uses Python stdlib `csv`, `io`, `json` and FastAPI's built-in `StreamingResponse`.
- **Self-audit**: 3 builder tasks + 1 validator task. All builder descriptions ≥50 words. All have design assertions and validation commands. Final `validate-all` present. No intermediate validator needed (≤5 builder tasks).
