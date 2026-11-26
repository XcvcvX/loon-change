# Phase 11 batch 13 — Weibo cardlist mblog reference cache

## Scope
- Runtime: `scripts/weibo/weibo-rstore.js`
- Reproducible optimizer: `tools/optimize_weibo_rstore.py`
- Regression coverage: `tests/test_weibo_rstore_performance.py`

## Finding
The high-frequency `/2/cardlist` route checked `group?.mblog` and then fetched the same property again for `removeAvatar`. The outer card branch repeated the same pattern. Each retained group/card with an mblog therefore performed two reads of the same property.

## Change
- Snapshot each nested group mblog reference once and pass that reference to `removeAvatar`.
- Snapshot each outer card mblog reference once and pass that reference to `removeAvatar`.
- Keep the existing card-type filters, stable in-place compaction, avatar cleanup, response ordering, and lazy serialization unchanged.
- Extend the reproducible optimizer with idempotence and fail-closed structure checks.
- Add regression coverage for the optimized call sites and optimizer drift detection.

## Expected effect
For each card/group with an mblog, this removes one repeated property lookup. It adds no traversal, callback, collection, or replacement-array allocation.

## Validation boundary
The tests establish source structure and preserved response behavior. This is a property-access reduction, not an iPhone CPU, battery, thermal, or latency benchmark.
