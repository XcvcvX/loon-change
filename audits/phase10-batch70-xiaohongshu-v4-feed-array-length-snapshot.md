# Phase 10 batch 70 — Xiaohongshu v4 feed array-length snapshots

## Scope
Optimized the active `/v4/note/videofeed` response handler in `scripts/xiaohongshu/xiaohongshu.js`.

## Changes
- Snapshot `obj.data` into `videoDataSource` and read its array length once into `videoDataLength`.
- Replace the response-level `for...of` traversal with an indexed loop bounded by the cached length. Parsed JSON arrays preserve the same item order and slot visitation.
- Snapshot each item's `function_switch` length once into `functionSwitchLength`, then reuse it for the indexed scan.
- Preserve download permission mutation, reason removal, function-entry insertion, best-stream selection, and `redBookVideoFeed` cache serialization.

## Verification
- Added optimizer idempotence and fail-closed tests.
- Added Node Proxy runtime coverage asserting one length getter read for the feed array and one for a populated `function_switch` array.
- CI regenerates the local script from upstream to validate reproducibility.

## Performance boundary
This removes repeated array-length reads from the two hot loops. It is a structural JavaScript operation-count reduction; no device-side CPU, battery, temperature, or frame-time benchmark is claimed.
