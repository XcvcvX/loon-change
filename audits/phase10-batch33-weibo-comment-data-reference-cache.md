# Phase 10 batch 33 — Weibo comment data reference cache

## Scope
Optimized the `/2/comments/build_comments` `datas` loop in `scripts/weibo/weibo-rstore.js`.

## Change
- Cache `item?.data` once per comment as `commentData`.
- Reuse the cached reference for the ad predicate, user/avatar cleanup, and four comment-field checks/deletions.
- Preserve the original truthiness gate, `isAd` call position, mutation order, user-name exclusions, item-type/adType filters, and stable in-place compaction.
- No new arrays, callbacks, or traversal passes are introduced.

## Safety
The change is limited to the existing `datas` branch. Root-comment and nested-comment branches remain unchanged. Runtime regression fixtures continue to cover ad removal, fake-comment exclusions, avatar cleanup, field deletion, and lazy serialization.

## Expected performance effect
Avoids repeated `item.data` property resolution within each processed comment. This is a narrow interpreter/property-access reduction; no device-level CPU, thermal, or battery measurement is claimed.

## Validation
The pull-request workflow runs the repository's complete Python and Node-backed regression suites, including optimizer idempotence and fail-closed structure-drift checks.
