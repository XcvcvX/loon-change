# Phase 10 · Batch 67 — Weibo profile statuses-tab array and mblog cache

## Scope
Active `/2/profile/statuses/tab` response branch for personal-profile status lists.

## Finding
The top-level `cards` array was read for the guard, source reference, and loop-bound length. Each card's `card_group` array had the same repeated-reference/length pattern. Group and non-group cards also read their `mblog` reference once for the condition and again for each cleanup helper.

## Change
- Cache the top-level cards reference and length once and reuse them for the in-place compaction loop.
- Cache each card's group-array reference and length once, preserving the existing non-empty-group versus card-level fallback behavior.
- Cache each selected group/card `mblog` reference and pass it to both cleanup helpers.
- Preserve removal of `card_type === 22`, in-place compaction, ordering, avatar cleanup, vote cleanup, and the page-type-08 hot-search cleanup.

## Runtime verification
Node.js Proxy tests count cards/card-group references and lengths, as well as group/card mblog getter reads. Each relevant read occurs once. Fixtures verify group filtering and avatar/vote cleanup in both nested-group and card-level paths.

## Validation boundary
This proves reduced repeated property/length reads structurally. It does not claim measured iPhone CPU, battery, latency, or thermal gains.
