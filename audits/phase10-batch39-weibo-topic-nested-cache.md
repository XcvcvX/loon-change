# Phase 10 batch 39 — Weibo nested hot-topic reference caching

## Change
- Cache each topic-group's nested `items` array once before branching, reusing it for the existing in-place top-group compaction and the nested-group traversal.
- Cache each nested item's `data` reference once and reuse it for avatar cleanup and `common_struct` removal.
- Cache `common_struct` once before its conditional deletion.
- Preserve group filtering, item order, hotword replacement, and all existing cleanup behavior.
- Extend the source optimizer with marker validation, idempotence, and fail-closed drift checks; add regression coverage for the generated structure.

## Performance rationale
- Avoids repeated nested property access in the high-frequency `/2/statuses/container_timeline_topic` response path.
- Avoids repeated `item.items` and `ii.data` access while traversing deep topic groups.
- Does not allocate replacement arrays or change traversal complexity.

## Validation
- Regression tests verify optimizer idempotence, required cached references, and fail-closed behavior if the transformed structure drifts.
- Existing topic-group runtime fixtures continue to cover stable ordering, allowlisted cards, and hotword replacement.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
