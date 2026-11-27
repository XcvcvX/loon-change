# Phase 11 batch 22 — CNTV iQIYI home-feed callback-free compaction

## Scope
- Active runtime: `scripts/cntv/cntv.js`
- Production route: iQIYI `/views_home/` home-feed response
- Rebuild integration: `tools/optimize_cntv.py`
- Regression coverage: `tests/test_cntv_performance.py`

## Finding
The iQIYI home-feed route compacted its top-level card list through the generic `compactInPlace(items, predicate)` helper. This allocated a per-response predicate closure and dispatched it once for every card. The callback also repeatedly resolved each card's top-banner and block-array references, including reading the nested block-array length again in each loop condition.

## Change
- Replace the per-card callback with a dedicated indexed `compactCntvIqiyiHomeCards` walker.
- Resolve the four fixed ad-card aliases with direct scalar comparisons rather than calling `Array.includes` for every card.
- Cache the home-card array and length once; cache each card's top-banner reference, nested block-array reference, and block-array length before traversing.
- Cache each block's buttons reference before deciding whether to remove the property.
- Preserve the original four ad aliases, nested button-removal condition, retained null/ordinary entries, stable item ordering, and in-place mutation.
- Skip same-index writes and update array length only when cards were actually removed.
- Add optimizer idempotence/fail-closed checks, callback-disabled runtime regression coverage, and a generated-runtime invariant.

## Validation boundary
The regression exercises mixed ad/ordinary/null cards and nested blocks with missing, empty, and non-empty button arrays. It checks output order and deletion behavior while `Array.map`, `Array.forEach`, and `Array.sort` are disabled; the existing harness also disables `Array.filter`. These tests verify source/runtime behavior and structural work reduction, not iPhone CPU, battery, temperature, memory, or end-to-end latency. No device-level performance percentage is claimed.
