# Phase 11 batch 18 — Amap Rucu6 callback-free compaction

## Scope

Optimize the active Romeo-derived Rucu6 Amap response runtime at `sources/amap/rucu6_amap.js`. This asset is distinct from the R-Store-based `scripts/amap/amap.js` runtime and is regenerated from the pinned Romeo asset during the production build before local patches are applied.

## Change

- Replace all 11 callback-based `compactInPlace(items, predicate)` callsites with eight mode-specialized direct loops: `withoutSchema`, `homeCards`, `findCar`, `dynamicAds`, `nonMusic`, `myOrder`, `nearbyModules`, and `searchContent`.
- Move mode dispatch outside each per-item loop so the hot loop no longer invokes a predicate callback for every element.
- Cache the target array length once per compaction, skip writes when the retained item is already in its final position, and update `length` only when the array actually shrinks.
- Preserve every original allowlist/denylist predicate, stable retained-item order, in-place mutation, route selection, and response serialization behavior. In particular, the `withoutSchema` path continues to preserve falsy entries and entries without an own `schema` property.
- Add a reproducible optimizer after the existing Romeo runtime patch in the production workflow. The optimizer validates callsite inventories, is idempotent, and fails closed when the expected upstream-patched structure changes.

## Validation

- Node VM runtime fixtures cover all eight modes and verify retained values/order.
- Runtime tests disable `Array.prototype.filter`, `map`, and `forEach` during target-script execution, ensuring the changed path does not regress to allocating array helpers.
- A Proxy-based regression verifies a single array-length read and a single length write only when compaction is required.
- The optimizer has regeneration, idempotence, and fail-closed structural tests; optimization invariants protect the generated runtime from upstream overwrite.
- The PR build also runs the full repository test suite and production synchronization preflight.

## Structural cost effect

The 11 callback callsites no longer construct predicate callbacks or dispatch a callback for each visited element. Each specialized compaction snapshots `length` once rather than re-reading it as the loop condition, avoids same-index array assignments, and avoids a redundant length assignment when no elements are removed. These are source-level reductions; no device-level CPU, battery, thermal, memory, or latency improvement is claimed without iPhone measurements.
