# Didi wallet nested property access cache

## Scope

Optimize the `/usercenter/me` card-mode pass in the active Didi response script.

## Change

For wallet cards, cache `item.items` once before validating and compacting the nested coupon list. For type-4 wallet cards, cache `item.bottom_items` once before validating and compacting the nested bottom-item list. The bottom-items property is still accessed only when `card_type === 4`, preserving the previous short-circuit behavior.

This removes repeated reads of the same wallet-card properties without changing the allowlists, retained order, in-place compaction, or handling of non-array values.

## Validation

- Optimizer remains idempotent and fails closed if the cache declarations or expected helper shape drift.
- Runtime getter instrumentation asserts exactly one read each for `tag`, `items`, `card_type`, and `bottom_items` on a wallet card, while checking the resulting retained entries.
- Existing tests continue to cover non-array nested fields, route guards, lazy serialization, and all Didi filters.

## Limits

This is a small source-level reduction in per-card property reads. No device-level battery, thermal, or latency gain is claimed.
