# Bug Report: BUG-007

| Field    | Value                                                                 |
| -------- | --------------------------------------------------------------------- |
| ID       | BUG-007                                                               |
| Type     | Bug                                                                   |
| Severity | Critical                                                              |
| Priority | High                                                                  |
| Status   | Open                                                                  |
| Reporter | bug-creator                                                           |
| Assignee | Unassigned                                                            |
| Module   | backend                                                               |
| Labels   | alerts, asyncio, float-comparison, loop-recovery, silent-failure      |
| Created  | 2026-03-16T01:00:00Z                                                  |

## Summary

Dashboard alert evaluation suffers from two related defects in `backend/alert_store.py` and `backend/main.py`:

1. **No exception recovery in `_evaluate_loop`** (`main.py:19-22`): The background asyncio task that runs alert evaluation every 10 seconds has no `try/except` block. Any unhandled exception raised inside `alert_store.evaluate()` propagates to the task level, killing the task permanently. Once dead, the loop is never restarted by the `lifespan()` context manager, meaning ALL alert evaluation silently stops for the entire process lifetime. The original crash trigger — `IndexError` from `metrics[-1]` on an empty `by_name()` result — has been partially mitigated with an empty-list guard at `alert_store.py:46`, but the loop itself remains fragile: any future exception in `evaluate()` causes the same permanent shutdown.

2. **Exact float equality for `eq` operator** (`alert_store.py:58`): The `eq` operator uses `latest == rule.threshold` for exact IEEE 754 float comparison. Values that differ by floating-point rounding errors — such as `0.1 + 0.2 = 0.30000000000000004` compared against threshold `0.3` — will never fire. Threshold alerts like `"cpu == 80.0"` silently fail to trigger when the actual measured value is `80.000001` due to arithmetic imprecision.

## Steps to Reproduce

### Issue 1: Evaluate loop killed permanently by unhandled exception

1. Start the backend: `cd backend && uvicorn main:app --reload`
2. Observe that the background task `_evaluate_loop` is created by `lifespan()` at startup
3. Create an alert rule:
   ```
   POST /alerts  {"metric_name": "cpu", "operator": "gt", "threshold": 80.0}
   ```
4. Introduce any condition that causes `evaluate()` to raise an unhandled exception (e.g., manually corrupt `_rules` in the store, or trigger a future code path that lacks a guard)
5. The asyncio task created at `main.py:27` is killed and never restarted
6. Submit a metric above the threshold:
   ```
   POST /metrics  {"name": "cpu", "value": 99.0}
   ```
7. Check alert state via `GET /alerts` — the rule will never transition to `"firing"` even though the metric exceeds the threshold

### Issue 2: `eq` operator misses due to float arithmetic

1. Start the backend: `cd backend && uvicorn main:app --reload`
2. Create an `eq` alert rule with threshold `0.3`:
   ```
   POST /alerts  {"metric_name": "result", "operator": "eq", "threshold": 0.3}
   ```
3. Submit a metric whose value is the result of `0.1 + 0.2` (i.e., `0.30000000000000004`):
   ```
   POST /metrics  {"name": "result", "value": 0.30000000000000004}
   ```
4. The alert rule stays in `"ok"` state — it never transitions to `"firing"` despite the value being equal within any reasonable epsilon

## Expected Behavior

1. **Loop recovery**: If `evaluate()` raises any exception, the `_evaluate_loop` should catch the exception (log it) and continue iterating, never dying permanently. Alert evaluation must remain operational regardless of transient errors.

2. **Float equality**: The `eq` operator should use `math.isclose()` with a suitable relative/absolute tolerance so that `0.30000000000000004 == 0.3` compares as equal. Thresholds like `cpu == 80.0` should fire when the actual value is `80.000001`.

## Actual Behavior

1. **Loop recovery**: `_evaluate_loop` (`main.py:19-22`) has no `try/except`. Any exception raised by `alert_store.evaluate()` propagates unhandled, kills the asyncio background task, and all alert evaluation permanently stops. The `lifespan()` context manager at `main.py:26-33` makes no attempt to restart or monitor the task.

2. **Float equality**: `alert_store.py:58` uses `latest == rule.threshold` for the `eq` operator. The Python `float` type uses IEEE 754 double precision, so `0.1 + 0.2 == 0.3` evaluates to `False`. Alert rules with `operator="eq"` silently fail to fire whenever the actual metric value differs from the threshold by any floating-point rounding error.

**Confirmed via direct test:**
```
Near match (80.000001 == 80.0): [] ← should fire but does NOT
0.1 + 0.2 = 0.30000000000000004
0.1 + 0.2 == 0.3: False
math.isclose(0.1+0.2, 0.3): True
```

## Environment

