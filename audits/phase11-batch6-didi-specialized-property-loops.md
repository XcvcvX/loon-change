# Phase 11 batch 6 — Didi specialized property access in response hot loops

## Scope
- Runtime: `scripts/didi/didi.js`
- Reproducible optimizer: `tools/optimize_didi.py`
- Regression coverage: `tests/test_didi_performance.py`

## Finding
The Didi response-array compactor already selected a dedicated loop by mode, but still accepted a dynamic `field` parameter and used `item[field]` inside the hot loop. Every element therefore performed a dynamic-key property access even though the key is fixed for each mode.

## Change
- Remove the dynamic field parameter from the helper.
- Use fixed property accesses per mode: `text`, `nav_id`, `id`, and `title`.
- Update all seven call sites to the two-argument helper.
- Keep every predicate, stable in-place compaction, recursion order, response route, and lazy serialization behavior unchanged.
- Upgrade the upstream optimizer to migrate the prior v1 helper and call sites, with explicit inventory and fail-closed checks.
- Add regression tests for fixed-key access.

## Validation boundary
This removes dynamic-key lookup from seven array-processing call paths. It is a structural runtime simplification, not a measured iPhone CPU, battery, thermal, or latency benchmark.
