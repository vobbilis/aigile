# Metrics Domain — Living Design Document

> **Last Updated:** 2026-03-15
> **Updated By:** design-updater (build: specs/metric-history-sparklines.md)
> **Code Baseline:** d3692ed + uncommitted sparkline build

## Current Design

The metrics dashboard is a full-stack application with a Python/FastAPI backend and a React/TypeScript frontend. The backend stores metrics in memory and exposes a REST API. The frontend polls the API and renders metrics in a card grid with support for submission, deletion, tag filtering, alerting, CSV export, and per-metric sparkline trend charts.

### Key Files

| File | Purpose |
|------|---------|
| `backend/models.py` | Pydantic models: `MetricIn`, `MetricOut`, `MetricSummary`, alert models |
| `backend/store.py` | `MetricStore` — in-memory storage with query, filter, history, and delete |
| `backend/main.py` | FastAPI app with all REST endpoints and CORS middleware |
| `backend/alert_store.py` | `AlertStore` — alert rule storage and evaluation loop |
| `frontend/src/api.ts` | API client: `fetchMetrics()`, `submitMetric()`, `deleteMetric()`, `fetchMetricHistory()`, alert functions |
| `frontend/src/App.tsx` | Root component: state management, polling, layout composition |
| `frontend/src/components/TagFilterBar.tsx` | Tag filter UI: input, validation, chips, lifted state |
| `frontend/src/components/MetricCard.tsx` | Metric display card with sparkline history visualization |
| `frontend/src/components/SparklineChart.tsx` | Compact line chart using Recharts — renders trend line with no axes, tooltip, or legend |
| `frontend/src/components/MetricForm.tsx` | Metric submission form |

### Data Model

Metrics carry a `tags` field of type `dict[str, str]` (backend, `models.py:14`) / `Record<string, string>` (frontend, `api.ts:25`). Tags are optional on submission (`default_factory=dict`, `models.py:14`) and always present on output (`models.py:21`).

### Storage Layer

`MetricStore` (`store.py:8-61`) uses an in-memory `list[MetricOut]` (`store.py:10`). Query methods:

- `all()` (`store.py:27-28`) — returns a copy of all metrics
- `filter_by_tags(tags)` (`store.py:30-36`) — filters by tag key/value pairs using AND logic; empty tags list returns all metrics
- `by_name(name)` (`store.py:38-39`) — filters by metric name
- `history(name, limit)` (`store.py:41-46`) — returns last N entries from a per-name `deque(maxlen=20)`
- `delete(name)` (`store.py:48-52`) — removes metrics and history by name

### API Layer

The `GET /metrics` endpoint (`main.py:56-67`) accepts optional `tag` query parameters via `Query(default=[])` (`main.py:57`). Each tag must be in `key:value` format. The endpoint:

1. Iterates over `tag` params, validates each contains `:` (`main.py:60`)
2. Returns HTTP 400 with descriptive error if format is invalid (`main.py:61-64`)
3. Splits on first colon via `t.split(":", 1)` to allow colons in values (`main.py:65`)
4. Delegates to `store.filter_by_tags(parsed_tags)` (`main.py:67`)

When no `tag` params are provided, the empty list flows through to `filter_by_tags([])` which returns all metrics — preserving backward compatibility.

### Frontend API Client

`fetchMetrics(tags?: string[])` (`api.ts:35-47`) constructs the request URL. When tags are provided:

1. Creates a `URLSearchParams` instance (`api.ts:38`)
2. Appends each tag as a `tag` parameter (`api.ts:39-41`)
3. Appends the query string to the base URL (`api.ts:42`)

When called without arguments or with an empty array, the URL has no query string — backward compatible.

`fetchMetricHistory(name: string, limit: number = 20)` (`api.ts:71-78`) fetches the last N data points for a specific metric from `GET /api/metrics/{name}/history?limit={limit}`. Returns `Promise<Metric[]>`. Used by `MetricCard` to populate sparkline charts (`MetricCard.tsx:18`).

### Frontend State & UI

Tag filter state is lifted to `App.tsx`:

- `activeTags` state (`App.tsx:15`) holds the current `string[]` of active tag filters
- `loadMetrics()` passes `activeTags` to `fetchMetrics(activeTags)` (`App.tsx:19`)
- `useEffect` depends on `[activeTags]` (`App.tsx:46`) — changing tags triggers immediate re-fetch and resets the polling interval
- `TagFilterBar` is rendered between `MetricForm` and the loading/error status (`App.tsx:62`)

`TagFilterBar` (`TagFilterBar.tsx:8-67`) is a controlled component:

- Props: `tags: string[]` and `onTagsChange: (tags: string[]) => void` (`TagFilterBar.tsx:4-5`)
- Local state for input text and validation error (`TagFilterBar.tsx:9-10`)
- Validates input contains `:` before adding (`TagFilterBar.tsx:14`)
- Prevents duplicate tags (`TagFilterBar.tsx:18`)
- Renders active filters as removable chip elements (`TagFilterBar.tsx:53-63`)
- Supports Enter key submission (`TagFilterBar.tsx:31-36`)

