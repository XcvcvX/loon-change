# Phase 11 batch 7 — Amap suggestion scalar property cache

## Scope
- Runtime: `scripts/amap/amap.js`
- Upstream regeneration: `tools/optimize_amap.py`
- Regression coverage: `tests/test_amap_rstore_performance.py` and `tests/optimization_invariants.json`

## Finding
The Amap search-suggestion compaction modes already cached each item's nested `tip` object, but repeatedly read its scalar fields while evaluating exclusion predicates. In the full suggestions mode, `result_type` was read three times and `task_tag` four times per item; the city-suggestions mode reread `result_type`.

## Change
- Snapshot `datatype_spec`, `result_type`, and `task_tag` into locals once per item in the full suggestions mode.
- Snapshot `datatype_spec` and `result_type` once per item in the city-suggestions mode.
- Preserve the exact exclusion values, boolean predicate order, stable in-place compaction, retained item ordering, and lazy serialization behavior.
- Update the reproducible upstream optimizer and make it fail closed if the scalar-cache structure drifts.
- Extend the checked-in optimization invariants and regression tests.

## Expected runtime effect
For each item, the full suggestions loop reduces scalar property reads from 8 to 3; the city-suggestions loop reduces them from 3 to 2. This does not alter the number of array passes or allocate replacement arrays.

## Validation boundary
The change is a structural reduction in repeated property reads. It is not a measured iPhone CPU, battery, thermal, or latency benchmark.
