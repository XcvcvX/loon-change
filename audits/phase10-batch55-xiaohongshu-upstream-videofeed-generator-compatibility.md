# Phase 10 batch 55 — Xiaohongshu upstream video-feed generator compatibility

## Problem
The sync workflow fetched the current R-Store source and failed while regenerating the Xiaohongshu response script. The V4 hot-path optimizer had already replaced the upstream filter/sort H.265 selection with a single-pass URL/height scan, but a later legacy `sort_old` rewrite still required the removed source anchor and raised `video stream sort anchor drift`.

## Fix
- Remove the redundant legacy H.265 sort rewrite; V3/V4 video-feed hot-path transformation now owns the single-pass H.265 selection.
- Update generated-source invariants to require the new `selectedStreamUrl` accumulator.
- Keep the no-`.filter().sort()` postcondition to protect the low-allocation path.

## Regression coverage
- Add an upstream-shaped V3/V4 fixture containing the original iterator, `some()`, H.265 `filter().sort()`, and selected-stream form.
- Verify the video-feed optimizer converts this raw shape, preserves V3/V4 markers and cached fields, removes `some()` and `filter().sort()`, and is idempotent on the result.

## Validation
- Re-run the repository sync workflow after merge to confirm upstream regeneration can proceed.
