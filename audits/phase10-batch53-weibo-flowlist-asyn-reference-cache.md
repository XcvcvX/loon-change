# Phase 10 batch 53 — Weibo flowlist/container-asyn nested reference cache

## Scope
Optimized the active Weibo `/2/container/asyn` and `/2/flowlist` response paths.

## Change
- Cache each route's top-level item array and length before traversal.
- Cache nested item arrays and their lengths, and reuse each nested card's `data` reference for avatar and vote cleanup.
- Cache `itemId` once in container/asyn and `flowId` once per flowlist channel.
- Cache the flowlist `channelInfo.channels` array and its length while preserving the original recommendation/super-topic tab filters.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed checks.
- Runtime property and proxy counters cover both routes' array references/lengths and nested data/ID fields.
- Runtime output checks ensure follow buttons, vote info, and excluded flow tabs are still removed.

## Performance note
Reduces repeated nested-reference reads and iterator overhead during multi-level response traversal. No device-level CPU, battery, thermal, or latency measurements are claimed.
