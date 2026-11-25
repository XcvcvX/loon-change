# Phase 10 batch 61 — Weibo profile and deep-comment hot-property caching

## Scope
- Active Weibo `/2/profile/container_timeline` profile-page response.
- Active Weibo `/2/comments/build_comments` comment response, including the shared per-item ad predicate used by deep comment and feed routes.

## Changes
- Cache the profile `items` array reference and length before the in-place compaction pass.
- Cache each profile item’s `data`, `category`, and repeatedly used data fields (`card_type`, `name`, `left_hint`).
- Cache group-card arrays and lengths, nested item `data` / `category`, and the nested card fields used by cleanup.
- Reuse the cached header/data and title/source references instead of repeating nested property chains.
- Refactor shared `isAd` to read `mblogtypename` once and cache nested promotion/content-auth/ad-material references, preserving the original predicate order and short-circuit semantics.
- Keep in-place compaction, filtering predicates, item ordering, and cleanup targets unchanged.

## Regression coverage
- Optimizer idempotence and fail-closed checks for the new profile transformation.
- Node runtime getter counters for profile arrays, lengths, group arrays, categories, data references, and nested card fields.
- Predicate fixtures cover all five existing ad-detection conditions.
- Deep-comment runtime getter counters verify one read for each shared ad-predicate nested reference.

## Validation boundary
- Static/runtime fixture tests exercise the script under Node; they do not constitute on-device Loon CPU, battery, thermal, or latency measurements.
- No device-side performance percentage is claimed.
- Other active large response paths (Didi, Baidu Map, Taobao, and Xiaohongshu) were reviewed against existing route-specific caches; this batch avoids adding another full traversal or speculative broad rewrite.
