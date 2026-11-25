# Phase 10 batch 54 — Weibo search timeline nested reference cache

## Scope
Optimized the active `/2/search/...container_timeline` response branch.

## Change
- Cache the search-result `items` array and length before in-place compaction.
- Cache `data` references only within feed/card categories that consume them, avoiding additional reads for cells or unrelated item types.
- Cache card `card_type` once and reuse it across existing exclusions.
- Cache group nested `items` and length, then cache each child's `data.card_type` during inner-card filtering.
- Preserve the existing feed/card/cell/group filters and response order.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed checks.
- Runtime getter/proxy counters verify one read for the top array, feed/card data, group items/length, and each nested data reference.
- Output fixture confirms feed/card retention and inner-group ad filtering remain unchanged.

## Performance note
Reduces repeated nested property reads in the active search timeline path without introducing additional data reads for categories that do not consume card data. No device-level CPU, battery, thermal, or latency measurements are claimed.
