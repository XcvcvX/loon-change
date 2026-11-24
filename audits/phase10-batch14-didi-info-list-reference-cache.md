# Didi info-list nested reference cache

## Scope

Reduce repeated nested property-chain reads in the supported Didi OTA info-list response branch.

## Change

Cache the top-banner data array and its first item once, then reuse those references for the banner predicate and removal. The existing first-item-only removal condition and array splice behavior remain unchanged. Optional chaining preserves the prior no-op behavior when intermediate response fields are absent.

## Validation

- A focused source test asserts both cached references are used and the repeated nested chain is absent from the branch.
- The existing runtime regression test continues to verify that the target banner is removed while following entries remain in order.
- The Didi optimizer applies the transformation idempotently and fails closed if the expected source block drifts.
- Repository optimization invariants require the cache marker and forbid the previous repeated access.

## Limits

This removes repeated nested property reads on the OTA info-list branch only. It does not change response parsing, array allocation, or binary payload handling. No device-level battery, thermal, or latency measurements are claimed.
