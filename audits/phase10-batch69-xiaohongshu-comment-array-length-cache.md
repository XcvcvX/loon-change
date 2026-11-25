# Xiaohongshu comment-tree array length cache

## Scope
- Runtime: `scripts/xiaohongshu/xiaohongshu.js`
- Hot path: `processCommentTree(data, livePhotos, commentVideos, noteId)`

## Change
Cache the array length once before reverse traversal for:
- Generic array nodes reached by the iterative comment-tree stack
- The root `comments` list
- Each top-level comment's `sub_comments` list

The loops now compare their cursor against a local scalar instead of repeatedly reading `.length` on every iteration.

## Behavior and safety
- Preserve reverse push order and the resulting depth-first processing order.
- Preserve comment classification, red-id cleanup, nested comment handling, and media extraction.
- The traversal does not mutate the arrays being enumerated, so taking the length snapshot before each loop preserves its original iteration boundary.
- Optimizer is idempotent and fails closed if the comment traversal anchors drift.

## Verification
- Static checks assert each loop uses the cached bound and reject the previous repeated-read loop forms.
- Node runtime Proxy tests instrument the root comments array, sub-comments array, and a generic nested traversal array, asserting one length getter read per traversal while checking transformed output.

This is a structural reduction in repeated property reads. No device-side CPU, battery, thermal, or frame-time benchmark is claimed.
