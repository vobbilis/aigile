# BUG-003: Frontend Polling Interval Resets on Filter Toggle

| Field      | Value                                           |
|------------|-------------------------------------------------|
| ID         | BUG-003                                         |
| Type       | Bug                                             |
| Severity   | Medium                                          |
| Priority   | P2                                              |
| Status     | Open                                            |
| Reporter   | bug-creator                                     |
| Assignee   | bug-fixer-frontend                              |
| Module     | frontend                                        |
| Labels     | polling, tag-filter, useEffect, timer           |
| Created    | 2026-03-15                                      |

---

## Summary

The 5-second polling interval for metrics data resets to zero every time the user adds or removes a tag filter. This is caused by `activeTags` being listed as a dependency of the `useEffect` that owns the `setInterval` in `App.tsx`. Each filter change triggers React to tear down the old effect (clearing the interval) and mount a fresh one (starting the timer from zero), so the next scheduled poll is postponed by up to 5 seconds relative to when the user expected it.

---

## Steps to Reproduce

1. Open the Metrics Dashboard frontend (`npm run dev`).
2. Wait approximately 3–4 seconds after initial load (so the polling timer is roughly mid-cycle).
3. Type a valid tag (e.g. `env:prod`) in the **Filter by tag** input and click **Add Filter**.
4. Observe when the next API call to `/api/metrics` fires (e.g. via browser DevTools → Network tab).
5. Remove the same tag chip by clicking the **×** button.
6. Again observe when the next API call fires.

---

## Expected Behavior

Adding or removing a tag filter should trigger an **immediate** one-time fetch with the new filter set, but the background polling timer should continue running on its existing schedule. The next periodic poll should fire at most `POLL_INTERVAL_MS` (5 000 ms) after the previous one — regardless of filter changes.

---

## Actual Behavior

Every time a tag is added or removed, the polling interval resets from zero. Concretely:

- If the user adds a tag at t = 4 s (1 s before the next scheduled poll), the next poll does not fire at t = 5 s — it fires at t = 9 s.
- If the user toggles filters rapidly or repeatedly within any 5-second window, the periodic poll may be postponed indefinitely.
- The dashboard therefore shows stale data for longer than users expect after any filtering interaction.

---

## Environment

| Key              | Value                                |
|------------------|--------------------------------------|
| Component        | `frontend/src/App.tsx`               |
| Framework        | React 18.3.1 (Vite 6, TypeScript 5) |
| Test runner      | Vitest 2.1.8                         |
| Node             | (project default — darwin/zsh)       |
| Browser          | All (client-side timer issue)        |
| Branch           | fix/bug-003                          |

---

## Severity

**Medium** — Polling still occurs; data is not permanently lost. However, the user experience degrades measurably whenever tag filters are used interactively, and in pathological cases (rapid toggling) polling can be starved for multiple cycles.

---

## Module/Area

**frontend** (`frontend/src/`)

Primary file: `frontend/src/App.tsx` — `useEffect` at lines 39–46.

---

## Evidence

### Root Cause — Source Code

**File:** `frontend/src/App.tsx`, lines 39–46

```tsx
useEffect(() => {
  const loadData = async () => {
    await Promise.all([loadMetrics(), loadAlerts()])
  }
  loadData()                                    // immediate fetch ✓
  const timer = setInterval(loadData, POLL_INTERVAL_MS)
  return () => clearInterval(timer)             // cleanup on re-run
}, [activeTags])                                // ← BUG: fires on every filter change
```

**Sequence of events when a tag is added/removed:**

1. `activeTags` state changes → React schedules effect teardown + re-mount.
2. Cleanup: `clearInterval(timer)` — the current polling timer is cancelled.
3. Re-mount: `loadData()` fires immediately (correct), then `setInterval` restarts the 5 000 ms countdown **from zero**.
4. Result: the next periodic poll is delayed by up to 5 000 ms relative to the previous one.

### No Existing Test Covers This Regression

`frontend/src/App.test.tsx` has a polling test (lines 69–87) that advances fake timers by 5 000 ms and verifies call counts, but it never changes `activeTags` mid-cycle. The test suite passes cleanly:

```
✓ src/App.test.tsx (13 tests) 206ms
✓ src/api.test.ts (14 tests) 5ms
✓ src/components/SparklineChart.test.tsx (4 tests) 14ms
✓ src/components/MetricCard.test.tsx (7 tests) ...
Test Files  4 passed (4)
Tests  38 passed (38)
```

A new test that adds a tag at t = 4 000 ms and asserts the next poll fires by t = 10 000 ms (not t = 9 000 ms) would fail against the current implementation.

### Proposed Reproduction Test (currently not in codebase)

```tsx
it('does not reset polling interval when activeTags changes', async () => {
  vi.useFakeTimers()
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  render(<App />)

  // Advance 4 seconds — one second before the first periodic poll
  await vi.advanceTimersByTimeAsync(4000)
  expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(1) // only initial

  // Add a tag filter
  const input = screen.getByPlaceholderText('Filter by tag (e.g. env:prod)')
  await user.type(input, 'env:prod')
  await user.click(screen.getByText('Add Filter'))

  // Immediate re-fetch fires (due to activeTags change) — call count = 2
  expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(2)

  // With current bug: advancing 5 more seconds (total 9s) gets call count to 3
  // EXPECTED (no reset): advancing only 1 more second (total 5s) should get 3
  await vi.advanceTimersByTimeAsync(1000)
  // This assertion FAILS with the current implementation:
  expect(vi.mocked(api.fetchMetrics)).toHaveBeenCalledTimes(3)
})
```

---

## Root Cause Analysis

`useEffect` with `[activeTags]` as dependency owns **both** the immediate data fetch and the recurring `setInterval`. Because React destroys and recreates the entire effect on each dependency change, the interval invariably restarts from zero. The fix is to decouple the two concerns: keep a single, stable `setInterval` on mount/unmount (empty dependency array `[]`), and trigger an additional one-time fetch whenever `activeTags` changes using a separate `useEffect([activeTags])` that does **not** touch the timer.

---

## Acceptance Criteria

- [ ] Changing `activeTags` (add or remove a filter) triggers an immediate `fetchMetrics` call with the new filter set.
- [ ] The background polling timer is **not** reset when `activeTags` changes; the next periodic poll fires within `POLL_INTERVAL_MS` of the **previous** poll, not of the filter change.
- [ ] A regression test is added to `App.test.tsx` that sets fake timers, advances to mid-cycle, changes a tag filter, advances past the original scheduled time, and asserts the poll fired on schedule.
- [ ] All existing 38 tests continue to pass after the fix.
