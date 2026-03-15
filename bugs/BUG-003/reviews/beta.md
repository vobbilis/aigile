# Review: BUG-003

## Reviewer: beta

## Verdict: APPROVE

The fix correctly addresses the root cause by decoupling the stable polling interval from activeTags state via a useRef pattern and a separate useEffect for immediate filter-change fetches. Minimal implementation, idiomatic React, both add and remove scenarios covered by regression tests. All 40 tests pass. No regressions introduced.
