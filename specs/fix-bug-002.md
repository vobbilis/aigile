# Fix Plan: BUG-002 — Stale Alerts After Metric Deletion

> **EXECUTION DIRECTIVE**: This is a team-orchestrated plan.
> **FORBIDDEN**: Direct implementation by the main agent.
> **REQUIRED**: Execute ONLY via the `build` prompt, which orchestrates sub-agents.

## Task Description

The bug occurs in the alerting system when a metric is deleted via the `DELETE /metrics/{name}` endpoint. Alert rules that reference the deleted metric continue to exist and evaluate against an empty dataset. During the next evaluation cycle (every 10 seconds), these alerts incorrectly transition from "firing" state to "ok" state, making it appear as if alert conditions have been resolved when they have not.

**Root Cause**: In `backend/alert_store.py`, lines 34-38, the `evaluate` method treats missing metrics the same as metrics with values that don't trigger the alert threshold:
```python
if not metrics:
    # No data → not firing
    new_state = "ok"
```

**Impact**: This causes high-severity bug where firing alerts appear resolved after metric deletion, potentially causing missed critical alerts in production systems.

**Solution**: Automatically delete alert rules when their associated metrics are deleted, ensuring orphaned rules cannot cause incorrect state transitions.

## Objective

Fix the stale alert bug by implementing cascade deletion - when `DELETE /metrics/{name}` is called, automatically delete any alert rules that reference that metric name. This prevents orphaned alert rules from incorrectly transitioning to "ok" state during evaluation cycles.

## Relevant Files

- `backend/alert_store.py` - Add method to delete rules by metric name
- `backend/main.py` - Modify DELETE /metrics/{name} endpoint to cascade delete alert rules
- `backend/tests/test_alert_store.py` - Add unit tests for new AlertStore method
- `backend/tests/test_api.py` - Add regression test and update existing test that expects buggy behavior

## Step by Step Tasks

### 1. Add cascade delete method to AlertStore
- **Task ID**: add-cascade-delete-method
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder
- **Description**: |
    Add a new method `delete_rules_by_metric_name(self, metric_name: str) -> int` to the `AlertStore` class in `backend/alert_store.py`. This method should find all alert rules that have the specified `metric_name` and remove them from the `_rules` list. The method should return the count of deleted rules, following the same pattern as the existing `delete_rule` method. The implementation should use list comprehension to filter out matching rules and calculate the difference in list length before and after filtering.

### 2. Modify DELETE metrics endpoint to cascade delete alerts
- **Task ID**: modify-delete-endpoint
- **Role**: builder
- **Depends On**: add-cascade-delete-method
- **Assigned To**: builder
- **Description**: |
    Modify the `delete_metric` function in `backend/main.py` around line 95. After calling `store.delete(name)` to delete metrics, also call `alert_store.delete_rules_by_metric_name(name)` to delete any associated alert rules. Update the return value to include both deleted metrics and deleted alert rules. Change the return dictionary from `{"deleted": deleted}` to `{"deleted": deleted, "alerts_deleted": alerts_deleted}` to provide visibility into the cascade deletion. This ensures that when metrics are deleted, orphaned alert rules are automatically cleaned up.

### 3. Add unit tests for AlertStore cascade delete method
- **Task ID**: test-cascade-delete-method
- **Role**: builder
- **Depends On**: add-cascade-delete-method
- **Assigned To**: builder
- **Description**: |
    Add comprehensive unit tests for the new `delete_rules_by_metric_name` method in `backend/tests/test_alert_store.py`. Create at least three test cases: (1) `test_delete_rules_by_metric_name_existing` - verify deletion count when rules exist, (2) `test_delete_rules_by_metric_name_nonexistent` - verify zero count when no rules match, and (3) `test_delete_rules_by_metric_name_multiple` - verify deletion when multiple rules reference the same metric. Each test should create AlertStore and AlertRuleIn instances, add rules, call the new method, and assert both the return count and that the correct rules were removed from the store.

### 4. Add regression test for cascade deletion behavior
- **Task ID**: add-regression-test
- **Role**: builder
- **Depends On**: modify-delete-endpoint
- **Assigned To**: builder
- **Description**: |
    Add a new regression test function `test_delete_metric_cascades_alert_deletion()` in `backend/tests/test_api.py`. This test should: (1) Create an alert rule for a metric, (2) Submit a metric that triggers the alert, (3) Run evaluation to make alert firing, (4) Delete the metric via DELETE /metrics/{name}, (5) Verify that both the metric and its alert rule are deleted, (6) Verify the response includes both deleted metrics and alerts counts. This test specifically covers the bug scenario and ensures that firing alerts are properly cleaned up when their metrics are deleted, preventing the original stale alert issue.

### 5. Update existing test that expects buggy behavior
- **Task ID**: fix-existing-test
- **Role**: builder
- **Depends On**: modify-delete-endpoint
- **Assigned To**: builder
- **Description**: |
    Update the existing test `test_delete_metric_does_not_affect_alert_rules()` in `backend/tests/test_api.py` around line 538. This test currently expects the buggy behavior where alerts remain after metric deletion and go to "ok" state. Rename it to `test_delete_metric_removes_related_alert_rules()` and update the test logic to expect that alert rules are deleted along with metrics. The test should verify that after deleting metrics, the alert rules are also removed (GET /alerts returns empty list), and include verification of the new response format that shows both deleted metrics and alerts counts.

### 6. Final Validation
- **Task ID**: validate-all
- **Role**: validator
- **Depends On**: add-cascade-delete-method, modify-delete-endpoint, test-cascade-delete-method, add-regression-test, fix-existing-test
- **Assigned To**: validator
- **Description**: |
    Run all validation commands and verify acceptance criteria.
    ## Validation Commands
    cd backend && pytest tests/ -v
    cd backend && ruff check .
    cd backend && ruff format --check .
    ## Acceptance Criteria
    All criteria from top-level section must pass

## Team Orchestration

The build prompt orchestrates sub-agents (builder, validator) sequentially.

### Team Members
- Builder
  - Name: builder
  - Role: Implements fix tasks
  - Agent Type: builder
- Validator
  - Name: validator
  - Role: Validates fix meets acceptance criteria
  - Agent Type: validator

## Acceptance Criteria

**Fixed** when:
1. When `DELETE /metrics/{name}` is called, any alert rules referencing that metric name are automatically deleted
2. The DELETE endpoint returns both deleted metrics count and deleted alerts count
3. No orphaned alert rules exist that could incorrectly transition from "firing" to "ok" state
4. All existing functionality remains intact (metrics CRUD, alert CRUD, evaluation loop)
5. New unit tests exist verifying the cascade delete method works correctly
6. Regression test exists that reproduces the original bug scenario and verifies it's fixed
7. Updated existing test no longer expects the buggy behavior
8. All tests pass with the fix in place

## Validation Commands

cd backend && pytest tests/ -v
cd backend && ruff check .
cd backend && ruff format --check .