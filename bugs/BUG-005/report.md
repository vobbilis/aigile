# Bug Report: BUG-005

| Field    | Value                |
| -------- | -------------------- |
| ID       | BUG-005              |
| Type     | Bug                  |
| Severity | High                 |
| Priority | High                 |
| Status   | Open                 |
| Reporter | bug-creator          |
| Assignee | Unassigned           |
| Module   | backend, frontend    |
| Labels   | export, filtering, csv |
| Created  | 2026-03-15T00:00:00Z |

## Summary

Exporting metrics as CSV always downloads the full unfiltered dataset — active tag filters are silently ignored. The backend `/metrics/export` endpoint calls `store.all()` with no tag parameter support, and the frontend export button is a hardcoded `<a href>` link that never passes the current `activeTags` state. Users who have filtered the dashboard to a specific environment or service tag will receive all metrics in the export regardless, with no warning that their filter was discarded.

## Steps to Reproduce

1. Start the backend: `cd backend && uvicorn main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Submit several metrics with mixed tags, e.g.:
   - `POST /metrics` `{"name": "cpu", "value": 10.0, "tags": {"env": "prod"}}`
   - `POST /metrics` `{"name": "mem", "value": 20.0, "tags": {"env": "staging"}}`
   - `POST /metrics` `{"name": "disk", "value": 30.0, "tags": {}}`
4. In the dashboard UI, activate the tag filter `env:prod` — the metric grid correctly shows only the `cpu` metric
5. Click the **Export CSV** button in the header
6. Open the downloaded `metrics.csv`
7. Observe that the CSV contains **all 3 metrics** (`cpu`, `mem`, `disk`), not just the filtered `cpu` metric

## Expected Behavior

The exported CSV should contain only the metrics that match the currently active tag filters. If a user has filtered the dashboard to `env:prod`, the CSV download should contain only `env:prod` metrics — exactly the same dataset visible in the metric grid.

## Actual Behavior

The CSV always contains all metrics regardless of active filters. Two independent bugs cause this:

1. **Backend**: `GET /metrics/export` accepts no `tag` query parameters. It unconditionally calls `store.all()` which returns every metric in the store. Even if `?tag=env:prod` is appended manually to the export URL, the parameter is silently ignored — FastAPI does not raise a validation error, it simply discards the unknown query parameter.

2. **Frontend**: The Export CSV button is a static anchor tag with a hardcoded URL:
   ```tsx
   <a href="/api/metrics/export?format=csv" className="export-btn" download="metrics.csv">
   ```
   The `activeTags` state variable is never referenced when constructing this link. Even after the backend is fixed to accept `tag` query params, the frontend would still download the unfiltered dataset.

**Reproduction proof** (backend test):
```
Filtered GET /metrics?tag=env:prod: 1 metric(s)
Export with tag=env:prod HTTP status: 200
Export CSV content:
id,name,value,tags,timestamp
294e8d9d-...,cpu,10.0,"{""env"": ""prod""}",2026-03-15 17:26:06.464163+00:00
0f4bc8fc-...,mem,20.0,"{""env"": ""staging""}",2026-03-15 17:26:06.465672+00:00
a2c58364-...,disk,30.0,{},2026-03-15 17:26:06.466198+00:00

RESULT: Export returned 3 data rows (should be 1 if filtered, but got ALL)
```

## Environment

- Python: 3.11.8
- FastAPI: 0.115.6
- Node: v18+
- React: 18.3.1
- Vite: 6.0.3
- OS: Darwin (macOS 25.3.0)
- Branch: `fix/bug-005`

## Severity

**High** — This is a data leakage / correctness bug. Users relying on exports for reporting, alerting pipelines, or compliance audits will unknowingly receive unfiltered data. The bug is silent — there is no error, warning, or indication that the filter was ignored. In multi-tenant or multi-environment deployments, exporting from a filtered view may leak data from other environments.

## Module/Area

Both **backend** and **frontend** modules are affected:

- `backend/main.py` line 76–102 — `export_metrics()` function: no `tag` query param, calls `store.all()` unconditionally
- `backend/store.py` line 27–28 — `all()` method returns all data with no filtering
- `frontend/src/App.tsx` line 68–70 — hardcoded export `<a href>` never includes `activeTags`

The store already has a working `filter_by_tags()` method (`store.py` lines 30–36) that is used by `GET /metrics`. The export endpoint simply does not call it.

## Evidence

### Backend: `export_metrics` calls `store.all()` unconditionally

**File**: `backend/main.py` lines 76–82

```python
@app.get("/metrics/export")
def export_metrics(format: str = "csv") -> StreamingResponse:
    if format != "csv":
        raise HTTPException(status_code=400, detail="Unsupported format. Use format=csv")

    # Get all metrics
    metrics = store.all()   # <-- no tag filtering, no tag parameter accepted
