# Phase 11 · Batch 12 — Weibo /2/page array reference and length cache

## Scope

Optimized the Weibo `/2/page` response branch in `scripts/weibo/weibo-rstore.js`.

## Changes

- Cache the outer `obj.cards` reference and its length once.
- Cache the first card and its `card_group` reference/length once.
- Cache the topic-page `obj.card_group` reference/length once on the existing fallback branch.
- Extend the existing in-place compactor with an optional known-length argument. Other call sites retain the original one-read fallback; the /2/page branch passes its already-read snapshot so compaction does not read array length again.
- Preserve the existing non-empty cards versus topic-card fallback condition, filtering modes, stable order, and lazy response serialization.
- Extend the optimizer, idempotence/drift tests, runtime getter instrumentation, and invariant manifest.

## Structural evidence

For the populated cards branch, `obj.cards` and the first card's `card_group` are each fetched once; each array length is read once and passed to the compactor. The topic fallback likewise reads its group reference and length once. Proxy-based Node VM tests instrument these accesses and validate output preservation.

This is deterministic property-access evidence, not an iPhone device benchmark or a measured battery/thermal percentage.
