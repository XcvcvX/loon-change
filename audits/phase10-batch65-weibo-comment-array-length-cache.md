# Phase 10 · Batch 65 — Weibo comment top-level array length cache

## Scope
Active `/2/comments/build_comments` response branch, covering the mutually exclusive `datas`, `root_comments`, and `comments` top-level arrays.

## Finding
Each selected comment array had its length read once for branch selection and again when initializing the indexed compaction loop. The root/reply branches also read their source array length a second time after the condition succeeded.

## Change
- Cache the `datas` array length before selecting the primary branch and reuse it as the loop bound.
- Cache `root_comments` and `comments` lengths in their respective `else if` conditions, then reuse those values as loop bounds.
- Preserve branch precedence (`datas`, then `root_comments`, then `comments`), in-place compaction, item order, and existing comment cleanup predicates.
- Keep branch-specific reads lazy: fallback arrays are not read when the higher-priority `datas` branch is non-empty.

## Runtime verification
Node.js Proxy tests count array `length` getter accesses for all three branches and for an empty-`datas` fallback into `root_comments`. Each evaluated array length is read once, and the same comment decorations are removed.

## Validation boundary
This is a structural property-access reduction. It does not claim measured iPhone CPU, battery, latency, or thermal gains.
