# Phase 10 batch 35 — Xiaohongshu flat comment traversal frames

## Scope
Continue the high-frequency comment-tree allocation audit after the prior traversal, media-cache, and array-classification optimizations.

## Change
- Replace each three-element comment metadata tuple `[commentFrameTag, node, isTopLevel]` with three adjacent entries on the existing iterative traversal stack.
- Pop the boolean metadata slot, verify the preceding sentinel, then recover the comment node. Ordinary object nodes remain distinguishable because the traversal only pushes object references as ordinary entries.
- Preserve the LIFO order, top-level/direct-sub-comment classification, depth-first traversal, red_id cleanup, comment type normalization, picture/video extraction, and video-info Map cache.
- Update the upstream optimizer so every source refresh regenerates the flat-frame implementation; the optimizer remains idempotent and fails closed on structural drift.

## Validation
- Existing Node VM comment-tree fixtures continue to cover nested comments, media extraction, normalization, and cache reuse.
- Static regression checks require flat stack slots and forbid tuple-array frame pushes and the previous Array.isArray frame classifier.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.

## Allocation effect
Removes one temporary three-element array allocation for each top-level comment and direct sub-comment frame. It does not remove the traversal stack itself or the live-photo output/cache allocations.
