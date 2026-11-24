# Phase 10 batch 26 — Weibo /2/page cached itemid reads

## Scope
The /2/page search-card filtering path repeatedly read each card's `itemid` property for up to five substring checks. The nested card-group filter also read `c.itemid` twice.

## Change
- Cache each card's `itemid` once per filter callback.
- In the nested card-group filter, preserve the existing actionlog short-circuit and only read `itemid` if the actionlog check does not already reject the item.
- Keep the original substring checks, their order, optional chaining, filter polarity, in-place compaction, and output order.

## Validation
Added optimizer idempotence/fail-closed checks and a Node runtime fixture for search-page and nested card-group filtering. No device-level CPU, battery, thermal, or latency measurements are claimed.
