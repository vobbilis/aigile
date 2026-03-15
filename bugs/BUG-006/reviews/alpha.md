# Review: BUG-006

## Reviewer: alpha

## Verdict: APPROVE

Root cause addressed: YES — _data changed from unbounded list to dict[str, MetricOut] keyed by name. All 5 root causes addressed: unbounded growth, duplicate API responses, duplicate frontend cards, O(n) by_name scan, filter_by_tags duplicates.
No regressions: YES — 71/71 tests pass. All methods updated correctly (all, filter_by_tags, by_name, delete, clear, summary). alert_store.py metrics[-1] still correct.
Test evidence: YES — real pytest output 71 passed in 0.56s. 3 new regression tests: test_list_metrics_returns_one_card_per_name, test_list_metrics_dedup_multiple_names, test_by_name_returns_latest_only.
Edge cases: YES — high submission count (100x), multiple names, delete after dedup, tag filtering, empty store, history isolation all covered.
Fix minimal: YES — 2 source files changed, 1 line frontend, dict restructure backend. No new abstractions.

Concerns: summary() total_data_points now equals unique_names always (minor semantic shift); same-name different-tags overwrite untested (acceptable per spec); no frontend E2E test for key prop (trivial change).

## Test Evidence Reviewed: YES
