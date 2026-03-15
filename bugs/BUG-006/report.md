# Bug Report: BUG-006

| Field    | Value                          |
| -------- | ------------------------------ |
| ID       | BUG-006                        |
| Type     | Bug                            |
| Severity | High                           |
| Priority | High                           |
| Status   | Open                           |
| Reporter | bug-creator                    |
| Assignee | Unassigned                     |
| Module   | backend                        |
| Labels   | store, memory-growth, ui-degradation, performance |
| Created  | 2026-03-16T00:30:00Z           |

## Summary

The dashboard accumulates unbounded duplicate metric cards for every metric name. `MetricStore._data` is an unbounded list — every `POST /metrics` call appends a new entry permanently with no eviction policy. Because `GET /metrics` calls `store.filter_by_tags()` which iterates all of `_data`, it returns every historical submission for each metric name rather than the latest value per name. The frontend renders one `<MetricCard>` per returned entry (keyed by `m.id`), so submitting `cpu` 100 times produces 100 separate `cpu` cards. Separately, alert evaluation calls `store.by_name()` which is an O(n) linear scan over all `_data` entries, growing slower with every submission. The `_history` deque is correctly capped at 20 entries per name, but `_data` has no retention policy at all.

## Steps to Reproduce

1. Start the backend: `cd backend && uvicorn main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Submit the same metric multiple times:
   ```
   POST /metrics  {"name": "cpu", "value": 10.0}
   POST /metrics  {"name": "cpu", "value": 20.0}
   POST /metrics  {"name": "cpu", "value": 30.0}
   ```
4. Open the dashboard at `http://localhost:5173`
5. Observe that **3 separate `cpu` metric cards** are displayed instead of 1
6. Repeat step 3 — each additional submission adds another card
7. After 100 submissions of `cpu`, the metric grid shows 100 `cpu` cards

To also observe the alert performance degradation:
1. Create an alert rule: `POST /alerts {"metric_name": "cpu", "operator": "gt", "threshold": 80.0}`
2. Submit `cpu` 10,000 times via a loop
3. Observe that background alert evaluation (every 10s) becomes progressively slower as `_data` grows

## Expected Behavior

- `GET /metrics` returns exactly **one entry per unique metric name** — the most recently submitted value for each name
- Submitting `cpu` 100 times results in **one** `cpu` card on the dashboard (showing the latest value)
- Historical values remain accessible via `GET /metrics/{name}/history` (which already uses the capped `_history` deque)
- Alert evaluation runs in O(1) or O(unique names) time regardless of submission history, not O(total submissions)
- Memory usage of `MetricStore._data` is bounded

## Actual Behavior

- `GET /metrics` returns **all** historical entries for every metric — N submissions of the same metric name yields N entries in the response
- The frontend renders `metrics.map((m) => <MetricCard key={m.id} ...>)` — since each entry has a unique `m.id`, N submissions of `cpu` renders N separate `cpu` metric cards
- `MetricStore._data` grows without bound — no eviction, no deduplication, no cap
- `store.by_name(name)` (used by alert evaluation) performs a full linear scan over all `_data` entries every 10 seconds; with 10,000 total submissions the scan takes ~0.4ms, scaling linearly with `_data` size
- `_history` is correctly capped at 20 entries per name, but `_data` is never trimmed

**Reproduction output** (verified locally):

```
_data length after 5 cpu submissions: 5
GET /metrics returns 5 entries (should return 1 deduplicated card)
  values: [0.0, 10.0, 20.0, 30.0, 40.0]
  names: ['cpu', 'cpu', 'cpu', 'cpu', 'cpu']
by_name("cpu") scans all 5 _data entries - O(n) as _data grows
After 25 mem submissions:
  _data total length: 30 (unbounded, no eviction)
  _history[mem] length: 20 (correctly capped at 20)
  _data unique names: 2
```

**Alert evaluation O(n) scan evidence**:

