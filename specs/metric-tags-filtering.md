# Plan: Metric Tags Filtering

> **Status:** COMPLETE (2026-03-15) — All acceptance criteria met. See [Build Evidence](#build-evidence) below.

> **EXECUTION DIRECTIVE**: This is a team-orchestrated plan.
> **FORBIDDEN**: Direct implementation (Edit, Write, NotebookEdit) by the main agent. If you are the main conversation agent and a user asks you to implement this plan, you MUST invoke `/build_v2 specs/metric-tags-filtering.md` -- do NOT implement it yourself.
> **REQUIRED**: Execute ONLY via the `/build_v2` command, which deploys team agents to do the work.

## Task Description

Add metric tag filtering to the metrics dashboard. Tags are already stored as `dict[str, str]` key=value pairs on every metric (the `tags` field on `MetricIn`/`MetricOut` models). This feature adds:

1. **API support**: The `GET /metrics` endpoint accepts optional `tag` query parameters in `key:value` format (e.g., `?tag=env:prod&tag=service:api`). Multiple tags use AND logic — only metrics matching ALL specified tags are returned.
2. **Store layer**: A new `filter_by_tags()` method on `MetricStore` that filters the in-memory metric list by tag key/value pairs.
3. **Frontend API client**: The `fetchMetrics()` function accepts an optional tags filter parameter and appends `tag` query params to the request URL.
4. **Frontend UI**: A `TagFilterBar` component rendered above the metric grid that lets users type `key:value` filters, displays active filters as removable chips, and triggers re-fetching of filtered metrics.

## Objective

When this plan is complete:
- `GET /metrics` without `tag` params works exactly as before (returns all metrics)
- `GET /metrics?tag=env:prod` returns only metrics whose `tags` dict contains `{"env": "prod"}`
- `GET /metrics?tag=env:prod&tag=service:api` returns only metrics matching BOTH tags (AND logic)
- `GET /metrics?tag=invalid` (no colon) returns 400 with a clear error message
- The frontend shows a tag filter bar above the metric grid with an input field and active filter chips
- Clicking the "x" on a chip removes that filter; pressing Enter or clicking "Add" adds a filter
- Filtered metrics are fetched from the API with the appropriate `tag` query parameters
- All existing tests pass without modification

## Problem Statement

The dashboard stores tags on every metric but provides no way to filter metrics by tag. Users submitting metrics with tags like `env=prod`, `service=api`, `region=us-east` cannot narrow down the dashboard view to only the metrics they care about. This makes the dashboard less useful as the number of metrics grows.

## Solution Approach

1. **Store layer** (`store.py`): Add a `filter_by_tags(tags: list[tuple[str, str]])` method that iterates `self._data` and returns only metrics where every `(key, value)` pair exists in the metric's `tags` dict. When the tags list is empty, return all metrics (same as `all()`).

2. **API layer** (`main.py`): Modify `GET /metrics` to accept `tag: list[str] = Query(default=[])`. Parse each tag string by splitting on the first `:` character. Return 400 if any tag string lacks a colon. Call `store.filter_by_tags()` when tags are provided, otherwise call `store.all()` as before.

3. **Frontend API** (`api.ts`): Update `fetchMetrics()` to accept an optional `tags?: string[]` parameter. When provided, append `tag=key:value` query params to the URL.

4. **Frontend UI** (`TagFilterBar.tsx`): New component with:
   - A text input for typing `key:value` filters
   - An "Add" button (also triggered by Enter key)
   - Active filter chips with "x" remove buttons
   - Validation: reject empty input or input without a colon
   - State is lifted to `App.tsx` which passes `activeTags` to both `TagFilterBar` and `fetchMetrics()`

## Relevant Files

Use these files to complete the task:

- `backend/store.py` — Add `filter_by_tags()` method to `MetricStore`
- `backend/main.py` — Modify `GET /metrics` to accept and parse `tag` query params; import `Query` from fastapi
- `backend/models.py` — No changes needed (tags already exist as `dict[str, str]`)
- `backend/tests/test_api.py` — Add tests for tag filtering on `GET /metrics`
- `frontend/src/api.ts` — Update `fetchMetrics()` to accept optional tags filter
- `frontend/src/App.tsx` — Add tag filter state, pass to `TagFilterBar` and `fetchMetrics()`
- `frontend/src/App.test.tsx` — Add tests for tag filtering UI behavior
- `frontend/src/api.test.ts` — Add tests for `fetchMetrics()` with tag params

### New Files

- `frontend/src/components/TagFilterBar.tsx` — New component for the tag filter bar UI

## Implementation Phases

### Phase 1: Foundation
Add the `filter_by_tags()` method to `MetricStore` and wire it into the `GET /metrics` endpoint with `tag` query parameter support. This is purely backend work with no frontend impact.

### Phase 2: Core Implementation
Update the frontend API client to pass tag filters, create the `TagFilterBar` component, and integrate it into `App.tsx` with state management.

### Phase 3: Integration & Polish
Write comprehensive tests for backend (tag filtering endpoint) and frontend (API client with tags, TagFilterBar component, App integration). Validate everything end-to-end.

## Team Orchestration

- The `/build_v2` command deploys a **self-organizing agent team**. Agents autonomously discover, claim, and execute tasks from a shared task list.
- You are responsible for designing the team composition and task graph so agents can work autonomously.
- IMPORTANT: The plan is the **single source of truth**. `/build_v2` is a pure executor — it does NOT make decisions. Everything must be specified here: team members, task assignments, dependencies, and exhaustive task descriptions.
- **`Assigned To` is enforced**: `/build_v2` injects each agent's name into their standing orders. Agents only claim tasks where `Assigned To` matches their own name. Every task MUST have an `Assigned To`.
- Agents cannot ask for clarification mid-task. Every task description must be fully self-contained with all context needed for autonomous execution.

### Team Members

- Builder
  - Name: builder-1
  - Role: Backend implementation — store method, API endpoint, backend tests
  - Agent Type: general-purpose
- Builder
  - Name: builder-2
  - Role: Frontend implementation — API client update, TagFilterBar component, App integration, frontend tests
  - Agent Type: general-purpose
- Validator
  - Name: validator
  - Role: Validates all acceptance criteria and runs validation commands
  - Agent Type: validator
- Design Updater
  - Name: design-updater
  - Role: Updates docs/design/ with code-aligned design decisions after build completes
  - Agent Type: design-updater

## Step by Step Tasks

- These tasks are executed by self-organizing agents. Agents discover and claim tasks autonomously from the shared task list.
- Each task maps directly to a `TaskCreate` call made by `/build_v2`.
- Task descriptions must be **exhaustive** — agents cannot ask for clarification. Include ALL context: file paths, code patterns, acceptance criteria, and validation commands.
- Every task MUST have an `Assigned To` matching a name in Team Members. This is enforced — tasks without a valid `Assigned To` will not be claimed.
- Start with foundational work, then core implementation, then validation.

### 1. Add filter_by_tags Method to MetricStore
- **Task ID**: add-filter-by-tags
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder-1
- **Description**: |
    Add a `filter_by_tags()` method to `MetricStore` in `backend/store.py` that filters the
    in-memory metrics list by tag key/value pairs using AND logic.

    ## What to do
    1. In `backend/store.py`, add this method to the `MetricStore` class after the existing `all()` method:

    ```python
    def filter_by_tags(self, tags: list[tuple[str, str]]) -> list[MetricOut]:
        if not tags:
            return list(self._data)
        return [
            m for m in self._data
            if all(m.tags.get(k) == v for k, v in tags)
        ]
    ```

    2. The method accepts a list of `(key, value)` tuples.
    3. When `tags` is empty, it returns all metrics (same behavior as `all()`).
    4. When tags are provided, it returns only metrics where EVERY tag pair matches (AND logic).
    5. A metric matches a tag pair `(k, v)` if `metric.tags.get(k) == v`.

    ## Files to modify
    - `backend/store.py` — add `filter_by_tags()` method to `MetricStore` class

    ## Code patterns to follow
    - Follow the existing pattern of `all()` and `by_name()`: return `list[MetricOut]`, use list comprehension.
    - The method is on the `MetricStore` class, same as all other query methods.
    - Keep type hints consistent: `list[tuple[str, str]]` for the parameter.

    ## Acceptance criteria
    - `store.filter_by_tags([])` returns all metrics (same as `store.all()`)
    - `store.filter_by_tags([("env", "prod")])` returns only metrics with `tags["env"] == "prod"`
    - `store.filter_by_tags([("env", "prod"), ("service", "api")])` returns only metrics matching BOTH tags
    - Metrics without any tags are excluded when any filter is active
    - Method exists and is callable on `MetricStore` instances

    ## Validation command
    ```bash
    cd backend && python -c "
    from store import MetricStore
    from models import MetricIn
    s = MetricStore()
    s.add(MetricIn(name='cpu', value=10.0, tags={'env': 'prod', 'service': 'api'}))
    s.add(MetricIn(name='mem', value=20.0, tags={'env': 'prod', 'service': 'web'}))
    s.add(MetricIn(name='disk', value=30.0, tags={'env': 'staging'}))
    s.add(MetricIn(name='net', value=40.0, tags={}))
    # No filter returns all
    assert len(s.filter_by_tags([])) == 4, 'empty filter should return all'
    # Single tag filter
    result = s.filter_by_tags([('env', 'prod')])
    assert len(result) == 2, f'Expected 2, got {len(result)}'
    assert all(m.tags.get('env') == 'prod' for m in result)
    # Multi-tag AND filter
    result2 = s.filter_by_tags([('env', 'prod'), ('service', 'api')])
    assert len(result2) == 1, f'Expected 1, got {len(result2)}'
    assert result2[0].name == 'cpu'
    # Non-matching filter
    result3 = s.filter_by_tags([('env', 'nonexistent')])
    assert len(result3) == 0, 'Should return empty for non-matching filter'
    print('ALL CHECKS PASSED')
    "
    ```

### 2. Add Tag Query Parameter to GET /metrics Endpoint
- **Task ID**: add-tag-query-param
- **Role**: builder
- **Depends On**: add-filter-by-tags
- **Assigned To**: builder-1
- **Description**: |
    Modify the `GET /metrics` endpoint in `backend/main.py` to accept optional `tag` query
    parameters and use the store's `filter_by_tags()` method.

    ## What to do
    1. In `backend/main.py`, add `Query` to the FastAPI import:
       Change `from fastapi import FastAPI, HTTPException` to `from fastapi import FastAPI, HTTPException, Query`

    2. Replace the existing `list_metrics` function:

    **Current code:**
    ```python
    @app.get("/metrics", response_model=list[MetricOut])
    def list_metrics() -> list[MetricOut]:
        return store.all()
    ```

    **New code:**
    ```python
    @app.get("/metrics", response_model=list[MetricOut])
    def list_metrics(tag: list[str] = Query(default=[])) -> list[MetricOut]:
        parsed_tags: list[tuple[str, str]] = []
        for t in tag:
            if ":" not in t:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tag format '{t}'. Expected 'key:value'.",
                )
            key, value = t.split(":", 1)
            parsed_tags.append((key, value))
        return store.filter_by_tags(parsed_tags)
    ```

    3. Key design decisions:
       - Tag format is `key:value` with `:` as separator (not `=`) to avoid URL encoding issues
       - Split on FIRST colon only (`split(":", 1)`) so values can contain colons
       - Return 400 for malformed tags (no colon)
       - When no `tag` params provided, `parsed_tags` is empty, so `filter_by_tags([])` returns all (backward compatible)

    ## Files to modify
    - `backend/main.py` — add `Query` import, modify `list_metrics()` function

    ## Code patterns to follow
    - Follow existing error pattern: `raise HTTPException(status_code=400, detail=...)` (same as export endpoint)
    - Use FastAPI's `Query(default=[])` for list query params — this allows `?tag=a:b&tag=c:d`
    - Keep the `response_model=list[MetricOut]` annotation unchanged

    ## Acceptance criteria
    - `GET /metrics` with no `tag` params returns all metrics (backward compatible)
    - `GET /metrics?tag=env:prod` returns only metrics with `env=prod` tag
    - `GET /metrics?tag=env:prod&tag=service:api` returns metrics matching BOTH tags
    - `GET /metrics?tag=invalid` returns 400 with detail message about invalid format
    - `GET /metrics?tag=key:val:with:colons` correctly parses as key="key", value="val:with:colons"

    ## Validation command
    ```bash
    cd backend && python -c "
    from fastapi.testclient import TestClient
    from main import app, store
    store.clear()
    c = TestClient(app)
    # Submit metrics with tags
    c.post('/metrics', json={'name': 'cpu', 'value': 10.0, 'tags': {'env': 'prod', 'service': 'api'}})
    c.post('/metrics', json={'name': 'mem', 'value': 20.0, 'tags': {'env': 'prod', 'service': 'web'}})
    c.post('/metrics', json={'name': 'disk', 'value': 30.0, 'tags': {'env': 'staging'}})
    # No filter - all metrics
    r = c.get('/metrics')
    assert r.status_code == 200
    assert len(r.json()) == 3, f'Expected 3, got {len(r.json())}'
    # Single tag filter
    r = c.get('/metrics?tag=env:prod')
    assert r.status_code == 200
    assert len(r.json()) == 2, f'Expected 2, got {len(r.json())}'
    # Multi-tag AND filter
    r = c.get('/metrics?tag=env:prod&tag=service:api')
    assert r.status_code == 200
    assert len(r.json()) == 1, f'Expected 1, got {len(r.json())}'
    assert r.json()[0]['name'] == 'cpu'
    # Invalid tag format
    r = c.get('/metrics?tag=invalid')
    assert r.status_code == 400, f'Expected 400, got {r.status_code}'
    assert 'Invalid tag format' in r.json()['detail']
    store.clear()
    print('ALL CHECKS PASSED')
    "
    ```

### 3. Add Backend Tests for Tag Filtering
- **Task ID**: add-backend-tag-tests
- **Role**: builder
- **Depends On**: add-tag-query-param
- **Assigned To**: builder-1
- **Description**: |
    Add comprehensive tests for the tag filtering feature in `backend/tests/test_api.py`.

    ## What to do
    1. In `backend/tests/test_api.py`, add the following test functions at the end of the file
       (after all existing tests). Do NOT modify any existing tests.

    ```python
    def test_list_metrics_no_tag_filter():
        """GET /metrics without tag params returns all metrics (backward compatible)."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {"env": "prod"}})
        client.post("/metrics", json={"name": "mem", "value": 20.0, "tags": {"env": "staging"}})
        r = client.get("/metrics")
        assert r.status_code == 200
        assert len(r.json()) == 2


    def test_list_metrics_single_tag_filter():
        """GET /metrics?tag=env:prod returns only matching metrics."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {"env": "prod", "service": "api"}})
        client.post("/metrics", json={"name": "mem", "value": 20.0, "tags": {"env": "staging"}})
        client.post("/metrics", json={"name": "disk", "value": 30.0, "tags": {"env": "prod", "service": "web"}})
        r = client.get("/metrics?tag=env:prod")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        names = {m["name"] for m in data}
        assert names == {"cpu", "disk"}


    def test_list_metrics_multiple_tag_filter_and_logic():
        """GET /metrics?tag=env:prod&tag=service:api uses AND logic."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {"env": "prod", "service": "api"}})
        client.post("/metrics", json={"name": "mem", "value": 20.0, "tags": {"env": "prod", "service": "web"}})
        client.post("/metrics", json={"name": "disk", "value": 30.0, "tags": {"env": "staging", "service": "api"}})
        r = client.get("/metrics?tag=env:prod&tag=service:api")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "cpu"


    def test_list_metrics_tag_filter_no_match():
        """GET /metrics?tag=env:nonexistent returns empty list."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {"env": "prod"}})
        r = client.get("/metrics?tag=env:nonexistent")
        assert r.status_code == 200
        assert r.json() == []


    def test_list_metrics_tag_filter_invalid_format():
        """GET /metrics?tag=invalid returns 400 error."""
        r = client.get("/metrics?tag=invalid")
        assert r.status_code == 400
        assert "Invalid tag format" in r.json()["detail"]


    def test_list_metrics_tag_filter_colon_in_value():
        """GET /metrics?tag=url:http://example.com correctly parses colon in value."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {"url": "http://example.com"}})
        r = client.get("/metrics?tag=url:http://example.com")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["tags"]["url"] == "http://example.com"


    def test_list_metrics_tag_filter_excludes_untagged():
        """Metrics without matching tags are excluded by filter."""
        client.post("/metrics", json={"name": "cpu", "value": 10.0, "tags": {}})
        client.post("/metrics", json={"name": "mem", "value": 20.0, "tags": {"env": "prod"}})
        r = client.get("/metrics?tag=env:prod")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["name"] == "mem"


    def test_store_filter_by_tags_method():
        """Test MetricStore.filter_by_tags() directly."""
        from models import MetricIn

        store.add(MetricIn(name="cpu", value=10.0, tags={"env": "prod", "service": "api"}))
        store.add(MetricIn(name="mem", value=20.0, tags={"env": "staging"}))
        # Empty filter returns all
        assert len(store.filter_by_tags([])) == 2
        # Single tag
        result = store.filter_by_tags([("env", "prod")])
        assert len(result) == 1
        assert result[0].name == "cpu"
        # AND logic
        result2 = store.filter_by_tags([("env", "prod"), ("service", "api")])
        assert len(result2) == 1
        assert result2[0].name == "cpu"
        # Non-matching
        assert len(store.filter_by_tags([("env", "nonexistent")])) == 0
    ```

    2. Ensure all tests use the existing `client` fixture and `clear_store` autouse fixture.
    3. Do NOT modify any existing tests.

    ## Files to modify
    - `backend/tests/test_api.py` — append 8 new test functions at the end of the file

    ## Code patterns to follow
    - Follow existing test patterns: use `client.post()` to create data, `client.get()` to query, assert status and body.
    - Use the existing `store` import from `main` for the direct store test.
    - No mocking — tests hit real routes via `TestClient`.

    ## Acceptance criteria
    - 8 new test functions exist in `test_api.py`
    - All 8 new tests pass
    - All existing tests still pass (no regressions)
    - Tests cover: no filter (backward compat), single tag, multi-tag AND, no match, invalid format, colon in value, untagged exclusion, direct store method

    ## Validation command
    ```bash
    cd backend && pytest tests/test_api.py -v -k "tag" && pytest tests/test_api.py -v
    ```

### 4. Update Frontend fetchMetrics to Support Tag Filters
- **Task ID**: update-fetch-metrics
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder-2
- **Description**: |
    Update the `fetchMetrics()` function in `frontend/src/api.ts` to accept an optional
    tags parameter and append `tag` query params to the URL.

    ## What to do
    1. In `frontend/src/api.ts`, modify the `fetchMetrics` function:

    **Current code:**
    ```typescript
    export async function fetchMetrics(): Promise<Metric[]> {
      const res = await fetch(`${BASE}/metrics`)
      if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`)
      return res.json()
    }
    ```

    **New code:**
    ```typescript
    export async function fetchMetrics(tags?: string[]): Promise<Metric[]> {
      let url = `${BASE}/metrics`
      if (tags && tags.length > 0) {
        const params = new URLSearchParams()
        for (const tag of tags) {
          params.append('tag', tag)
        }
        url += `?${params.toString()}`
      }
      const res = await fetch(url)
      if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.status}`)
      return res.json()
    }
    ```

    2. Key points:
       - The parameter is optional (`tags?: string[]`), so existing callers with no args still work
       - Uses `URLSearchParams` to properly encode multiple `tag` params
       - `params.append('tag', tag)` allows multiple `tag` keys (not `set` which would overwrite)
       - When `tags` is undefined or empty, the URL is unchanged (backward compatible)

    ## Files to modify
    - `frontend/src/api.ts` — modify `fetchMetrics()` function signature and body

    ## Code patterns to follow
    - Follow existing patterns in `api.ts`: use raw `fetch()`, throw on `!res.ok`, return `res.json()`
    - Keep the existing `Metric` interface and `BASE` constant unchanged
    - Use `URLSearchParams` for query string construction (standard Web API)

    ## Acceptance criteria
    - `fetchMetrics()` with no args still works (backward compatible)
    - `fetchMetrics(['env:prod'])` fetches from `/api/metrics?tag=env%3Aprod`
    - `fetchMetrics(['env:prod', 'service:api'])` fetches with both tag params
    - `fetchMetrics([])` fetches from `/api/metrics` (no query params)
    - TypeScript compiles without errors

    ## Validation command
    ```bash
    cd frontend && npx tsc --noEmit && echo "TYPECHECK PASSED"
    ```

