# Phase 10 · Batch 63 — Weibo comment status page-info reference cache

## Scope
Optimize the `/2/comments/build_comments` status-level vote-info cleanup path.

## Finding
The comment response branch read `obj.status` once to test `page_info`, then read `obj.status` again when invoking `removeVoteInfo`. The helper then re-read `status.page_info`, even though the branch had already obtained that reference.

## Change
- Cache `obj.status` and its `page_info` reference once in the comment response branch.
- Allow the shared vote-info helper to accept an explicitly cached page-info reference; existing one-argument callers retain their original lookup behavior.
- Preserve the original truthiness gate, nested `media_info.vote_info` condition, deletion target, and modified flag behavior.
- Add optimizer marker validation, idempotence and fail-closed checks, plus getter-count regression coverage.

## Validation
The focused regression verifies one read each for `obj.status` and `status.page_info`, and confirms the same vote-info field is removed. Full repository CI remains the merge gate.

## Performance note
This removes two repeated property reads on the comment response's status branch. No device-side CPU, latency, battery, or thermal measurements are available; no real-device performance gain is claimed.