### Per-Card History Fetching & Sparklines

Each `MetricCard` independently fetches its own history data on mount using a `useEffect` with `[metric.name]` dependency (`MetricCard.tsx:14-36`). The pattern:

- Local state: `historyData` (`MetricCard.tsx:11`) and `historyLoading` (`MetricCard.tsx:12`)
- `useEffect` calls `fetchMetricHistory(metric.name)` (`MetricCard.tsx:18`) and maps the result to `{ value: number }[]` for the chart (`MetricCard.tsx:20`)
- Cleanup uses a `cancelled` flag (`MetricCard.tsx:15, 33-35`) to prevent state updates after unmount
- Error handling: catch block silently sets empty data (`MetricCard.tsx:22-25`) — the card continues to show the current value
- The sparkline renders only when loading is complete and data is non-empty (`MetricCard.tsx:52-56`)

`SparklineChart` (`SparklineChart.tsx:9-30`) is a pure presentational component:

- Uses Recharts `LineChart`, `Line`, and `ResponsiveContainer` (`SparklineChart.tsx:1`)
- No axes, tooltip, legend, or cartesian grid — only the trend line (`SparklineChart.tsx:18-28`)
- Returns `null` for empty data (`SparklineChart.tsx:10-12`)
- Duplicates single data points to render a flat line (`SparklineChart.tsx:14`)
- Animation disabled (`isAnimationActive={false}`, `SparklineChart.tsx:25`) for testability
- Default height 60px (`SparklineChart.tsx:9`), responsive width via `ResponsiveContainer` (`SparklineChart.tsx:17`)

### Polling

The app polls both metrics and alerts every 5 seconds (`App.tsx:7`). The `useEffect` cleanup clears the interval on unmount or when `activeTags` changes (`App.tsx:45`), preventing stale closures.

---

## Design Decisions

### DD-001: Tag query parameter format — `key:value` with colon separator

**Date:** 2026-03-15

**Context:** The `GET /metrics` endpoint needed a way to accept tag filters as query parameters. Tags are stored as `dict[str, str]` key-value pairs.

**Options considered:**
1. `?tag=env:prod` — colon-separated key:value in a single param
2. `?tag_key=env&tag_value=prod` — separate params for key and value
3. `?tags={"env":"prod"}` — JSON-encoded object

**Decision:** Option 1 — `key:value` format with colon separator.

**Rationale:** Simple, human-readable, composable with repeated params (`?tag=a:b&tag=c:d`). Split on first colon (`main.py:65`) allows colons in values (e.g., URLs).

**Tradeoffs:** Keys cannot contain colons. This is acceptable for typical tag keys (env, service, region, etc.).

**Code evidence:** `backend/main.py:57-67`, `backend/tests/test_api.py:759-766` (colon-in-value test)

---

### DD-002: AND logic for multiple tag filters

**Date:** 2026-03-15

**Context:** When multiple tag filters are specified, the system needs a combining strategy.

**Options considered:**
1. AND — metrics must match ALL specified tags
2. OR — metrics must match ANY specified tag

**Decision:** AND logic — all specified tags must match.

**Rationale:** AND is the more common filtering semantic (narrowing results). Users can always remove filters to broaden results. OR logic would be harder to use for precise filtering.

**Tradeoffs:** Cannot express "env:prod OR env:staging" in a single query. This could be added later with an explicit OR operator if needed.

**Code evidence:** `backend/store.py:35` (`all(m.tags.get(k) == v for k, v in tags)`), `backend/tests/test_api.py:732-741` (multi-tag AND test)

---

### DD-003: `filter_by_tags()` as a separate method from `all()`

**Date:** 2026-03-15

**Context:** Tag filtering could be implemented by modifying the existing `all()` method or as a new method.

**Options considered:**
1. Add optional `tags` parameter to `all()`
2. Create a new `filter_by_tags()` method

**Decision:** Option 2 — new `filter_by_tags()` method.

**Rationale:** Keeps `all()` simple and backward compatible. The filtering method has distinct semantics (AND logic, tuple-based input) that deserve their own method signature. Other callers of `all()` (export, summary) are not affected.

**Tradeoffs:** Two methods that can return "all metrics" (`all()` and `filter_by_tags([])`). Acceptable because `filter_by_tags([])` explicitly documents intent.

**Code evidence:** `backend/store.py:27-28` (`all()`), `backend/store.py:30-36` (`filter_by_tags()`), `backend/main.py:67` (endpoint uses `filter_by_tags`)

---

### DD-004: Tag state lifted to App.tsx with TagFilterBar as controlled component

**Date:** 2026-03-15

**Context:** The tag filter state needs to be accessible to both the filter UI and the data-fetching logic.