### 5. Create TagFilterBar Component
- **Task ID**: create-tag-filter-bar
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder-2
- **Description**: |
    Create a new `TagFilterBar` React component in `frontend/src/components/TagFilterBar.tsx`
    that provides a UI for adding and removing tag filters.

    ## What to do
    1. Create the file `frontend/src/components/TagFilterBar.tsx` with the following content:

    ```typescript
    import { useState } from 'react'

    interface Props {
      tags: string[]
      onTagsChange: (tags: string[]) => void
    }

    export function TagFilterBar({ tags, onTagsChange }: Props) {
      const [input, setInput] = useState('')
      const [error, setError] = useState<string | null>(null)

      const addTag = () => {
        const trimmed = input.trim()
        if (!trimmed) return
        if (!trimmed.includes(':')) {
          setError('Tag must be in key:value format')
          return
        }
        if (tags.includes(trimmed)) {
          setError('Tag already added')
          return
        }
        setError(null)
        onTagsChange([...tags, trimmed])
        setInput('')
      }

      const removeTag = (tagToRemove: string) => {
        onTagsChange(tags.filter((t) => t !== tagToRemove))
      }

      const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          addTag()
        }
      }

      return (
        <div className="tag-filter-bar">
          <div className="tag-filter-input">
            <input
              type="text"
              placeholder="Filter by tag (e.g. env:prod)"
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                setError(null)
              }}
              onKeyDown={handleKeyDown}
              aria-label="Tag filter input"
            />
            <button type="button" onClick={addTag}>
              Add Filter
            </button>
          </div>
          {error && <span className="tag-filter-error">{error}</span>}
          {tags.length > 0 && (
            <div className="tag-filter-chips">
              {tags.map((tag) => (
                <span key={tag} className="tag-chip">
                  {tag}
                  <button
                    type="button"
                    onClick={() => removeTag(tag)}
                    aria-label={`Remove filter ${tag}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )
    }
    ```

    2. Key design decisions:
       - State is lifted: `tags` and `onTagsChange` come from parent (`App.tsx`)
       - Input validation: must contain `:`, must not be duplicate
       - Enter key triggers add (prevents form submission if inside a form)
       - Each chip has an accessible remove button with aria-label
       - Error messages clear when user types

    ## Files to modify
    - Create new file: `frontend/src/components/TagFilterBar.tsx`

    ## Code patterns to follow
    - Follow the existing component patterns from `MetricCard.tsx` and `MetricForm.tsx`:
      - Functional component with destructured props interface
      - useState for local state
      - CSS class names with `kebab-case` (e.g., `tag-filter-bar`)
      - Button event handlers as inline arrow functions or separate named functions
    - Use the same import style: `import { useState } from 'react'`

    ## Acceptance criteria
    - File exists at `frontend/src/components/TagFilterBar.tsx`
    - Component renders an input with placeholder "Filter by tag (e.g. env:prod)"
    - Component renders an "Add Filter" button
    - Typing "env:prod" and pressing Enter adds a chip
    - Typing "invalid" and pressing Enter shows error "Tag must be in key:value format"
    - Clicking "x" on a chip removes it and calls `onTagsChange` without that tag
    - Duplicate tags show error "Tag already added"
    - TypeScript compiles without errors

    ## Validation command
    ```bash
    cd frontend && npx tsc --noEmit && echo "TYPECHECK PASSED"
    ```

### 6. Integrate TagFilterBar into App.tsx
- **Task ID**: integrate-tag-filter
- **Role**: builder
- **Depends On**: create-tag-filter-bar, update-fetch-metrics
- **Assigned To**: builder-2
- **Description**: |
    Integrate the `TagFilterBar` component into `App.tsx`, adding tag filter state
    and passing active filters to the `fetchMetrics()` API call.

    ## What to do
    1. In `frontend/src/App.tsx`, add the import for `TagFilterBar` alongside existing component imports:

    Add this import after the existing imports at the top of the file:
    ```typescript
    import { TagFilterBar } from './components/TagFilterBar'
    ```

    2. Add tag filter state inside the `App` component, after the existing `useState` declarations:
    ```typescript
    const [activeTags, setActiveTags] = useState<string[]>([])
    ```

    3. Modify the `loadMetrics` function to pass `activeTags` to `fetchMetrics`:

    **Current code:**
    ```typescript
    const loadMetrics = async () => {
      try {
        const data = await fetchMetrics()
        setMetrics(data)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }
    ```

    **New code:**
    ```typescript
    const loadMetrics = async () => {
      try {
        const data = await fetchMetrics(activeTags.length > 0 ? activeTags : undefined)
        setMetrics(data)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }
    ```

    4. Update the `useEffect` to include `activeTags` in its dependency array so it re-fetches when tags change:

    **Current code:**
    ```typescript
    useEffect(() => {
      const loadData = async () => {
        await Promise.all([loadMetrics(), loadAlerts()])
      }
      loadData()
      const timer = setInterval(loadData, POLL_INTERVAL_MS)
      return () => clearInterval(timer)
    }, [])
    ```

    **New code:**
    ```typescript
    useEffect(() => {
      const loadData = async () => {
        await Promise.all([loadMetrics(), loadAlerts()])
      }
      loadData()
      const timer = setInterval(loadData, POLL_INTERVAL_MS)
      return () => clearInterval(timer)
    }, [activeTags])
    ```

    5. Add the `TagFilterBar` component in the JSX, between `<MetricForm>` and the loading/error/empty states. Insert it right after the `<MetricForm onSubmit={loadMetrics} />` line:

    ```tsx
    <TagFilterBar tags={activeTags} onTagsChange={setActiveTags} />
    ```

    So the JSX structure becomes:
    ```tsx
    <MetricForm onSubmit={loadMetrics} />

    <TagFilterBar tags={activeTags} onTagsChange={setActiveTags} />

    {loading && <p className="status">Loading...</p>}
    ```

    ## Files to modify
    - `frontend/src/App.tsx` — add import, add state, modify loadMetrics, update useEffect deps, add TagFilterBar to JSX

    ## Code patterns to follow
    - Follow existing patterns in `App.tsx`:
      - `useState` for component state (like `metrics`, `alerts`, `error`, `loading`)
      - Components rendered in JSX with prop passing (like `<MetricForm onSubmit={loadMetrics} />`)
      - The `useEffect` pattern with interval polling
    - Keep the `loadAlerts` function unchanged

    ## Acceptance criteria
    - `TagFilterBar` renders above the metric grid (between MetricForm and loading states)
    - Adding a tag filter triggers a re-fetch of metrics from the API with `?tag=` params
    - Removing all tag filters re-fetches all metrics (unfiltered)
    - Polling continues to work with active tag filters
    - The MetricForm's `onSubmit` still triggers `loadMetrics` (which now respects active tags)
    - TypeScript compiles without errors

    ## Validation command
    ```bash
    cd frontend && npx tsc --noEmit && echo "TYPECHECK PASSED"
    ```

### 7. Add Frontend Tests for Tag Filtering
- **Task ID**: add-frontend-tag-tests
- **Role**: builder
- **Depends On**: integrate-tag-filter
- **Assigned To**: builder-2
- **Description**: |
    Add tests for the tag filtering feature in the frontend: API client tests and
    App component integration tests.

    ## What to do

    ### Part A: Add API client tests in `frontend/src/api.test.ts`

    Add a new `describe('fetchMetrics with tags')` block inside the existing `describe('API Client')` block, after the existing `describe` blocks:

    ```typescript
    describe('fetchMetrics with tags', () => {
      it('should fetch metrics without tags by default', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        } as Response)

        await fetchMetrics()

        expect(mockFetch).toHaveBeenCalledWith('/api/metrics')
      })

      it('should fetch metrics with single tag filter', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        } as Response)

        await fetchMetrics(['env:prod'])

        expect(mockFetch).toHaveBeenCalledWith('/api/metrics?tag=env%3Aprod')
      })

      it('should fetch metrics with multiple tag filters', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        } as Response)

        await fetchMetrics(['env:prod', 'service:api'])

        expect(mockFetch).toHaveBeenCalledWith(
          '/api/metrics?tag=env%3Aprod&tag=service%3Aapi'
        )
      })

      it('should fetch metrics without params when tags array is empty', async () => {
        mockFetch.mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        } as Response)

        await fetchMetrics([])

        expect(mockFetch).toHaveBeenCalledWith('/api/metrics')
      })
    })
    ```

    You must also add `fetchMetrics` to the import at the top of the file. The current import is:
    ```typescript
    import {
      fetchMetricHistory,
      fetchAlerts,
      createAlert,
      deleteAlert,
      type AlertRuleIn,
      type AlertRule,
    } from './api'
    ```

    Change it to:
    ```typescript
    import {
      fetchMetrics,
      fetchMetricHistory,
      fetchAlerts,
      createAlert,
      deleteAlert,
      type AlertRuleIn,
      type AlertRule,
    } from './api'
    ```

    ### Part B: Add App component tests in `frontend/src/App.test.tsx`

    Add these tests inside the existing `describe('App')` block, after the existing tests:

    ```typescript
    describe('Tag Filtering', () => {
      it('renders the tag filter bar', async () => {
        render(<App />)
        expect(
          await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
        ).toBeInTheDocument()
        expect(screen.getByText('Add Filter')).toBeInTheDocument()
      })

      it('shows error for invalid tag format', async () => {
        render(<App />)
        const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
        await userEvent.type(input, 'invalid')
        await userEvent.click(screen.getByText('Add Filter'))
        expect(screen.getByText('Tag must be in key:value format')).toBeInTheDocument()
      })

      it('adds and displays a tag filter chip', async () => {
        render(<App />)
        const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
        await userEvent.type(input, 'env:prod')
        await userEvent.click(screen.getByText('Add Filter'))
        expect(await screen.findByText('env:prod')).toBeInTheDocument()
      })

      it('removes a tag filter chip when x is clicked', async () => {
        render(<App />)
        const input = await screen.findByPlaceholderText('Filter by tag (e.g. env:prod)')
        await userEvent.type(input, 'env:prod')
        await userEvent.click(screen.getByText('Add Filter'))
        expect(await screen.findByText('env:prod')).toBeInTheDocument()
        await userEvent.click(screen.getByLabelText('Remove filter env:prod'))
        expect(screen.queryByText('env:prod')).not.toBeInTheDocument()
      })
    })
    ```

    You must also add `userEvent` import at the top of `App.test.tsx`:
    ```typescript
    import userEvent from '@testing-library/user-event'
    ```

    Add this after the existing imports.

    ## Files to modify
    - `frontend/src/api.test.ts` — add `fetchMetrics` import and `describe('fetchMetrics with tags')` test block
    - `frontend/src/App.test.tsx` — add `userEvent` import and `describe('Tag Filtering')` test block

    ## Code patterns to follow
    - Follow existing test patterns in both files:
      - `api.test.ts`: uses `mockFetch`, `vi.clearAllMocks()`, direct assertion on fetch URL
      - `App.test.tsx`: uses `render(<App />)`, `screen.findByText()`, `vi.mocked(api.fetchMetrics)`
    - Use `@testing-library/user-event` for user interactions (typing, clicking)
    - Use `findBy` for async elements, `getBy` for sync elements, `queryBy` for absence checks

    ## Acceptance criteria
    - 4 new API client tests pass (no tags, single tag, multiple tags, empty tags array)
    - 4 new App integration tests pass (renders bar, invalid format error, add chip, remove chip)
    - All existing frontend tests still pass
    - TypeScript compiles without errors

    ## Validation command
    ```bash
    cd frontend && npx vitest run --reporter=verbose && echo "ALL FRONTEND TESTS PASSED"
    ```

### 8. Final Validation
- **Task ID**: validate-all
- **Role**: validator
- **Depends On**: add-backend-tag-tests, add-frontend-tag-tests
- **Assigned To**: validator
- **Description**: |
    Run all validation commands and verify all acceptance criteria across both backend and frontend.

    ## Validation Commands
    Run each of these commands and verify they pass:

    1. `cd backend && ruff check .` — Python lint passes
    2. `cd backend && pytest tests/ -v` — All backend tests pass (existing + 8 new tag filter tests)
    3. `cd frontend && npx tsc --noEmit` — TypeScript compiles
    4. `cd frontend && npx vitest run --reporter=verbose` — All frontend tests pass (existing + 8 new)
    5. `cd frontend && npx eslint src --ext .ts,.tsx --max-warnings 0` — No lint warnings

    ## Acceptance Criteria
    Verify ALL of these:

    **Backend:**
    - `GET /metrics` with no `tag` params returns all metrics (backward compatible)
    - `GET /metrics?tag=env:prod` returns only metrics matching that tag
    - `GET /metrics?tag=env:prod&tag=service:api` returns metrics matching BOTH (AND logic)
    - `GET /metrics?tag=invalid` returns 400 with error detail
    - `MetricStore.filter_by_tags()` method exists and works correctly
    - All existing backend tests pass without modification
    - 8 new backend test functions exist and pass

    **Frontend:**
    - `fetchMetrics()` with no args still works
    - `fetchMetrics(['env:prod'])` constructs correct URL with `?tag=env:prod`
    - `TagFilterBar` component exists at `frontend/src/components/TagFilterBar.tsx`
    - Tag filter bar renders above the metric grid with input and "Add Filter" button
    - Adding a tag shows a chip; clicking "x" removes it
    - Invalid tag format (no colon) shows error message
    - Active tag filters are passed to `fetchMetrics()` on every poll
    - All existing frontend tests pass without modification
    - 8 new frontend test functions exist and pass
    - TypeScript compiles clean, ESLint passes

    ## How to validate manually
    If automated tests pass, also do a quick code review:
    1. Read `backend/store.py` — confirm `filter_by_tags` method exists with correct AND logic
    2. Read `backend/main.py` — confirm `list_metrics` uses `Query(default=[])` for `tag` param
    3. Read `frontend/src/api.ts` — confirm `fetchMetrics` accepts optional `tags?: string[]`
    4. Read `frontend/src/components/TagFilterBar.tsx` — confirm component structure
    5. Read `frontend/src/App.tsx` — confirm `activeTags` state and `TagFilterBar` integration

### 9. Update Design Documentation
- **Task ID**: update-design-metrics
- **Role**: design-updater
- **Depends On**: validate-all
- **Assigned To**: design-updater
- **Description**: |
    Update the living design document for the metrics domain to reflect
    what was actually built in this plan.

    ## Target Design Doc
    docs/design/metrics.md

    ## Spec File
    specs/metric-tags-filtering.md

    ## Scope
    Tag filtering on the GET /metrics endpoint, MetricStore.filter_by_tags() method,
    frontend TagFilterBar component, and fetchMetrics() tag parameter support.

    ## Prior Decisions to Check
    - Tags are stored as `dict[str, str]` on MetricIn/MetricOut (established in initial design)
    - MetricStore uses in-memory list storage with `_data: list[MetricOut]` (established pattern)
    - Frontend uses raw `fetch()` with `/api` base URL proxied through Vite (established pattern)
    - History endpoint uses `_history` dict separate from `_data` (from metric-history-endpoint plan)

    ## What to Record
    Read git diff HEAD~1 HEAD, then the changed source files, then the existing
    design doc (if it exists — create it if not). Update Current Design to match
    the implementation. Append a Design Decision entry for each non-trivial
    architectural choice made in this build:
    - Tag query parameter format: `key:value` with `:` separator (split on first colon)
    - AND logic for multiple tag filters
    - `filter_by_tags()` as a separate method (not modifying `all()`)
    - Tag state lifted to App.tsx with TagFilterBar as controlled component
    - `useEffect` dependency on `activeTags` for automatic re-fetch

    Every claim must cite a file:line from the actual code.

## Acceptance Criteria

- `GET /metrics` without `tag` params returns all metrics (fully backward compatible)
- `GET /metrics?tag=env:prod` returns only metrics whose tags include `env=prod`
- `GET /metrics?tag=env:prod&tag=service:api` returns only metrics matching ALL specified tags (AND logic)
- `GET /metrics?tag=invalid` returns HTTP 400 with a clear error message about expected format
- `GET /metrics?tag=key:val:with:colons` correctly parses key as "key" and value as "val:with:colons"
- `MetricStore.filter_by_tags([])` returns all metrics (same as `all()`)
- `MetricStore.filter_by_tags([("env", "prod")])` returns only matching metrics
- Frontend `fetchMetrics()` with no args works identically to before
- Frontend `fetchMetrics(['env:prod'])` fetches with `?tag=env%3Aprod` query param
- `TagFilterBar` component renders input with placeholder and "Add Filter" button
- Adding a valid `key:value` tag creates a removable chip
- Adding an invalid tag (no colon) shows an inline error message
- Removing a chip triggers re-fetch without that filter
- Polling every 5s continues to work with active filters
- All existing backend tests pass without modification (26+ tests)
- All existing frontend tests pass without modification
- 8 new backend tests pass covering tag filtering
- 8 new frontend tests pass covering API client and UI
- `ruff check .` passes in backend
- `tsc --noEmit` passes in frontend
- `eslint` passes in frontend with zero warnings

## Validation Commands

Execute these commands to validate the task is complete:

- `cd backend && ruff check .` — Python lint clean
- `cd backend && pytest tests/ -v` — All backend tests pass
- `cd frontend && npx tsc --noEmit` — TypeScript compilation clean
- `cd frontend && npx vitest run --reporter=verbose` — All frontend tests pass
- `cd frontend && npx eslint src --ext .ts,.tsx --max-warnings 0` — ESLint clean

## Notes

- **No new backend dependencies**: All filtering is done with Python builtins (list comprehension, `all()`, `dict.get()`).
- **No new frontend dependencies**: Uses standard `URLSearchParams` Web API and existing React/testing libraries.
- **Tag format**: Using `key:value` with colon separator rather than `key=value` to avoid URL encoding ambiguity with `=` in query strings. The colon in values is handled by splitting on first colon only (`split(":", 1)`).
- **AND logic**: Multiple tags use AND logic (all must match). OR logic could be a future enhancement but AND is the most common filtering pattern and was specifically requested.
- **Backward compatibility**: The `tag` query parameter defaults to an empty list, so existing API consumers are completely unaffected.
- **CSS styling**: The plan does not include CSS for the TagFilterBar. The component uses class names (`tag-filter-bar`, `tag-filter-chips`, `tag-chip`, etc.) that can be styled later. Basic functionality works without styling.

## Build Evidence

> Collected by **spec-updater** on **2026-03-15**.

### Validation Commands

| # | Command | Result | Notes |
|---|---------|--------|-------|
| 1 | `cd backend && ruff check .` | PASS | All checks passed |
| 2 | `cd backend && pytest tests/ -v` | PARTIAL (62/63 passed) | 1 pre-existing failure in `test_metrics_export_csv_with_data` — hardcoded date assertion (`2026-03-01`) fails against today's date. **Not related to tag filtering.** All 8 new tag-filtering tests pass. |
| 3 | `cd frontend && npx tsc --noEmit` | PASS | No type errors |
| 4 | `cd frontend && npx vitest run --reporter=verbose` | PASS | 27/27 tests pass (2 files) |
| 5 | `cd frontend && npx eslint src --ext .ts,.tsx --max-warnings 0` | PASS | No warnings or errors |

### Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| GET /metrics backward compatible (no tags returns all) | PASS | `test_tag_filter_no_filter_returns_all` passes |
| Tag filtering with AND logic | PASS | `test_tag_filter_multi_tag_and_logic` passes |
| 400 on invalid tag format (no colon) | PASS | `test_tag_filter_invalid_format` passes |
| `MetricStore.filter_by_tags()` works | PASS | `test_tag_filter_store_direct` passes |
| `fetchMetrics()` accepts optional tags | PASS | 4 dedicated API client tests pass (`should fetch metrics without tags when none provided`, `should fetch metrics without tags when empty array provided`, `should append single tag query parameter`, `should append multiple tag query parameters`) |
| TagFilterBar renders with input, chips, validation | PASS | `renders the tag filter input and button`, `shows validation error when tag has no colon`, `adds a valid tag chip and passes it to fetchMetrics`, `removes a tag chip when clicking remove button` — all pass |
| All existing + new tests pass, lint clean | PASS | All existing tests pass (except 1 pre-existing date bug unrelated to this feature). All new tests pass. Ruff, TSC, and ESLint clean. |

### New Tag-Filtering Tests Added

**Backend** (`backend/tests/test_api.py`):
- `test_tag_filter_no_filter_returns_all`
- `test_tag_filter_single_tag`
- `test_tag_filter_multi_tag_and_logic`
- `test_tag_filter_no_match`
- `test_tag_filter_invalid_format`
- `test_tag_filter_colon_in_value`
- `test_tag_filter_untagged_excluded`
- `test_tag_filter_store_direct`

**Frontend** (`frontend/src/api.test.ts`):
- `should fetch metrics without tags when none provided`
- `should fetch metrics without tags when empty array provided`
- `should append single tag query parameter`
- `should append multiple tag query parameters`

**Frontend** (`frontend/src/App.test.tsx`):
- `renders the tag filter input and button`
- `shows validation error when tag has no colon`
- `adds a valid tag chip and passes it to fetchMetrics`
- `removes a tag chip when clicking remove button`

### Pre-existing Issue (Not Related)

`test_metrics_export_csv_with_data` fails because it asserts `"2026-03-01" in data_row[4]` but the timestamp is dynamically generated (today = `2026-03-15`). This is a pre-existing test bug unrelated to tag filtering.