```
_data size after 1000 cpu submissions: 1000
by_name("cpu") over 1000 entries: 0.039ms, returned 1000 entries
by_name("cpu") over 10000 entries: 0.403ms, returned 10000 entries
=> Alert evaluation is O(n) over all _data entries, slows as store grows
```

**Frontend duplicate cards evidence**:

```
GET /metrics response (used by frontend to render metric cards):
  id=528a6e2f... name=cpu value=50.0
  id=47f512e7... name=cpu value=51.0
  id=cbd5539b... name=cpu value=52.0
=> Frontend renders 3 MetricCard for name="cpu" (BUG: should be 1)

App.tsx renders: metrics.map((m) => <MetricCard key={m.id} ...>)
=> 3 unique id keys => 3 cards, all with name="cpu"
```

## Environment

- Python: 3.11.8
- FastAPI: 0.115.6
- Pydantic: v2
- Node: v18+
- React: 18.3.1
- Vite: 6.0.3
- OS: Darwin 25.3.0 (macOS)
- Branch: `fix/bug-006`

## Severity

**High** — The bug causes compounding UI degradation (the grid becomes unusable after repeated metric submissions) and unbounded memory growth. In a long-running production deployment, `MetricStore._data` grows monotonically — there is no mechanism to bound or evict old entries. Additionally, alert evaluation runs every 10 seconds in a background loop and scans the entire `_data` list for each rule; as submissions accumulate this creates a persistent CPU drain. Users cannot rely on the dashboard to show a meaningful "current state" view since the same metric name appears N times.

## Module/Area

Primary: **backend**

- `backend/store.py` line 10 — `_data: list[MetricOut] = []` is unbounded; no retention policy
- `backend/store.py` lines 21–21 — `self._data.append(out)` — unconditional append with no deduplication
- `backend/store.py` lines 27–28 — `all()` returns the full unbounded list
- `backend/store.py` lines 30–36 — `filter_by_tags()` iterates all of `_data`, returning duplicates
- `backend/store.py` lines 38–39 — `by_name()` is an O(n) linear scan over `_data`
- `backend/main.py` lines 56–67 — `list_metrics()` calls `store.filter_by_tags()` which returns all historical entries

Secondary: **frontend**

- `frontend/src/App.tsx` line 93–95 — `metrics.map((m) => <MetricCard key={m.id} ...>)` — uses unique `m.id` per entry so N submissions renders N cards; should use `m.name` as key or deduplicate before render

## Evidence

### Root Cause 1: `_data` is an unbounded list with unconditional append

**File**: `backend/store.py` lines 10, 21–24

```python
class MetricStore:
    def __init__(self) -> None:
        self._data: list[MetricOut] = []          # line 10: no size limit, no eviction
        self._history: dict[str, deque[MetricOut]] = {}   # line 11: has maxlen=20 cap

    def add(self, metric: MetricIn) -> MetricOut:
        out = MetricOut(...)
        self._data.append(out)                    # line 21: always appends, never deduplicates
        if metric.name not in self._history:
            self._history[metric.name] = deque(maxlen=20)   # maxlen=20 correctly caps history
        self._history[metric.name].append(out)
```

`_history` is correctly capped at 20 entries per name via `deque(maxlen=20)`. `_data` has no equivalent cap.

### Root Cause 2: `filter_by_tags()` and `all()` return all historical entries

**File**: `backend/store.py` lines 27–36

```python
def all(self) -> list[MetricOut]:
    return list(self._data)                       # returns ALL entries, no deduplication

def filter_by_tags(self, tags: list[tuple[str, str]]) -> list[MetricOut]:
    if not tags:
        return list(self._data)                   # returns ALL entries when no filter
    return [
        m for m in self._data                     # scans ALL entries, returns all matching
        if all(m.tags.get(k) == v for k, v in tags)
    ]
```

Neither method deduplicates by metric name. Submitting `cpu` N times means both methods return N `cpu` entries.

### Root Cause 3: `list_metrics` passes all duplicates to the frontend

**File**: `backend/main.py` lines 56–67

