# Bug Report: BUG-004

| Field     | Value                            |
| --------- | -------------------------------- |
| ID        | BUG-004                          |
| Type      | Bug                              |
| Severity  | Medium                           |
| Priority  | High                             |
| Status    | Open                             |
| Reporter  | bug-creator                      |
| Assignee  | bug-fixer-frontend               |
| Module    | frontend                         |
| Labels    | ui, state-management, delete     |
| Created   | 2026-03-15T00:00:00Z             |

---

## Summary

Clicking the delete button on a metric card fires the `DELETE /api/metrics/{name}` request and receives a success response, but the card does not disappear from the UI until the next polling interval (up to 5 seconds). The root cause is in `MetricCard.tsx`: `handleDelete` provides no optimistic state update and calls `onDelete()` without `await`. When `onDelete()` — which is `loadMetrics` in App.tsx — is called unawaited, its Promise is dropped. If the subsequent GET /metrics re-fetch fails for any reason, `setMetrics` is never called and the deleted card persists in the UI until the next 5-second polling cycle. Additionally, `handleDelete` has no try/catch, so any error from `deleteMetric` is silently swallowed and `onDelete` is never invoked.

---

## Steps to Reproduce

1. Start the backend: `cd backend && uvicorn main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Submit a metric via the form (e.g., name: `cpu`, value: `42`)
4. Observe the metric card appears on the dashboard
5. Click the `×` (delete) button on the metric card
6. Observe the card in the UI

---

## Expected Behavior

Upon a successful `DELETE /api/metrics/{name}` response (HTTP 200), the metric card should disappear from the UI **immediately** — before the next polling cycle. The optimistic local state update should remove the card from the rendered list without requiring a full round-trip GET /metrics response.

---

## Actual Behavior

The card remains visible after the delete button is clicked and the API call succeeds. It only disappears when:

- The next polling interval fires (up to 5 seconds later), OR
- The `onDelete()` re-fetch happens to succeed before the next poll

Under adverse conditions (transient network error on the GET /metrics re-fetch), the card may persist for the full 5-second polling cycle. In the worst case, if `deleteMetric` throws (unhandled), `onDelete()` is never called and the card persists indefinitely until the next poll.

---

## Environment

- OS: Darwin (macOS) 25.3.0
- Node: v25.6.1
- React: ^18.3.1
- Vite: ^6.0.3
- Vitest: ^2.1.8
- Python: 3.11.8
- FastAPI: 0.115.6
- Pydantic: 2.10.3

---

## Severity

**Medium** — The delete operation completes successfully at the backend, so no data integrity issue exists. However, the UI inconsistency degrades UX: users see a card that should be gone, which can cause confusion, double-click attempts, or loss of trust in the dashboard's responsiveness.

---

## Module/Area

**frontend** (`frontend/src/`)

Primary affected files:
- `frontend/src/components/MetricCard.tsx` — `handleDelete` function (lines 38–41): no optimistic update, `onDelete()` not awaited, no error handling
- `frontend/src/App.tsx` — `onDelete={loadMetrics}` prop (line 86): the callback is async but callers cannot await it through the prop interface

Secondary (no code bug, but missing test coverage):
- `frontend/src/components/MetricCard.test.tsx` — no test for delete button click behavior

Backend (no bug):
- `backend/main.py` — `DELETE /metrics/{name}` endpoint (lines 121–125): correctly deletes metric and cascade-deletes associated alerts
- `backend/store.py` — `delete()` method (lines 48–52): correctly removes entries and clears history
- `backend/alert_store.py` — `delete_rules_by_metric_name()` (lines 30–33): cascade delete works correctly

---

## Evidence

### Frontend: Missing Optimistic Update and Unawaited Callback

**File:** `frontend/src/components/MetricCard.tsx`, lines 38–41

```typescript
const handleDelete = async () => {
  await deleteMetric(metric.name)
  onDelete()  // ← NOT awaited; dropped Promise; no optimistic update; no error handling
}
```

- `deleteMetric(metric.name)` is correctly awaited and returns `{ deleted: N, alerts_deleted: M }` on success
- `onDelete()` is `loadMetrics` (App.tsx line 86), an async function that performs a GET /metrics round-trip
- `onDelete()` is called **without `await`** — its Promise is immediately discarded
- There is **no try/catch** around `deleteMetric` — any error silently prevents `onDelete()` from being called
- There is **no optimistic update** — no `setMetrics(prev => prev.filter(...))` call on success

**File:** `frontend/src/App.tsx`, line 86

```tsx
<MetricCard key={m.id} metric={m} onDelete={loadMetrics} />
```

`loadMetrics` (lines 19–29) fetches GET /metrics and calls `setMetrics(data)` only after the response arrives. If the re-fetch fails, `setMetrics` is never called and the deleted metric remains in the previous state.

### Backend: DELETE Endpoint Works Correctly

**File:** `backend/main.py`, lines 121–125

```python
@app.delete("/metrics/{name}")
def delete_metric(name: str) -> dict[str, int]:
    deleted = store.delete(name)
    alerts_deleted = alert_store.delete_rules_by_metric_name(name)
    return {"deleted": deleted, "alerts_deleted": alerts_deleted}
