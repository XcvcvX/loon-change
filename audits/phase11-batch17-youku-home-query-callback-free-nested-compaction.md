# Phase 11 batch 17 — Youku home.query callback-free nested compaction

## Scope
- Runtime: `scripts/cnftp/cnftp.js`
- Reproducible optimizer: `tools/optimize_cnftp.py`
- Regression coverage: `tests/test_cnftp_performance.py`
- Preservation guard: `optimization_invariants.json`

## Finding
The active CNFTP response handler processes Youku `columbus.home.query` data with nested node arrays up to four levels deep. Each level used `compactInPlace(items, keep)`, invoking a JavaScript callback for every visited element. Nested callbacks were created while walking parent nodes, adding per-item function dispatch and transient closure work on a potentially large page response.

## Change
- Add a dedicated `compactYoukuHomeQuery(items, mode, knownLength)` walker with four explicit modes: root, level2, level3, and level4.
- Move mode dispatch outside each element loop; no predicate callback is created or invoked for individual items.
- Cache every traversed `nodes` array reference and its length once, passing the snapshot into the next depth.
- Preserve the existing order of field cleanup and filtering: root node keys, index-position cards, refresh backgrounds, CRM banners, hot keywords, ad drawer/banner cards, carousel card ID, and nested ad-marked cards.
- Keep in-place stable compaction, update `modified` only when an array is shortened, and retain the existing lazy serialization behavior.
- Add a fail-closed optimizer migration for the reviewed prior callback branch, idempotence checks, a static invariant, and runtime tests that verify output order, nested cleanup, one length read per traversed node array, and no `filter/map/forEach` callbacks.

## Expected effect
Removes one per-element JavaScript callback invocation from each visited item across up to four nested levels, and avoids repeatedly reading the same nested `nodes` reference/length. No temporary filtered arrays or extra traversal are introduced.

## Validation boundary
The regression fixture exercises all four levels, verifies the retained IDs and order, confirms nested cleanup behavior, counts one `length` read for each traversed `nodes` array, and makes array callback methods fail during the target route. This is a structural operation-count reduction; no iPhone CPU, battery, heat, or latency benchmark is claimed.
