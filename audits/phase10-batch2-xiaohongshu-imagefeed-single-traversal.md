# Phase 10 Batch 2 — Xiaohongshu image-feed single traversal

## Change

The active R-Store Xiaohongshu response handler previously walked the top-level `images_list` twice:

1. A first loop extracted `live_photo_file_id`, `video_id`, and the first H.265 `master_url` into the compact save cache.
2. `imageEnhance` then traversed the same array and nested image objects to rewrite image-quality URLs.

The cache extraction now runs when the existing iterative image-enhancement traversal visits each top-level image. Nested objects continue through the same traversal for image URL enhancement, but are not treated as additional top-level live-photo records.

## Behavior safeguards

- Keep the same cache record fields and top-level eligibility check (`live_photo_file_id`).
- Preserve top-level array order and the original quality-mode behavior, including the single `originalDone` replacement.
- Preserve the existing image mutation and the compact persistent cache consumed by the live-photo save route.
- No route matcher, script trigger, cache key, JSON parse count, or response serialization behavior is changed.
- The optimizer applies exact anchors, validates the marker, checks for the absence of the old standalone loop, and remains idempotent.

## Regression coverage

The Node VM test harness wraps the image-feed root array and counts numeric index reads during runtime processing, excluding JSON serialization reads. Fixtures assert one root-array access per top-level image, retained image enhancements, preserved live-photo cache records, and exclusion of nested objects that happen to contain similarly named fields.

## Cross-rule audit follow-up

- Pinduoduo home, personal-center, and order response handlers remain distinct by endpoint and/or query scope; no extra response transform was proven redundant.
- Similar Pinduoduo request-stage rules with different actions or match scopes remain untouched.
- The current combined plugin still has no clearly attributed app-specific Douyin response handler. The observed ByteDance SDK response trigger points to a generic script whose route logic is for Tencent News; no Douyin response transformation was added without a confirmed Douyin URL/body fixture.
- Amap and Baidu Map paths reviewed in Batch 1 retain their already optimized fast paths; no additional safe, measurable source-level candidate was justified.

## Validation boundary

The runtime test demonstrates fewer root-array reads in the controlled fixture; it does not provide an iPhone CPU, energy, latency, or memory percentage. Real-device verification is still needed for such measurements.
