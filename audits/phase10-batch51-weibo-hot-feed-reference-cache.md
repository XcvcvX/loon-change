# Phase 10 batch 51 — Weibo hot-feed response reference cache

## Scope
Optimized the active Weibo `/2/statuses/container_timeline_hot` and `/2/statuses/unread_hot_timeline` response branch.

## Change
- Cache the `items` and `statuses` array references and their lengths before in-place compaction.
- Cache each feed-card `data` reference once and reuse it for ad classification, feed cleanup, and vote cleanup.
- Preserve the two arrays' independent filtering rules and original item order.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed structure validation.
- Runtime counters for both top-level arrays, their lengths, and the feed-card data reference.
- Output assertions check that the status survives and expected feed decorations are still removed.

## Performance note
Reduces repeated response property reads on the active recommendation/hot timeline path. No device-level battery, thermal, or latency measurements are claimed.
