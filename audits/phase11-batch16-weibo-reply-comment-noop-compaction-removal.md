# Phase 11 batch 16 — Weibo reply-comment no-op array compaction removal

## Scope
- Runtime: `scripts/weibo/weibo-rstore.js`
- Reproducible optimizer: `tools/optimize_weibo_rstore.py`
- Regression coverage: `tests/test_weibo_rstore_performance.py`

## Finding
In the `/2/comments/build_comments` fallback branch that processes `obj.comments`, every reply-comment item is retained. The loop only removes nested user icons and reply badges; it does not filter or reorder the top-level array. The previous implementation nevertheless wrote every item back to the same array index, advanced a write cursor, and reassigned the original array length.

## Change
- Keep the cached `replyComments` reference and the existing `replyCommentsLength` snapshot.
- Iterate the original array by index and retain the existing nested property cleanup.
- Remove the unnecessary same-index array writes, write cursor, and final length assignment.
- Keep object cleanup, item order, array identity, branch precedence, and lazy response serialization unchanged.
- Add an optimizer marker with idempotent structure checks and fail-closed handling; add the marker to the runtime invariant manifest.

## Expected effect
The reply-comment traversal still performs one read per item and the same nested property checks/deletions, but no longer performs one redundant array-element write per item or a final length write. The reduction is linear in the number of reply comments. No additional pass, collection, callback, or clone is introduced.

## Validation boundary
A Node regression test proxies the reply-comment array and verifies that cleanup preserves all entries and order while issuing zero indexed writes and zero length writes to that array. Optimizer tests verify idempotence and fail-closed behavior. This is a structural runtime-operation reduction; no iPhone CPU, battery, thermal, or latency benchmark is claimed.