- **Runtime**: Python 3.11.8
- **Framework**: FastAPI (uvicorn ASGI)
- **Test runner**: pytest 8.3.4, pytest-asyncio 0.24.0
- **Platform**: darwin (macOS)
- **Backend path**: `backend/`
- **Affected files**:
  - `backend/main.py` (lines 19-22: `_evaluate_loop`, lines 26-33: `lifespan`)
  - `backend/alert_store.py` (line 58: `eq` operator float comparison)
- **Test command**: `cd backend && uv run pytest tests/ -v`
- **All existing tests pass** (71/71)

## Severity

**Critical** — Issue 1 causes a complete, silent, permanent shutdown of alert evaluation for the lifetime of the process after the first unhandled exception. No alerts will ever fire again. There is no visible error to the operator and no health check exposes the dead background task. Issue 2 causes silent incorrect behavior where `eq` threshold alerts never fire due to floating-point arithmetic — this is a correctness bug that is invisible to users.

## Module/Area

**backend** — `backend/alert_store.py`, `backend/main.py`

## Evidence

### Code: `_evaluate_loop` has no exception handling (main.py:19-22)

```python
async def _evaluate_loop() -> None:
    while True:
        await asyncio.sleep(10)
        alert_store.evaluate(store)  # No try/except — exception kills task permanently
```

### Code: `lifespan()` does not restart or monitor the task (main.py:26-33)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    task = asyncio.create_task(_evaluate_loop())
    yield
    task.cancel()        # Only cancels on shutdown — no restart on failure
    try:
        await task
    except asyncio.CancelledError:
        pass
```

### Code: `eq` operator uses exact `==` float comparison (alert_store.py:57-58)

```python
elif rule.operator == "eq":
    new_state = "firing" if latest == rule.threshold else "ok"
```

### Reproduction output: Float comparison fails for near-equal values

```
$ uv run python3 -c "
from alert_store import AlertStore
from store import MetricStore
from models import AlertRuleIn, MetricIn

ms = MetricStore()
as_ = AlertStore()
rule = as_.add_rule(AlertRuleIn(metric_name='cpu', operator='eq', threshold=80.0))
ms.add(MetricIn(name='cpu', value=80.000001))
transitions = as_.evaluate(ms)
print('Near match (80.000001 == 80.0):', transitions)
"
Near match (80.000001 == 80.0): [] ← should fire but does NOT
```

### Reproduction output: Loop task dies permanently on any unhandled exception

```
$ uv run python3 -c "
import asyncio
from unittest.mock import patch

async def _evaluate_loop():
    while True:
        await asyncio.sleep(10)
        raise RuntimeError('Simulated crash in evaluate()')  # No try/except

async def main():
    task = asyncio.create_task(_evaluate_loop())
    try:
        await task
    except RuntimeError as e:
        print(f'Loop task died: {e}')
        print('All alert evaluation permanently stopped!')

asyncio.run(main())
"
Loop task died: Simulated crash in evaluate()
All alert evaluation permanently stopped!
```

### Python float arithmetic proof

```
0.1 + 0.2 = 0.30000000000000004
0.1 + 0.2 == 0.3: False
math.isclose(0.1 + 0.2, 0.3): True
```

### Test suite baseline: 71/71 passing before fix

```
============================== 71 passed in 0.51s ==============================
```
No existing tests cover:
- Exception recovery in `_evaluate_loop`
- `eq` operator behavior with near-equal float values (only exact `100.0 == 100.0` is tested)

## Root Cause Analysis

### Issue 1: Unhandled exception kills asyncio task

`main.py:27` creates the background task with `asyncio.create_task(_evaluate_loop())`. The coroutine body has no `try/except`. In Python asyncio, an unhandled exception inside a task propagates to the `Task` object and the task is marked as "done with exception". Since no code re-creates or monitors the task, the evaluate loop silently stops forever. The original trigger (empty `by_name()` returning `[]` causing `metrics[-1]` to raise `IndexError`) was partially addressed by the guard at `alert_store.py:46-47`, but the root cause — the naked `while True` loop with no exception boundary — was never fixed.

### Issue 2: IEEE 754 float equality

Python `float` is IEEE 754 double-precision. Arithmetic operations introduce rounding errors that make exact equality tests unreliable. The `==` operator at `alert_store.py:58` requires bit-identical float values. The standard library function `math.isclose(a, b, rel_tol=1e-9)` provides the correct semantic for "are these floats approximately equal".

## Acceptance Criteria

- [ ] `_evaluate_loop` catches all exceptions from `alert_store.evaluate()`, logs the error, and continues the loop without dying
- [ ] After any exception in `evaluate()`, alert evaluation resumes on the next 10-second tick
- [ ] `alert_store.evaluate()` using `operator="eq"` fires when `math.isclose(latest, threshold)` is `True`
- [ ] `math.isclose(0.1 + 0.2, 0.3)` triggers an `eq` alert on threshold `0.3`
- [ ] All 71 existing tests continue to pass
- [ ] New tests added for: (a) loop recovery after exception, (b) `eq` operator with near-equal float values
