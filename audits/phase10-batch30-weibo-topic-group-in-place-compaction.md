# Phase 10 batch 30 — Weibo topic-group in-place compaction

## Scope
The Weibo topic timeline handler filters the top-level topic-group items when `itemId === null`. The previous loop allocated a new `newII` array and assigned it back to `item.items` after every child item, causing repeated array allocation and repeated property assignment in a single pass.

## Change
- Reuse the parsed `item.items` array and compact it with read/write indices.
- Cache each child `data` object and `itemid` once for the keep/drop decision.
- Preserve the three retained item-id categories, the pass-through behavior for records without an own `itemid`, search-hotword replacement, avatar cleanup for every child, and original item order.
- Set the final array length once after traversal; remove the per-item new-array allocation and repeated parent-property assignment.

## Validation
- Added optimizer idempotence and fail-closed drift checks.
- Added a Node runtime fixture covering all keep/drop categories, order, hotword replacement, and avatar cleanup.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
