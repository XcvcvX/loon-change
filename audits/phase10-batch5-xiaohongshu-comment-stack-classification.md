# Phase 10 Batch 5 — Xiaohongshu comment classification without WeakSets

## Change

Both local Xiaohongshu response handlers previously pre-scanned the top-level comments and allocated two `WeakSet` instances to mark top-level comments and comment nodes. The later iterative tree walk queried those sets for every visited object and discovered direct sub-comments during the same walk.

The handlers now carry comment classification only on the DFS stack entries for top-level comments and their direct sub-comments. Ordinary response nodes remain plain object references. This removes the classification pre-scan and both per-response `WeakSet` allocations while retaining the same iterative traversal for `red_id` cleanup.

## Behavior safeguards

- Only objects in `data.comments` and their direct `sub_comments` are classified as comment nodes, matching the previous one-level membership rules.
- Only top-level comments extract the primary script's `videos` list; top-level comments and direct sub-comments continue to process `pictures`.
- Deeper nested `sub_comments` are traversed for ordinary cleanup but are not reclassified as comment nodes.
- The R-Store handler retains its existing top-level/direct-sub-comment cleanup scope and H.265 video-info cache behavior.
- The shared DFS remains iterative; it does not add recursion, JSON parsing, serialization, or full-tree marker properties.

## Regression coverage

The Node VM tests count runtime `WeakSet` construction and now require zero instances for these comment requests. They also verify that top-level and direct sub-comments retain their original transformations, deeper sub-comments remain outside the comment-specific transformation scope, cached media IDs and URLs remain unchanged, and deep generic objects are still processed iteratively. Both source optimizers and the invariant manifest are updated to preserve the change after upstream synchronization.

## Pinduoduo audit note

The active plugin snapshot exposes Pinduoduo request-rejection rules for splash, popup, search-hot-query, and selected activity endpoints, but no corresponding Pinduoduo homepage response-body `jq(map(select(...)))` handler to safely fuse or rewrite in this batch. The existing order cleanup consolidation remains in place. No speculative response transformation was introduced without a live matching rule or response fixture.

## Scope and measurement

This removes a preliminary comment-classification scan and two `WeakSet` instances per matching comment response. Comment node wrapper frames are created only for top-level comments and their direct sub-comments, not for every traversed object. No iPhone CPU, memory, battery, temperature, or latency percentage is claimed; device-level profiling would still be needed.
