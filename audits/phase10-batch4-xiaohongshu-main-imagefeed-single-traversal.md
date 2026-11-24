# Phase 10 Batch 4 — Xiaohongshu main image-feed single traversal

## Change

The active local `scripts/xiaohongshu/xiaohongshu.js` response handler previously traversed the same root `images_list` twice:
1. A standalone loop extracted compact live-photo fields (`live_photo_file_id`, `video_id`, and the first H.265 `master_url`).
2. `imageEnhance` then performed an iterative depth-first walk over the root array and nested objects to rewrite image URLs.

The cache extraction now runs while the existing iterative image enhancement traversal reads each root-array item. The new optional cache argument is only populated for direct children of the root `images_list` array; nested objects remain eligible for URL enhancement but cannot become extra top-level live-photo cache records.

## Behavior safeguards

- Preserve the compact cache schema, exact truthy eligibility checks, first H.265 stream selection, and root array order.
- Preserve normal 2160-width/height rewriting and the `original` quality mode's single successful replacement.
- Preserve nested URL traversal, response object mutation, cache key, and save handler input.
- Keep the existing iterative traversal (no recursion, no second image-array loop) and do not add a JSON parse/stringify pass.
- Update the optimizer so both current marked sources and freshly synchronized upstream sources receive the fused helper; exact anchors and idempotence checks fail closed on source drift.

## Regression coverage

The Node VM harness instruments numeric reads of the root image array and excludes reads made during final JSON serialization. Tests cover one-item and multi-item feeds, nested live-photo-shaped objects, compact cache contents, and the original-quality replacement rule. The optimizer is tested for idempotence and refusal to accept a structurally damaged traversal.

## Scope and measurement

This removes one full top-level array scan from each qualifying image-feed response. It does not remove the existing iterative nested URL traversal or the final response serialization. No iPhone battery, CPU, memory, temperature, or latency percentage is claimed; device-level measurement would still be needed.
