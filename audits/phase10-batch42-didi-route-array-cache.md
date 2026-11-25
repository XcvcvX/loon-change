# Phase 10 batch 42 — Didi route array reference caching

## Change
- Cache `scene_list` and `show_data` once before their scene-list processing branches.
- Reuse the cached `show_data` array for the existing indexed nested traversal.
- Cache the user-center `cards` array once before in-place card compaction.
- Preserve route selection, list predicates, stable ordering, and lazy serialization.
- Extend the optimizer with idempotent and fail-closed transformation checks and add regression coverage.

## Performance rationale
- Removes repeated reads of `responseData.scene_list`, `responseData.show_data`, and `responseData.cards` in supported high-frequency Didi responses.
- Does not allocate new arrays or alter the traversal algorithm.

## Validation
- Existing runtime fixtures cover scene-list and user-center filtering.
- Added source-level optimizer idempotence and fail-closed assertions, plus a scene-list behavior regression.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
