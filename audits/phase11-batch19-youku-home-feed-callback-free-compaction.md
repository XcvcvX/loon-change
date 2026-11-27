# Phase 11 · Batch 19 — Youku home.feed callback-free compaction

## Scope

- Active runtime: `scripts/cnftp/cnftp.js`, referenced by the consolidated plugin's Youku response triggers.
- Route: `columbus.home.feed/`.
- Upstream rebuild: `tools/optimize_cnftp.py` reapplies the change after the CNFTP source is refreshed.

## Change

The previous route ran `compactInPlace` over the root `nodes` array with a callback that always returned `true`. That root pass never removed entries, but still walked the complete array and dispatched one callback per root item. It then dispatched another predicate callback for every item in each `PHONE_FEED_CARD_GROUP`.

The new `compactYoukuHomeFeed` walker traverses the root array without compacting or writing it. It reads each group child-array reference and its length once, then uses a dedicated indexed loop to remove only `PHONE_FEED_CARD_S_AD` and `PHONE_H_UC_AD` children. It preserves root and child order, performs no per-item callbacks or filtered-copy allocations, and writes the child array's `length` only when entries were actually removed.

## Regression protection

- Runtime fixture blocks `Array.prototype.filter`, `map`, and `forEach` while executing the target route.
- Proxy instrumentation checks one length read for the root array and each visited group array.
- Tests assert zero root-array writes, zero writes to unchanged/non-group child arrays, and only the necessary shifts and shrink on the filtered group.
- Optimizer tests cover idempotence, migration from the prior callback-based route, and fail-closed behavior when the marked route structure drifts.
- Both optimization-invariant manifests require the new helper and route markers and forbid the former callback call sites.

## Performance boundary

This removes a redundant root-array compaction pass and per-item predicate callback dispatch from the active `home.feed` route. It also avoids unnecessary same-index writes and unchanged-length assignments in the route's arrays. These are source-level structural reductions; no iPhone CPU, battery, thermal, memory, or latency benchmark is claimed.
