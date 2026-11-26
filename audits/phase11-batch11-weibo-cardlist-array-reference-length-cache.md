# Phase 11 · Batch 11 — Weibo cardlist array reference and length cache

## Scope

Optimized the high-frequency `/2/cardlist` response branch in `scripts/weibo/weibo-rstore.js`.

## Changes

- Cache `obj.cards` once as `cardlistCards`; cache its length once as `cardlistCardsLength`.
- Cache each `card.card_group` reference once as `cardGroup`; cache its length once as `cardGroupLength`.
- Reuse these snapshots for the existing in-place stable compaction loops.
- Keep card-type filtering, avatar cleanup, array ordering, mutation tracking, and lazy serialization unchanged.
- The optimizer is idempotent and fails closed if the route block or required cache structure drifts.

## Structural operation counts

For each processed non-empty `/2/cardlist` response, the outer array now performs one reference read and one length read instead of two of each. Each card with a group performs the same reduction for its nested `card_group` array. This removes up to two repeated property reads per array level, without allocating replacement arrays.

These are source-level/property-access counts, not device benchmark results. No claim is made about a measured CPU, battery, or thermal percentage.

## Validation

- Optimizer idempotence and drift guard.
- Node VM Proxy instrumentation checks exactly one reference and one `length` getter read for each array.
- Runtime fixture confirms an unchanged cardlist still returns an empty result without JSON serialization.
- Existing filtering/order and response-serialization tests remain part of the repository suite.
- `optimization_invariants.json` tracks the required markers and rejects the prior duplicate-read patterns.
