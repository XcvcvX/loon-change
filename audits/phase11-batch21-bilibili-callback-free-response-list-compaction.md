# Phase 11 batch 21 — Bilibili callback-free response list compaction

## Scope
- Runtime: `scripts/bilibili/bilibili-json.js`
- Regression coverage: `tests/test_bilibili_json_performance.py`
- Reproducible optimizer: `tools/optimize_bilibili.py`
- Active routes checked in `allAdRewrite.plugin`: Bilibili feed index, account tabs/profile, splash, PGC page, and live-room info

## Finding
The active Bilibili response handler used a generic predicate callback for seven array-cleanup call sites. Tab filtering also delegated ordering to callback-based filtering and sorting. The splash and PGC branches used `forEach`, while profile and splash branches created short-lived fixed-key arrays for simple operations.

## Change
- Replace generic per-item predicate callbacks with a mode-dispatched indexed compactor whose mode is resolved once per list.
- Specialize fixed allowlists as scalar comparisons, including feed cards, iPad navigation sections, PGC banner/function links, and live-room tabs.
- Replace tab filter/sort callback paths with stable in-place compaction and a short stable insertion pass using fixed rank comparisons. Preserve the original priority and duplicate order.
- Replace splash-field iteration with direct tracked deletions.
- Replace PGC module `forEach` and splash-list iterator traversal with indexed loops and cached array lengths.
- Keep same-index writes out of compaction and set array length only when a list actually shrinks.
- Preserve the existing `modified` tracking so unchanged response bodies still skip `JSON.stringify`.
- Add runtime regressions that disable `Array.filter`, `Array.forEach`, and `Array.sort` while exercising affected routes.

## Expected effect
Avoids per-response predicate closures and callback dispatch for the covered lists, removes a temporary sorting callback on tab reorder, and removes callback/iterator traversal from PGC and splash paths. It also avoids constructing fixed allowlist arrays in hot response branches. These are structural reductions; device-level impact depends on actual payload sizes and route frequency.

## Validation boundary
CI tests verify retained item sets, ordering, duplicate stability, mutations, no-op serialization behavior, and successful execution with array callback methods disabled. No iPhone CPU, battery, thermal, or end-to-end latency benchmark is claimed.
