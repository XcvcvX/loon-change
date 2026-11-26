# Phase 11 batch 9 — Taobao splash media property single-read cache

## Finding
For each splash item with non-empty `imgUrl` or `videoUrl`, the normalizer previously read the property once in its truthiness check and again before assigning the empty string.

## Change
- Cache `imgUrl` and `videoUrl` once per item.
- Preserve the existing truthiness conditions and only clear non-empty values.
- Add a reproducible, idempotent optimizer and mirrored runtime invariants.
- Add a Node VM getter-count regression proving one getter read per populated media field and verifying both fields are still cleared.

## Expected effect
For splash items where both media URLs are populated, this removes two redundant property reads per item. It does not reduce the number of items traversed, JSON parsing, or serialization.

## Validation limits
The regression test measures property getter reads, not CPU time, battery, device temperature, or latency. No iPhone device benchmark is claimed.
