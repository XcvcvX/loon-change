# Phase 10 batch 60 — Weibo/Xiaohongshu composed cache validation and duplicate traversal

## Weibo optimizer stability
- Scope comment-user cache validation to the exact block between the comment-user marker and the comment-decoration marker. This prevents unrelated same-named variables in other response routes from masking a damaged optimized block.
- Keep the comment-data optimizer valid in its intentional intermediate state, before the later comment-user reference transform runs.
- Remap lazy-serialization delete tracking for cached reply-user/reply-comment fields and the cached root-comment bubble.
- Keep strict validation for the cached avatar-user field and all expected helper references.
- Fix route-marker postcondition order and route-scoped optimizer assertions from the preceding batch.

## Xiaohongshu comment traversal
- Cache each comment's pictures array and length once for video extraction.
- Avoid enqueueing the same pictures array into the generic JSON-tree traversal after processing it in the cached-length pass.
- Strip the direct `red_id` property from each picture object in that pass, preserving the relevant cleanup while avoiding a second array-length/index walk.
- Keep recursive traversal of other response children unchanged.

## Regression coverage
- Weibo optimizer tests cover the comment-user marker's local fail-closed block, intermediate comment-data state, cached root-comment fields, and marker-before-postcondition order.
- Weibo runtime tests use getter/proxy counters for nested arrays and feed properties.
- Xiaohongshu runtime tests assert one pictures reference/length/index pass per processed comment and retain live-photo cache output.
- V4 video-feed tests check single reads for H.265 candidate URL/height and array length.

## Validation
- The latest full workflow runs 655 tests. Earlier iterations narrowed failures from 10 to 1; the latest remaining issue was isolated to the scope of a negative test fixture and is now fixed.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
