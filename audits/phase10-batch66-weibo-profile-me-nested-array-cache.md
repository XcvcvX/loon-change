# Phase 10 · Batch 66 — Weibo profile/me nested array cache

## Scope
Active `/2/profile/me` response branch: the top-level profile card list, the `profileme_mine` detail list, and the `100505_-_top8` shortcut list.

## Finding
The top-level list was read through `obj.items` for its length check, source reference, and loop bound. Both nested branches also re-read `item.items` after checking its length. The friends shortcut used `for...of`, while the top-8 list called the shared compactor, which re-read the length after its guard.

## Change
- Cache the top-level `obj.items` reference and array length once; reuse them as the in-place compaction source and loop bound.
- Cache each selected nested `item.items` reference and length once.
- Replace the friends-list iterator with a bounded indexed traversal.
- Inline the top-8 in-place compaction using the cached length; preserve the exact four-item allowlist, retained item order, and `modified` behavior.
- Keep the branches lazy: nested arrays are read only for their corresponding card IDs.

## Runtime verification
Node.js Proxy regression tests count top-level and nested array-reference/length reads. Each relevant array reference and length is read once. Fixtures also verify the friends scheme rewrite, top-8 allowlist, and top-level card retention order.

## Validation boundary
This is a structural property-access and traversal-bound reduction. It does not claim measured iPhone CPU, battery, response latency, or thermal gains.
