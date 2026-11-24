# Phase 10 batch 31 — Xiaohongshu flat comment stack frames

## Scope
The comment-tree traversal tagged top-level comments and direct sub-comments by allocating a three-element array for every tagged comment. Large comment responses can contain many such entries, creating avoidable short-lived arrays in the traversal hot path.

## Change
- Encode comment-frame metadata directly in the existing traversal stack as three adjacent stack values instead of allocating a tuple array per comment.
- Use the unique per-invocation `commentFrameTag` object as the frame discriminator.
- Preserve LIFO traversal order, top-level versus direct-sub-comment classification, and all existing cleanup and media extraction behavior.
- Keep ordinary tree nodes as plain references; no WeakSet or object-key materialization is introduced.

## Validation
- Added optimizer idempotence and fail-closed drift checks.
- Existing Node runtime fixture exercises top-level comments, direct sub-comments, deeper nested objects, media extraction, cache reuse, and type normalization.
- Added static assertions that the per-comment tuple allocations are absent.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
