# Phase 10 · Batch 67 — Xiaohongshu image traversal array-frame length cache

## Scope
The active R-Store Xiaohongshu image-enhancement traversal in `scripts/xiaohongshu/xiaohongshu-rstore.js`.

## Finding
The iterative traversal cached object keys per frame, but its array branch re-read `value.length` on every loop iteration. Large image-feed arrays therefore repeated the same stable array-length property access for each item.

## Change
- Cache the root array length when creating the initial traversal frame.
- Cache each child array length when its frame is pushed.
- Use the frame-local length for the array termination check.
- Keep object-key snapshots, traversal order, image URL replacement, top-level live-photo extraction, and in-place mutation unchanged.
- Extend the optimizer's marked-source upgrade path with idempotent structure checks.
- Add runtime Proxy getter-count assertions for the image array length on one-item and multi-item fixtures.

## Validation boundary
The Node fixture verifies one root image-array length read independent of item count. It does not measure device-side CPU, battery, thermal, or response-latency changes.
