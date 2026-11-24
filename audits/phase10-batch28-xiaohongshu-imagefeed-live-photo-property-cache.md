# Phase 10 batch 28 — Xiaohongshu imagefeed live-photo property cache

## Scope
During the existing single-pass imagefeed traversal, live-photo extraction repeatedly walked the same nested `live_photo.media.stream` chain and re-read the file ID and master URL.

## Change
- Cache the root image's `live_photo`, `media`, stream entry, file ID, video ID, and master URL in local references.
- Preserve the existing root-array-only extraction scope, truthy field requirements, cache record shape, traversal order, and image enhancement behavior.
- Add a fail-closed, idempotent optimizer transform and invariant coverage.

## Validation
Static optimizer regression verifies the cached references and rejects stale marker structure. Existing Node imagefeed fixtures continue to exercise compact-cache contents and the single root-array traversal. No device-level CPU, battery, thermal, or latency measurements are claimed.
