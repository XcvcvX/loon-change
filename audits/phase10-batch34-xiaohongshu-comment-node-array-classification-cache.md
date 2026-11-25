# Phase 10 batch 34 — Xiaohongshu comment node array classification cache

## Scope
In `processCommentTree`, each traversed object node called `Array.isArray(current)` once to decide whether to process object properties and then called it again to decide whether to traverse array elements.

## Change
- Cache the classification once in `currentIsArray` for each visited node.
- Reuse the boolean in both object-property and array-element branches.
- Preserve traversal order, stack push order, comment-frame handling, property enumeration, and media extraction.
- No additional arrays, callbacks, or traversal passes are introduced.

## Expected performance effect
Removes one redundant `Array.isArray` call per visited node in the comment-tree traversal. The benefit scales with the number of nodes visited; no device-level CPU, battery, thermal, or latency measurements are claimed.

## Validation
- Optimizer checks exact anchors, idempotence, and fail-closed structure drift.
- Static regression test confirms one classification call and one cached branch.
- Existing Node comment-tree fixtures continue to validate cleanup, comment classification, nested comments, and media extraction.