```python
@app.get("/metrics", response_model=list[MetricOut])
def list_metrics(tag: list[str] = Query(default=[])) -> list[MetricOut]:
    parsed_tags: list[tuple[str, str]] = []
    for t in tag:
        ...
        parsed_tags.append((key, value))
    return store.filter_by_tags(parsed_tags)      # returns all historical entries, not latest per name
```

There is no deduplication step before returning the response. The frontend receives all N entries for each metric name.

### Root Cause 4: Frontend renders one card per entry, not per name

**File**: `frontend/src/App.tsx` lines 92–95

```tsx
<div className="metric-grid">
  {metrics.map((m) => (
    <MetricCard key={m.id} metric={m} onDelete={...} />
    {/* key=m.id: each historical entry has a unique UUID, so React renders N cards */}
  ))}
</div>
```

`key={m.id}` uses the per-entry UUID. Since `GET /metrics` returns N entries for the same name, React renders N distinct `MetricCard` components, one for each UUID.

### Root Cause 5: Alert evaluation is O(n) over all `_data` entries

**File**: `backend/store.py` lines 38–39 and `backend/alert_store.py` lines 42–44

```python
# store.py
def by_name(self, name: str) -> list[MetricOut]:
    return [m for m in self._data if m.name == name]   # O(n) scan over ALL data

# alert_store.py - called every 10s from background loop
def evaluate(self, metric_store: MetricStore) -> list[tuple[str, str, str]]:
    for rule in self._rules:
        metrics = metric_store.by_name(rule.metric_name)  # O(n) call per rule
```

The alert loop calls `store.by_name()` for each rule every 10 seconds. As `_data` grows without bound, each call scans an ever-growing list.

### Measured performance degradation

```
_data size after    1,000 cpu submissions → by_name scan:  0.039ms
_data size after   10,000 cpu submissions → by_name scan:  0.403ms
(10x data → ~10x scan time: confirmed O(n) growth)
```

### `_history` deque is correctly bounded (for comparison)

```python
# store.py line 22-23
if metric.name not in self._history:
    self._history[metric.name] = deque(maxlen=20)   # automatically evicts oldest entry
```

After 25 `mem` submissions: `_history["mem"]` has 20 entries (capped), while `_data` has 25 `mem` entries (unbounded).

## Root Cause Analysis

The core design gap is that `MetricStore` was built with two storage structures that serve different purposes — `_data` as a "current state" view and `_history` as a bounded time-series — but `_data` was never given a retention policy. The `_history` deque correctly evicts old entries on overflow. `_data` has no equivalent mechanism: it was designed as if it would only hold the latest value per name, but the `add()` method appends unconditionally.

The consequence propagates through the entire stack:
1. `_data` grows → `filter_by_tags()` returns duplicates → `GET /metrics` returns N entries per name → frontend renders N cards
2. `_data` grows → `by_name()` scan is O(n) → alert evaluation slows every 10 seconds

The fix requires `GET /metrics` to deduplicate and return only the latest entry per metric name. The existing `_history` structure and `GET /metrics/{name}/history` endpoint already provide bounded historical access, so no new API surface is needed — only the `list_metrics` response must be deduplicated.

## Acceptance Criteria

**Fixed** means:

1. `GET /metrics` returns exactly one entry per unique metric name — the most recently submitted value
2. Submitting `cpu` 100 times results in exactly one `cpu` card visible in the dashboard
3. `MetricStore._data` either: (a) stores only latest-per-name, OR (b) `list_metrics` deduplicates before returning
4. `store.by_name()` for alert evaluation does not scan all `_data` — it returns (or derives) the latest value in O(1) or O(unique names) time
5. Historical data remains accessible via `GET /metrics/{name}/history` (unchanged)
6. `DELETE /metrics/{name}` still removes all data for that name (history and current)
7. Existing tag filter tests continue to pass (`test_tag_filter_*`)
8. New regression test: `test_list_metrics_returns_one_card_per_name` — submit same name 5 times, `GET /metrics` returns 1 entry
9. Frontend `MetricCard` key prop updated to `key={m.name}` (or equivalent) to prevent stale duplicate cards on re-render
