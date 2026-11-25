# Phase 10 batch 49 — Weibo comment response array reference cache

## Scope
Optimized the active Weibo `/2/comments/build_comments` response route.

## Change
- Cache the `datas` array reference before testing it.
- Resolve `root_comments` and `comments` lazily in their respective `else if` branches, caching each checked reference once.
- Preserve the original branch priority and short-circuit behavior; later response arrays are not read when an earlier branch matches.
- Reuse each cached reference as the source array for the existing in-place cleanup loop.

## Regression coverage
- Optimizer marker, idempotence, and fail-closed structure validation.
- Runtime accessor counters for all four response shapes: `datas`, `root_comments`, `comments`, and `rootComment`-only.
- Existing comment decoration/accessor and response cleanup fixtures are retained.

## Performance note
Avoids a second top-level property access for the selected comment array while preserving branch semantics. No device CPU, battery, or latency measurements are claimed.
