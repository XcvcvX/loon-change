# Phase 11 batch 8 — BaiduMap target segment offset cache

## Finding
The initial RepHead header scan already cached each segment's `length`, but repeatedly read the same `messageHead.offset` while validating bounds and calculating the Ads byte-view start. The hot loop could read the same decoded header property up to five times per Ads segment.

## Change
- Snapshot each header's `offset` once into `targetDataOffset`.
- Reuse the local for integer/bounds checks and Ads payload offset arithmetic.
- Preserve validation order, early exits, byte-view creation, target signature preflight, protobuf decode, and response reconstruction.
- Add an idempotent fail-closed optimizer, a static invariant, and a Node runtime getter-count regression.

## Expected effect
The initial scan reads each consumed header offset once, rather than repeating the property read across the validation predicates and offset calculation. The runtime fixture verifies two reads total for a normal Result + Ads pair (one per header). No device CPU, battery, thermal, or latency benchmark is claimed.
