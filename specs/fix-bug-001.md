# Plan: Fix BUG-001 — Frontend Alert Polling Integration

> **EXECUTION DIRECTIVE**: This is a team-orchestrated plan.
> **FORBIDDEN**: Direct implementation by the main agent.
> **REQUIRED**: Execute ONLY via the `build` prompt, which orchestrates sub-agents.

## Task Description

The frontend lacks alert functionality entirely, causing a disconnect between metric data and alert states. The bug report at bugs/BUG-001/report.md identifies that frontend/src/api.ts is missing alert API functions (fetchAlerts, createAlert, deleteAlert), and frontend/src/App.tsx has no alert polling logic. While the backend has working alert evaluation every 10 seconds and provides endpoints (GET /alerts, POST /alerts, DELETE /alerts/{id}), the frontend polls only metrics every 5 seconds with no awareness of alert states. This creates a timing mismatch where users see current metric values but miss critical alert state changes entirely.

The fix requires adding complete alert integration to match the existing metrics pattern: API client functions in api.ts using raw fetch(), alert state management in App.tsx with synchronized polling, and proper TypeScript interfaces based on backend models (AlertRuleIn, AlertRuleOut from backend/models.py).

## Objective

Alert states are fully integrated with the frontend metrics dashboard. Users can view current alert rules alongside metrics, with alert states updating on the same 5-second polling cycle as metric data. No stale alert states are visible when metrics cross thresholds, and the system maintains data consistency between metrics and alerts within the frontend polling window.

## Relevant Files

- **frontend/src/api.ts** — Add fetchAlerts(), createAlert(), deleteAlert() functions using raw fetch() API following existing patterns for fetchMetrics/submitMetric/deleteMetric
- **frontend/src/App.tsx** — Add alert state management and synchronized polling logic alongside existing metrics polling  
- **frontend/src/App.test.tsx** — Add regression tests for alert functionality and polling integration
- **backend/models.py** — Reference for AlertRuleIn/AlertRuleOut TypeScript interface shapes (no changes needed)
- **backend/main.py** — Reference for alert endpoint contracts: GET /alerts → AlertRuleOut[], POST /alerts → AlertRuleOut, DELETE /alerts/{id} → {deleted: number}

## Step by Step Tasks

### 1. Add Alert TypeScript Interfaces and API Functions
- **Task ID**: add-alert-api-functions
- **Role**: builder
- **Depends On**: none
- **Assigned To**: builder
- **Description**: |
    Add complete alert API integration to frontend/src/api.ts following the existing metrics pattern. Define TypeScript interfaces AlertRuleIn and AlertRuleOut matching backend/models.py (AlertRuleIn has metric_name, operator "gt"|"lt"|"eq", threshold; AlertRuleOut adds id, state "ok"|"firing", created_at). Implement fetchAlerts() function calling GET /api/alerts returning AlertRuleOut[], createAlert(rule: AlertRuleIn) calling POST /api/alerts with JSON body returning AlertRuleOut with 201 status check, and deleteAlert(ruleId: string) calling DELETE /api/alerts/{ruleId} returning {deleted: number}. Use raw fetch() API with proper error handling following existing fetchMetrics/submitMetric patterns. Set Content-Type: application/json for POST requests. Include TypeScript strict mode compliance with explicit return types and parameter types.
    
    **Acceptance Criteria**: api.ts exports AlertRuleIn, AlertRuleOut interfaces and fetchAlerts, createAlert, deleteAlert functions with proper typing and error handling
    **Validation Command**: `cd frontend && npm run typecheck`

### 2. Add Alert State Management to App Component
- **Task ID**: add-alert-state-management  
- **Role**: builder
- **Depends On**: add-alert-api-functions
- **Assigned To**: builder
- **Description**: |
    Integrate alert state management into frontend/src/App.tsx alongside existing metrics state. Import AlertRuleOut interface and fetchAlerts function from api.ts. Add useState<AlertRuleOut[]> for alerts state and loading/error states specifically for alerts. Create loadAlerts async function following loadMetrics pattern with try/catch error handling and setAlerts/setError state updates. Add alert polling to the existing useEffect hook - modify the interval callback to call both loadMetrics() and loadAlerts() concurrently using Promise.all or sequential calls to synchronize data fetching. Ensure alerts poll on the same 5-second cycle as metrics to maintain data consistency. Handle loading states appropriately - show loading indicator until both metrics and alerts are loaded initially.
    
    **Acceptance Criteria**: App.tsx manages alert state with synchronized 5-second polling alongside metrics, proper loading/error handling for alerts
    **Validation Command**: `cd frontend && npm run typecheck && npm run lint`

### 3. Add Alert Polling Integration Tests
- **Task ID**: add-alert-polling-tests
- **Role**: builder  
- **Depends On**: add-alert-state-management
- **Assigned To**: builder
- **Description**: |
    Add comprehensive tests to frontend/src/App.test.tsx covering alert functionality and the specific BUG-001 regression scenario. Mock fetchAlerts in the vi.mock('./api') block returning test AlertRuleOut data. Add test case "renders alerts when returned from API" verifying alert data displays correctly in the component. Create regression test "polls both metrics and alerts synchronously" using vi.useFakeTimers to verify both fetchMetrics and fetchAlerts are called on the same interval cycle, preventing the original bug where only metrics were polled. Test error handling with "handles alert fetch errors gracefully" ensuring alert errors don't break metrics polling. Use @testing-library/react patterns with screen.findByText for async content and proper cleanup. Include test data with realistic alert rule shapes (id, metric_name, operator, threshold, state, created_at) matching backend AlertRuleOut interface.
    
    **Acceptance Criteria**: App.test.tsx has regression tests covering alert polling integration with proper mocking and async assertions  
    **Validation Command**: `cd frontend && npm test -- --run`

### 4. Final Validation
- **Task ID**: validate-all
- **Role**: validator
- **Depends On**: add-alert-api-functions, add-alert-state-management, add-alert-polling-tests
- **Assigned To**: validator
- **Description**: |
    Run all validation commands and verify acceptance criteria.
    ## Validation Commands
    - `cd frontend && npm run typecheck`
    - `cd frontend && npm run lint`
    - `cd frontend && npm test -- --run`
    ## Acceptance Criteria
    - Frontend api.ts contains fetchAlerts(), createAlert(), deleteAlert() functions using raw fetch() API
    - Frontend App.tsx polls both metrics and alerts every 5 seconds synchronously
    - Alert states update within the same polling cycle as metric data (no stale states)
    - TypeScript interfaces match backend AlertRuleIn/AlertRuleOut models
    - Integration tests verify alert-metric polling synchronization (regression test for BUG-001)
    - All tests pass and code passes TypeScript strict mode and linting

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

- Frontend api.ts contains fetchAlerts(), createAlert(), deleteAlert() functions using raw fetch() API
- Frontend App.tsx polls both metrics and alerts every 5 seconds synchronously  
- Alert states update within the same polling cycle as metric data (no stale states)
- TypeScript interfaces match backend AlertRuleIn/AlertRuleOut models
- Integration tests verify alert-metric polling synchronization (regression test for BUG-001)
- All tests pass and code passes TypeScript strict mode and linting

## Validation Commands

- `cd frontend && npm run typecheck`
- `cd frontend && npm run lint` 
- `cd frontend && npm test -- --run`