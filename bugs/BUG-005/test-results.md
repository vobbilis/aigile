# BUG-005 Test Results

## Backend Tests (pytest)

```
tests/test_api.py::test_metrics_export_csv_tag_filter PASSED
tests/test_api.py::test_metrics_export_csv_multi_tag_filter PASSED
tests/test_api.py::test_metrics_export_csv_no_tag_returns_all PASSED
tests/test_api.py::test_metrics_export_csv_invalid_tag_format PASSED
tests/test_api.py::test_metrics_export_csv_tag_no_match PASSED
```

**67 passed, 1 failed (pre-existing)** — the single failure is `test_metrics_export_csv_with_data` which has a hardcoded date `2026-03-01` that doesn't match today's date `2026-03-15`. This failure is pre-existing and unrelated to BUG-005.

All 5 new BUG-005 backend tests pass.

## Frontend Tests (vitest)

```
 ✓ src/App.test.tsx > App > BUG-005: Export CSV includes active tag filters > export link includes tag params when tags are active
 ✓ src/App.test.tsx > App > BUG-005: Export CSV includes active tag filters > export link has no tag params when no tags active
 ✓ src/App.test.tsx > App > BUG-005: Export CSV includes active tag filters > export link includes multiple tag params
 ✓ src/App.test.tsx > App > BUG-005: Export CSV includes active tag filters > export link reverts to base URL when all tags removed
```

**Test Files: 4 passed (4) | Tests: 46 passed (46)**

All 4 new BUG-005 frontend tests pass. All pre-existing tests continue to pass.

## Summary

| Suite    | New Tests | New Pass | New Fail | Total Pass | Total Fail | Pre-existing Fail |
|----------|-----------|----------|----------|------------|------------|-------------------|
| Backend  | 5         | 5        | 0        | 67         | 1          | 1 (date mismatch) |
| Frontend | 4         | 4        | 0        | 46         | 0          | 0                 |
