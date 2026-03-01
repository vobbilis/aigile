# Bug Report: BUG-001

| Field    | Value                |
| -------- | -------------------- |
| ID       | BUG-001              |
| Type     | Bug                  |
| Severity | High                 |
| Status   | Open                 |
| Module   | frontend             |
| Created  | 2026-02-28T00:00:00Z |

## Summary

The frontend metrics polling interval (5 seconds) conflicts with the backend alert evaluation interval (10 seconds), causing the dashboard to display stale alert states that don't reflect current metric values. The frontend lacks alert polling functionality entirely, and if it were implemented, the mismatched intervals would still create race conditions where metric data updates more frequently than alert state evaluations.

## Steps to Reproduce

1. Start the FastAPI backend with alert evaluation enabled (background task runs every 10 seconds)
2. Create an alert rule via `POST /alerts` with a threshold (e.g., cpu > 80%)
3. Start the frontend (polls metrics every 5 seconds via `setInterval`)
4. Submit metric values that cross the alert threshold at timestamps between evaluation cycles
5. Observe the dashboard between seconds 5-10, 15-20, etc.
6. Notice that new metric values appear immediately but alert states lag behind by up to 10 seconds

## Expected Behavior

Alert states should be synchronized with metric values displayed on the dashboard. When a metric crosses an alert threshold, the alert state should be immediately visible or update within the same polling cycle as the metric data.

## Actual Behavior

Alert states become stale and inconsistent with displayed metric values due to:

1. **Missing Frontend Alert Polling**: The frontend has no API functions to fetch alert states from `GET /alerts` endpoint
2. **Interval Mismatch**: Frontend polls metrics every 5 seconds while backend evaluates alerts every 10 seconds
3. **Race Conditions**: Metric updates occur at timestamps that don't align with alert evaluation cycles

Result: Dashboard shows current metric values but outdated alert states, potentially missing critical alerts or showing false positives.

## Environment

- Python: 3.14.3
- Node: v25.6.1  
- OS: Darwin (macOS)
- Key packages: FastAPI 0.115.6, React 18, Pydantic 2.10.3

## Severity

High — This is a data consistency bug that affects alert reliability. Under load or specific timing conditions, users may miss critical alerts or receive false alert states, compromising the monitoring system's effectiveness.

## Module/Area

frontend — While the backend alert evaluation works correctly, the primary issue is the lack of alert polling in the frontend and the mismatched polling intervals.

Affected files and directories:
- `frontend/src/api.ts` — Missing alert API functions
- `frontend/src/App.tsx` — Missing alert polling logic
- `backend/main.py` — Alert evaluation timing

## Evidence

**Backend Alert Evaluation Interval:**
- File: `backend/main.py` line 17
- Code: `await asyncio.sleep(10)` 
- Alert evaluation runs every 10 seconds in background task

**Frontend Metrics Polling Interval:**
- File: `frontend/src/App.tsx` line 6
- Code: `const POLL_INTERVAL_MS = 5000`
- File: `frontend/src/App.tsx` line 27  
- Code: `const timer = setInterval(loadMetrics, POLL_INTERVAL_MS)`
- Metrics polling runs every 5 seconds

**Missing Frontend Alert Functions:**
- File: `frontend/src/api.ts` lines 1-42
- Contains `fetchMetrics()`, `submitMetric()`, `deleteMetric()`, `fetchMetricHistory()`
- Missing: `fetchAlerts()`, `createAlert()`, `deleteAlert()` functions
- Backend provides endpoints: `GET /alerts`, `POST /alerts`, `DELETE /alerts/{id}` (backend/main.py lines 85-96)

**Backend Alert Store Implementation:**
- File: `backend/alert_store.py` line 33-58
- Method: `evaluate(metric_store)` compares latest metric values against thresholds
- Updates rule states and returns state transitions
- Called from background task but results never exposed to frontend

## Root Cause Analysis

**Primary Cause**: Frontend lacks alert polling functionality entirely. The `frontend/src/api.ts` file contains no functions to interact with the backend alert endpoints (`GET /alerts`, `POST /alerts`, `DELETE /alerts/{id}`).

**Secondary Cause**: Mismatched polling intervals create timing windows where data is inconsistent:
- Frontend fetches metrics every 5 seconds
- Backend evaluates alerts every 10 seconds  
- Between seconds 5-10, frontend shows updated metrics but stale alert states

**Technical Root**: The `_evaluate_loop()` in `backend/main.py` line 15-18 operates independently of frontend polling, with no mechanism to surface alert state changes to the UI.

## Acceptance Criteria

**Fixed** means:

1. Frontend `api.ts` contains functions: `fetchAlerts()`, `createAlert()`, `deleteAlert()`
2. Frontend polling includes both metrics AND alerts on synchronized intervals
3. Alert states update within the same cycle as metric data (≤5 second lag)
4. No stale alert states visible when metric values cross thresholds
5. Alert evaluation frequency matches or exceeds frontend polling frequency
6. Integration tests verify alert-metric state consistency under timing stress