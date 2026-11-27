# Phase 11 batch 15 — Xiaohongshu image traversal array classification cache

## Scope
- Runtime: `scripts/xiaohongshu/xiaohongshu-rstore.js`
- Reproducible optimizer: `tools/optimize_xiaohongshu_rstore.py`
- Regression coverage: `tests/test_xiaohongshu_rstore_performance.py`

## Finding
The active R-Store image-feed helper uses an iterative depth-first walk. Each loop iteration checked `Array.isArray(value)` again, even though the current traversal frame always refers to the same node. For a large array, that repeated classification occurred once per visited element.

## Change
- Classify the root node once and store the result on its traversal frame.
- Classify each nested child once when its frame is pushed.
- Branch on the cached `frame.isArray` flag during traversal rather than re-running `Array.isArray` for every element/property.
- Keep the existing cached array-length snapshot, object-key order, depth-first traversal, live-photo extraction boundary, URL rewrite rules, and in-place object mutation unchanged.
- Extend the upstream optimizer to upgrade the previous array-length-only helper and fail closed on stale or mixed structures.

## Expected effect
For array nodes, reduces `Array.isArray` from one call per traversed element to one call per frame. Object nodes are also classified only once when entered. This avoids repeated type checks on the main image traversal path without adding another pass, callback, or collection.

## Validation boundary
Existing Node runtime tests cover image URL rewrites, nested object traversal, top-level-only live-photo cache extraction, and response serialization. New structural tests verify classification is cached per frame and the optimizer remains idempotent/fail-closed. No iPhone CPU, battery, thermal, or latency benchmark is claimed.