**Options considered:**
1. Tag state owned by `TagFilterBar`, communicated via callback
2. Tag state lifted to `App.tsx`, `TagFilterBar` as controlled component

**Decision:** Option 2 — lifted state.

**Rationale:** `App.tsx` owns the fetch logic and needs direct access to `activeTags` for `fetchMetrics(activeTags)` (`App.tsx:19`). Lifting state avoids prop-drilling callbacks and keeps the data flow unidirectional.

**Tradeoffs:** `App.tsx` gains another piece of state. Acceptable given the component's existing role as state coordinator.

**Code evidence:** `frontend/src/App.tsx:15` (`activeTags` state), `frontend/src/App.tsx:62` (controlled prop passing), `frontend/src/components/TagFilterBar.tsx:4-5` (Props interface)

---

### DD-005: `useEffect` dependency on `activeTags` for automatic re-fetch

**Date:** 2026-03-15

**Context:** When the user adds or removes a tag filter, metrics should update immediately rather than waiting for the next poll cycle.

**Options considered:**
1. Manual re-fetch via callback when tags change
2. Include `activeTags` in `useEffect` dependency array

**Decision:** Option 2 — `useEffect` dependency.

**Rationale:** Adding `activeTags` to the dependency array (`App.tsx:46`) triggers an immediate re-fetch and resets the polling interval. This is the idiomatic React pattern for derived data fetching and avoids stale closure bugs.

**Tradeoffs:** Changing tags also re-fetches alerts (bundled in `loadData`). Minor inefficiency, but keeps the polling logic simple.

**Code evidence:** `frontend/src/App.tsx:39-46` (useEffect with activeTags dependency)

---

### DD-006: Recharts for sparkline visualization — minimal line chart with no chrome

**Date:** 2026-03-15

**Context:** MetricCard needed a compact trend visualization. A charting library was required to render SVG line charts from `{ value: number }[]` data.

**Options considered:**
1. Recharts — React-native composable charting library built on D3; provides `LineChart`, `Line`, `ResponsiveContainer` components
2. Chart.js / react-chartjs-2 — canvas-based charting, heavier bundle, less React-idiomatic
3. Custom SVG — manual `<polyline>` rendering from data points

**Decision:** Option 1 — Recharts (`recharts` ^3.8.0, `frontend/package.json:17`).

**Rationale:** Recharts is purpose-built for React with composable components. A sparkline requires only `LineChart`, `Line`, and `ResponsiveContainer` — three imports (`SparklineChart.tsx:1`). No axes (`XAxis`, `YAxis`), no tooltip, no legend, no grid are rendered. The `dot={false}` prop removes data point markers (`SparklineChart.tsx:24`). Animation is disabled with `isAnimationActive={false}` (`SparklineChart.tsx:25`) to ensure deterministic rendering and testable output.

**Tradeoffs accepted:** Recharts adds ~200KB to the production bundle. Acceptable for a dashboard application that already bundles React and React-DOM. A custom SVG polyline would be lighter but harder to maintain and extend.

**Code evidence:** `frontend/src/components/SparklineChart.tsx:1` (imports), `frontend/src/components/SparklineChart.tsx:17-28` (minimal LineChart with no chrome), `frontend/package.json:17` (recharts dependency)

**Build:** `specs/metric-history-sparklines.md`

---

### DD-007: Per-card history fetching in MetricCard vs. lifting to App.tsx

**Date:** 2026-03-15

**Context:** Each MetricCard needs historical data to render its sparkline. The data could be fetched at the card level or lifted to the parent `App.tsx`.

**Options considered:**
1. Fetch history in each `MetricCard` via `useEffect` — each card manages its own loading/error state
2. Fetch all history in `App.tsx` and pass as props — centralized data management, single loading state

**Decision:** Option 1 — per-card fetching in `MetricCard` (`MetricCard.tsx:14-36`).

**Rationale:** History is card-specific data tied to `metric.name`. Lifting to `App.tsx` would require N parallel API calls coordinated at the parent level, adding complexity to an already state-heavy component. Per-card fetching keeps the data collocated with its consumer and allows independent loading/error handling. The `useEffect` cleanup with a `cancelled` flag (`MetricCard.tsx:15, 33-35`) prevents state updates on unmounted components. Error handling is silent — the card still shows its current value without a sparkline (`MetricCard.tsx:22-25`).

**Tradeoffs accepted:** Each card makes an independent API call on mount, which could mean many concurrent requests if many cards are visible. Acceptable because the history endpoint (`GET /metrics/{name}/history`) is lightweight (returns max 20 entries from an in-memory deque). If card count grows significantly, a batched fetch could be introduced later.

**Code evidence:** `frontend/src/components/MetricCard.tsx:14-36` (useEffect with per-card fetch), `frontend/src/components/MetricCard.tsx:11-12` (local state), `frontend/src/components/MetricCard.tsx:52-56` (conditional sparkline rendering)

**Build:** `specs/metric-history-sparklines.md`
