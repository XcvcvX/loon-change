# Phase 10 batch 52 — Xiaohongshu V3/V4 video-feed reference cache

## Scope
Optimized the active Xiaohongshu `/note/videofeed` V3 and V4 response paths.

## Change
- Cache each version's top-level `data` array reference and length before iteration; use indexed traversal.
- V3 caches the per-item media-save config, share-info object, and function-entry array before mutating them. The existing first-entry check and prepend behavior are preserved.
- V4 caches the video-info/media/stream path, reads each H.265 candidate's URL and height once, caches the selected URL, and reuses the note ID once when emitting the download cache record.
- Preserve first-stream-on-height-ties behavior and the existing filtering/selection semantics.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed structure checks.
- V3 accessor-count fixture verifies one read for data length, media-save config, share-info, and function-entry array, plus unchanged flags/button result.
- Existing V4 function-entry and stream-selection fixtures remain.

## Performance note
Reduces per-item nested property reads and array iterator overhead in both active video-feed versions. No device-level CPU, battery, or latency measurements are claimed.
