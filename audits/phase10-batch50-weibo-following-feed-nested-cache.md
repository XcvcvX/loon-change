# Phase 10 batch 50 — Weibo following-feed nested reference cache

## Scope
Optimized the active Weibo `/2/statuses/container_timeline` and unread-following timeline response branch.

## Change
- Cache the top-level `items` array and its length before compaction.
- Cache each card's `data` reference once before ad classification and subsequent cleanup.
- Reuse cached `title`, `screen_name_suffix_new`, `user`, and `tag_struct` references at their original points of use.
- Preserve the order of all filters and mutations, including forwarding-card, following-state, and promotional-card cleanup.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed structure test.
- Runtime property/array proxy counters expect one read each for items, item.data, nested references, and suffix length/index.
- Runtime output assertions preserve the expected feed item while retaining existing cleanup behavior.

## Performance note
This reduces repeated per-card object and nested-property reads in the high-frequency following feed. No device-level battery, thermal, or latency measurements are claimed.
