# Phase 10 batch 48 — Xiaohongshu comment traversal array-length caching

## Scope
Optimized the active R-Store Xiaohongshu comment-response cleanup/media extraction helper used by the plugin's `note/comment/list` and `note/comment/sub_comments` response routes.

## Change
- Cache each processed comment's picture-array length once and use an indexed loop rather than the iterator protocol.
- Cache the current node array length once during iterative JSON-tree traversal.
- Cache top-level comment and direct sub-comment array lengths before reverse stack pushes.
- Preserve reverse push order, stack-frame representation, and processing boundaries (only top-level comments and their direct sub-comments are treated as comment frames).

## Regression coverage
- Optimizer marker, required anchors, idempotent regeneration checks, and fail-closed validation.
- Runtime getter/proxy assertions: picture references remain one read per processed comment; each picture array length is read once and each indexed picture is visited once.
- Existing deep-tree and comment media extraction fixtures remain in the suite.

## Performance note
This removes per-picture iterator work and repeated array-length reads in the active comment-media path. No device-level CPU, battery, or latency measurements are claimed.