```

No `tag` parameter is declared in the function signature (unlike `list_metrics` at line 57 which has `tag: list[str] = Query(default=[])`).

### Backend: `store.all()` returns everything

**File**: `backend/store.py` lines 27–28

```python
def all(self) -> list[MetricOut]:
    return list(self._data)
```

No filtering logic. Compare with `filter_by_tags()` at lines 30–36 which correctly filters on tag key/value pairs — but is never called by the export endpoint.

### Backend: `list_metrics` has tag support; `export_metrics` does not

**File**: `backend/main.py` lines 56–67

```python
@app.get("/metrics", response_model=list[MetricOut])
def list_metrics(tag: list[str] = Query(default=[])) -> list[MetricOut]:
    parsed_tags: list[tuple[str, str]] = []
    for t in tag:
        ...
    return store.filter_by_tags(parsed_tags)
```

The `GET /metrics` endpoint correctly accepts and applies `tag` query params. The export endpoint lacks equivalent support.

### Frontend: hardcoded export URL ignores `activeTags`

**File**: `frontend/src/App.tsx` lines 68–70

```tsx
<a href="/api/metrics/export?format=csv" className="export-btn" download="metrics.csv">
  Export CSV
</a>
```

`activeTags` (defined at line 15: `const [activeTags, setActiveTags] = useState<string[]>([])`) is never referenced in this element. The URL is a compile-time constant with no dynamic construction.

### Live reproduction output

```
$ python -c "
from fastapi.testclient import TestClient
from main import app, store
store.clear()
client = TestClient(app)
client.post('/metrics', json={'name': 'cpu', 'value': 10.0, 'tags': {'env': 'prod'}})
client.post('/metrics', json={'name': 'mem', 'value': 20.0, 'tags': {'env': 'staging'}})
client.post('/metrics', json={'name': 'disk', 'value': 30.0, 'tags': {}})
filtered = client.get('/metrics?tag=env:prod')
print('Filtered GET /metrics?tag=env:prod:', len(filtered.json()), 'metric(s)')
export = client.get('/metrics/export?format=csv&tag=env:prod')
print('Export with tag=env:prod HTTP status:', export.status_code)
print(export.text)
print('Export returned', export.text.count(chr(10)) - 1, 'data rows')
"

Filtered GET /metrics?tag=env:prod: 1 metric(s)
Export with tag=env:prod HTTP status: 200
id,name,value,tags,timestamp
294e8d9d-f742-41d7-860c-635a541a9338,cpu,10.0,"{""env"": ""prod""}",2026-03-15 17:26:06.464163+00:00
0f4bc8fc-48d2-4f83-a386-1c748739d6eb,mem,20.0,"{""env"": ""staging""}",2026-03-15 17:26:06.465672+00:00
a2c58364-d6f1-4c24-85b0-abbf35a61ef0,disk,30.0,{},2026-03-15 17:26:06.466198+00:00

Export returned 3 data rows (expected 1)
```

## Root Cause Analysis

**Root cause 1 (backend)**: `export_metrics()` in `backend/main.py:82` calls `store.all()` instead of `store.filter_by_tags()`. The function signature does not declare a `tag` query parameter, so no filtering is possible regardless of what the client sends. The fix pattern already exists in `list_metrics()` at line 57.

**Root cause 2 (frontend)**: The export button at `frontend/src/App.tsx:68` is a static `<a href>` element. It was implemented before tag filtering was added to the application and was never updated to be filter-aware. It must be converted to a dynamic `<button>` (or computed `href`) that constructs the export URL from `activeTags` state, appending `&tag=key:value` for each active tag.

## Acceptance Criteria

**Fixed** means:

1. `GET /metrics/export` accepts one or more `tag=key:value` query parameters (same format as `GET /metrics`)
2. When tag params are present, only matching metrics appear in the exported CSV (uses `store.filter_by_tags()`)
3. When no tag params are provided, all metrics are exported (backward compatible with existing behavior)
4. Frontend export button constructs the URL dynamically from `activeTags` state
5. If no tags are active, the export URL is `/api/metrics/export?format=csv` (unchanged behavior)
6. If tags are active (e.g., `["env:prod", "service:api"]`), the URL becomes `/api/metrics/export?format=csv&tag=env:prod&tag=service:api`
7. Backend test: `test_metrics_export_csv_tag_filter` — export with `tag=env:prod` returns only `env:prod` metrics
8. Frontend test: export button href updates when `activeTags` changes
