# Bug Report: BUG-002

| Field | Value |
|-------|-------|
| ID | BUG-002 |
| Type | Bug |
| Severity | High |
| Status | Open |
| Module | backend |
| Created | 2026-03-01 |

## Summary

When a metric is deleted via the DELETE /metrics/{name} endpoint, alert rules that reference the deleted metric name continue to exist and evaluate against an empty dataset. During the next evaluation cycle, these alerts incorrectly transition from "firing" state to "ok" state, even though the underlying condition that triggered the alert has not been resolved. This causes stale alerts to appear resolved when they should either remain firing until manually addressed or be automatically deleted along with the metric.

## Steps to Reproduce

1. Start the FastAPI backend server
2. Create a metric with high value: `POST /metrics {"name": "cpu_usage", "value": 95.0}`
3. Create an alert rule for that metric: `POST /alerts {"metric_name": "cpu_usage", "operator": "gt", "threshold": 80.0}`
4. Wait for the evaluation loop to run (10 seconds) - alert should transition to "firing" state
5. Delete the metric: `DELETE /metrics/cpu_usage`
6. Wait for the next evaluation cycle (10 seconds)
7. Check alert state via `GET /alerts`

## Expected Behavior

After deleting a metric that has associated alert rules, one of the following should occur:
- Alert rules should be automatically deleted along with the metric, OR
- Alert rules should remain in their current state ("firing" if they were firing) until manually resolved, OR  
- Alert rules should transition to a distinct "no data" state that clearly indicates the metric is missing

## Actual Behavior

Alert rules that were in "firing" state incorrectly transition to "ok" state when their associated metric is deleted. This makes it appear as if the alert condition has been resolved when it has not. The alert evaluation logic treats missing metrics the same as metrics with values that don't trigger the alert threshold.

Reproduction evidence:
```
Added metric: cpu_usage = 95.0
Alert state after evaluation: firing
Deleted 1 metrics
Alert state after metric deleted: ok
BUG: Alert should NOT automatically go to ok when metric is deleted!
```

## Environment

- Python: 3.13.7
- FastAPI: 0.115.6
- Pydantic: 2.10.3
- Uvicorn: 0.32.1
- OS: macOS

## Severity

High — This bug causes incorrect alert state management which could lead to missed critical alerts. Operations teams relying on this system might believe alerts have been resolved when they have not, potentially causing unnoticed system issues. The bug affects core alerting functionality and could result in false sense of security.

## Module/Area

backend — Affects the alert evaluation logic in `backend/alert_store.py`, specifically the `evaluate` method that processes alert rules against metric data. The bug also involves the interaction between `backend/main.py` DELETE endpoint and the alert system's lifecycle management.

## Evidence

**Root Cause Location**: [backend/alert_store.py](backend/alert_store.py#L34-L38)
```python
if not metrics:
    # No data → not firing
    new_state = "ok"
```

**Problem Analysis**:
1. The `evaluate` method in `AlertStore` calls `metric_store.by_name(rule.metric_name)` which returns an empty list when metrics are deleted
2. The logic assumes empty metrics list should result in "ok" state, but this is incorrect for firing alerts
3. The DELETE /metrics/{name} endpoint in `main.py` only removes metrics from `MetricStore`, it doesn't handle associated alert rules
4. The evaluation loop continues running every 10 seconds via `_evaluate_loop` in `main.py`, inadvertently "resolving" firing alerts

**Affected Files**:
- [backend/alert_store.py](backend/alert_store.py#L34) - Incorrect evaluation logic for missing metrics
- [backend/main.py](backend/main.py#L112) - DELETE endpoint lacks alert cleanup
- [frontend/src/App.tsx](frontend/src/App.tsx#L58) - UI shows incorrect "ok" state for orphaned alerts

**Test Evidence**: 
The bug is inadvertently covered by `test_evaluate_no_metrics()` in [backend/tests/test_alert_store.py](backend/tests/test_alert_store.py#L6), which expects alerts with no metrics to stay in "ok" state. However, this test only covers new rules, not existing firing rules that lose their metrics.

## Root Cause Analysis

The root cause is in the `AlertStore.evaluate` method which treats "no metrics found" the same as "metrics found but don't meet threshold". When `metric_store.by_name()` returns an empty list (due to metric deletion), the code sets `new_state = "ok"` regardless of the alert's previous state. This logic fails to distinguish between:
1. A new alert rule with no data (should be "ok") 
2. A firing alert whose metric was deleted (should maintain state or be handled specially)

## Acceptance Criteria

**Fixed** when:
1. Alert rules with "firing" state that lose their associated metrics do NOT automatically transition to "ok"
2. Either: Alert rules are automatically deleted when their metric is deleted, OR
3. Or: Alert rules maintain their previous state when metrics are missing, OR  
4. Or: Alert rules transition to a new "no_data" state that clearly indicates missing metrics
5. The DELETE /metrics/{name} endpoint includes proper alert rule lifecycle management
6. Tests exist that verify correct behavior when firing alerts lose their metrics
7. Frontend UI properly displays the chosen resolution (deleted alerts, maintained state, or no_data state)