```

Returns HTTP 200 with `{"deleted": N, "alerts_deleted": M}`. Backend data is removed synchronously from the in-memory store before the response is sent.

### Backend Tests: All Delete Tests Pass

```
tests/test_api.py::test_delete_metric PASSED
tests/test_api.py::test_history_cleared_by_delete PASSED
tests/test_api.py::test_delete_alert_existing PASSED
tests/test_api.py::test_delete_alert_nonexistent PASSED
tests/test_api.py::test_delete_alert_removes_from_list PASSED
tests/test_api.py::test_delete_metric_does_not_affect_alert_rules PASSED
tests/test_api.py::test_delete_metric_cascades_alert_deletion PASSED

======================= 7 passed, 44 deselected in 0.34s =======================
```

### Frontend Tests: Delete Click Behavior Is Untested

```
✓ src/components/MetricCard.test.tsx > MetricCard > renders metric name and value
✓ src/components/MetricCard.test.tsx > MetricCard > calls fetchMetricHistory on mount
✓ src/components/MetricCard.test.tsx > MetricCard > renders sparkline when history data is available
✓ src/components/MetricCard.test.tsx > MetricCard > does not render sparkline when history is empty
✓ src/components/MetricCard.test.tsx > MetricCard > does not render sparkline when history fetch fails
✓ src/components/MetricCard.test.tsx > MetricCard > renders delete button with correct aria label
✓ src/components/MetricCard.test.tsx > MetricCard > renders metric tags

Test Files  1 passed (1)
     Tests  7 passed (7)
```

**None of the 7 tests simulate clicking the delete button or verify that `onDelete` is called after a successful delete.** The missing test allowed the unawaited/no-optimistic-update bug to go undetected.

---

## Root Cause Analysis

**Primary Cause:** `handleDelete` in `MetricCard.tsx` (line 38–41) does not perform an optimistic local state update after `deleteMetric` resolves. Instead, it delegates the entire UI refresh to `onDelete()` (= `loadMetrics`), which requires a full asynchronous GET /metrics round-trip. Because `onDelete()` is called without `await`, its Promise is dropped — the caller has no reference to await or catch.

**Secondary Cause:** `handleDelete` has no `try/catch`. A thrown exception from `deleteMetric` (e.g., network error, non-2xx status) silently prevents `onDelete()` from ever being called, leaving the card on screen until the next polling interval.

**Contributing Factor:** The `MetricCard.test.tsx` suite has no test for the delete click interaction, allowing this defect to ship undetected.

---

## Acceptance Criteria

**Fixed** means:

1. Clicking the delete button causes the metric card to disappear **immediately** upon API success — before any polling cycle fires
2. The optimistic update uses `setMetrics(prev => prev.filter(m => m.name !== metric.name))` (or equivalent) called synchronously after `await deleteMetric(...)` resolves
3. `handleDelete` wraps the delete call in try/catch; errors are surfaced to the user (e.g., an error state or console message)
4. A new test in `MetricCard.test.tsx` (or `App.test.tsx`) simulates clicking the delete button, mocks `deleteMetric` to resolve, and asserts that the card is removed from the DOM without requiring an additional `fetchMetrics` call
5. All existing backend tests continue to pass (`7 passed`)
6. All existing frontend tests continue to pass (`7 passed`)
