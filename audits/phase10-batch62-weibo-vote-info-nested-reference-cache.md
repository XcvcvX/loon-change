# Phase 10 Batch 62 — Weibo vote-info nested reference cache

## Scope
Reduce repeated nested property traversal in the shared `removeVoteInfo` helper. This helper is called from Weibo comment responses and active feed/container paths, including nested cards.

## Change
Cache `item.page_info`, `page_info.media_info`, and `media_info.vote_info` once, then use the cached `mediaInfo` reference for deletion. The existing truthiness condition and deletion behavior are preserved.

## Safety
- No response fields or filtering criteria are changed.
- Missing/null intermediate objects remain safe through optional chaining.
- The optimizer is marker-guarded, idempotent, and fails closed if the upstream helper shape drifts.
- Regression tests cover the transformation, idempotence, fail-closed behavior, and generated-script structure.

## Expected effect
Avoid repeated reads of the nested `page_info -> media_info -> vote_info` chain on the helper's active path. This is a structural optimization; no device-side CPU, energy, or latency measurements are claimed.
