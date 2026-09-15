# Double Function Design

Status: Implemented (final workflow audit pending)  
Date: 2026-09-09

## Purpose

Provide the repository's single requested operation: double an integer.

## Public Contract

The implemented public surface is defined at `double.py:1`:

```python
def double(value: int) -> int:
    ...
```

For a positive integer, zero, or a negative integer, `double` returns the
mathematical value `2 * value` as an `int`. The direct expression at
`double.py:2` performs the multiplication and introduces no side effects.

Python's ordinary integer semantics apply, including arbitrary-precision values.
The annotation documents the supported interface; runtime rejection or coercion
of non-`int` values is not required, and no such validation is present in
`double.py:1-2`.

## Current Implementation

- `double.py:1` defines the only public operation with the exact signature
  `double(value: int) -> int`.
- `double.py:2` returns `value * 2` directly, with no helper, coercion, explicit
  overflow handling, or runtime type enforcement.
- `test_double.py:1` imports the public function, and `test_double.py:4` defines
  the sole test function, `test_double`.
- `test_double.py:5-7` invokes the function with `2`, `0`, and `-3`.
  `test_double.py:9-14` contains exactly six checks: expected values `4`, `0`, and
  `-6`, plus `type(result) is int` for each result.

## Files and Responsibilities

- `double.py` owns the public function and contains no unrelated behavior
  (`double.py:1-2`).
- `test_double.py` owns one pytest test named `test_double`
  (`test_double.py:4`). That test covers one positive input, zero, and one
  negative input (`test_double.py:5-7`), checking both mathematical value and
  exact runtime `int` type for each result (`test_double.py:9-14`).

## Constraints

- Use only Python language features; add no dependency.
- Perform no network access or subprocess invocation.
- Add no configuration.
- Keep the implementation direct and readable.

## Verification

From the repository root, run:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/vobbilis/go/src/github.com/vobbilis/codegen/metrics-dashboard/venv/bin/python -m pytest -p no:cacheprovider test_double.py -q
```

Success means pytest exits with status 0 and reports the single promised test as
passed. Positive, zero, and negative value/type assertions must all execute within
that test.

## Assumptions and Deferred Behavior

- The README's `int` contract is authoritative; `bool`, floats, strings, custom
  numeric objects, and explicit runtime type checking are outside scope.
- Overflow handling is unnecessary because Python integers are arbitrary precision.
- Packaging, command-line interfaces, logging, and performance benchmarks are
  outside scope.
- Any requested behavior beyond the `int -> int` contract requires escalation
  before implementation.
