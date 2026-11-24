# Phase 10 batch 29 — Xiaohongshu comment media property cache

## Scope
The comment-tree processor visits nested comment records and inspects each comment's picture list, plus the top-level comment's video list. The hot path previously re-read collection properties in the array guard and loop, and re-read each media item's identifier or serialized video-info field when constructing extracted records.

## Change
- Cache each comment's `pictures` collection once before the array check and traversal.
- Cache `videos` only for top-level comments, preserving the original top-level-only processing gate.
- Cache each picture/video identifier and serialized video-info string once, then reuse those values for validation, parsing, and output.
- Preserve comment traversal order, top-level/sub-comment distinction, video-info parsing cache, stream selection, and extracted record shapes.

## Validation
- Added optimizer idempotence and fail-closed drift checks.
- Existing Node comment-tree runtime fixture continues to cover nested comments, picture extraction, video extraction, and comment type normalization.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
