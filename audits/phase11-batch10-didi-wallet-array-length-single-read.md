# Phase 11 batch 10 — Didi wallet array length single-read

## Finding
The wallet-card compactor checked `walletItems.length > 0` and `walletBottomItems.length > 0` before calling `compactDidiByField`. The compactor itself reads the array length once to bound its in-place loop, so each non-empty wallet array incurred a duplicate length read. Empty arrays also needed no special pre-check.

## Change
- Keep the cached wallet-array references.
- Call the specialized in-place compactor for any actual array, including empty arrays; its zero-length loop is a no-op.
- Upgrade the wallet cache marker to v2 and make the optimizer migrate the prior v1 form idempotently and fail closed on drift.
- Add a Node Proxy-based runtime regression that counts array `length` reads for both a non-empty wallet array and an empty bottom-items array.
- Extend runtime invariants to forbid the redundant `walletItems.length` and `walletBottomItems.length` checks.

## Expected effect
Each wallet array's length is read once by the compactor instead of once in the pre-check plus once in the compactor. No array traversal is added or removed for non-empty arrays; empty arrays enter a zero-iteration helper path.

## Validation limits
Tests measure property-access counts and preserved filtering results, not iPhone CPU time, battery consumption, temperature, or latency. No device benchmark is claimed.
