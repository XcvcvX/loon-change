# Phase 11 · Batch 20 — CNTV Youku home.query callback-free nested compaction

## Scope

- Active production script: `scripts/cntv/cntv.js`.
- Active response route: `columbus.home.query/` (the consolidated plugin routes Youku response triggers to this CNTV runtime).
- Rebuild integration: `tools/optimize_cntv.py` reapplies the helper and route transform after each R-Store upstream refresh.

## Change

The former route used `compactInPlace` with four nested predicate callbacks. Each visited node dispatched a callback, and each nested array passed through the generic compactor. The filter logic also repeatedly read nested properties and used static membership lists for small, fixed sets.

The replacement `compactCntvYoukuHomeQuery` selects one of four modes (`root`, `level2`, `level3`, `level4`) before entering each indexed loop. It preserves the previous filtering rules, the special early-retain behavior for id `31476`, and the stable order of retained nodes. It snapshots each nested array reference and length once, caches values such as node data, type name, and id, replaces small static membership lookups with scalar comparisons, avoids same-index writes, and only updates array length when the array actually shrinks.

## Regression coverage

- Optimizer tests verify idempotence, migration from the previous four-callback route, and fail-closed behavior when the marked route structure is changed.
- Runtime tests block `filter`, `map`, and `forEach` while executing the route.
- Proxy instrumentation verifies exactly one length read per traversed array, one shrink write per changed array, no length write on an unchanged nested array, and only required element moves.
- The fixture validates root cleanup, the id `31476` special case, all four nesting levels, ad removal, and output ordering.
- The optimization invariant manifest requires the new helper and route markers and forbids the old callback call sites.

## Performance boundary

This is a source-level reduction in predicate callback dispatch, repeated property reads, static membership calls, and no-op array writes on the active Youku home.query route. The test measures array access and write counts in a Node.js runtime fixture; it does not claim real-device CPU, battery, thermal, memory, or latency improvement.
