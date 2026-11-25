# Phase 10 · Batch 65 — BaiduMap protobuf segment metadata cache

## Scope
The active BaiduMap binary response reconstruction helper `assembleBaiduResponseSegments`, which rebuilds the protobuf payload only after a target Ads segment has changed.

## Finding
The rebuild path validated each header by repeatedly reading `header.offset` and `header.length`, then read them again when constructing the internal segment descriptor. The same helper also reevaluated stable `messageHead`, `segments`, and `chunks` array lengths in loop conditions.

## Change
- Cache each segment's original offset and length once, preserving validation order and all existing bounds checks.
- Cache the `messageHead` length before metadata collection.
- Cache the sorted `segments` length and completed `chunks` length before their respective copy loops.
- Keep original header ordering, payload-offset sorting, replacement mapping, gaps/trailing bytes, one-payload-allocation behavior, and MD5/header reconstruction unchanged.
- Add static structure checks and a runtime Proxy/getter-count regression proving one read per header offset/length and one read of the messageHead array length.

## Validation boundary
Existing BaiduMap binary fixture tests continue to cover zero through three Ads segments, payload ordering, offsets, malformed layouts, and MD5 correctness. The new checks measure property reads in a controlled Node fixture; they do not claim device-side CPU, battery, thermal, or latency gains.
