# Phase 10 batch 44 — Xiaohongshu comment and V4 video hot paths

## Change
- Cache the active comment's `pictures` array once and reuse that exact reference during the generic tree walk instead of reading the property again.
- Cache each picture's video ID locally before the live-photo extraction check and cache append.
- Preserve the comment frame rules: only top-level comments and their direct sub-comments receive media processing; the existing iterative tree walk and nested cleanup behavior remain.
- Replace the V4 video-feed per-item `.some()` callback with a bounded indexed scan.
- Cache the V4 item's `share_info` and `function_entries` references once and retain early exit as soon as an existing download action is found.
- Add reproducible optimizer checks and getter-/runtime-based regressions.

## Performance rationale
- Avoids a repeated `current.pictures` lookup between media extraction and generic traversal.
- Removes a per-item callback invocation from the V4 video-feed hot loop and avoids re-reading the share-info/entries chain.
- Does not add a map, set, closure, or temporary array.

## Validation
- Comment fixture tracks the pictures accessor and expects one read for each processed comment.
- V4 fixture disables `Array.prototype.some` and checks both existing and missing download action cases.
- Existing single-pass H.265 selection, highest-height behavior, comment media extraction, and stable response semantics remain covered.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
