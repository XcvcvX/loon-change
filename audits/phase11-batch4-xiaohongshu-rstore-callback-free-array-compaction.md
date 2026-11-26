# Phase 11 batch 4 — Xiaohongshu R-Store callback-free response-array compaction

## Scope
- Active runtime: `scripts/xiaohongshu/xiaohongshu-rstore.js`
- Active plugin coverage: 10 response trigger entries in `allAdRewrite.plugin`
- Reproducible upstream regeneration: `tools/optimize_xiaohongshu_rstore.py`

## Finding
The active handler used one generic `compactInPlace(items, keep)` helper. Each call created a predicate closure and invoked it once per array element. The image-feed route called this helper for every note's hashtag array, so closure creation scaled with the number of notes in a matching response. The same callback pattern also handled followings, follow-list, home-feed, search-result, and live-photo deduplication paths.

## Change
- Replace predicate callbacks with mode-dispatched in-place loops; the mode is selected once before traversal and each loop evaluates its filter condition directly.
- Cover hashtag removal, friend-post allowlisting, recommended-user removal, note-only search results, home-feed ad-card filtering, and live-photo deduplication.
- Preserve stable ordering, retained object identity, null-item handling, the home-feed `related_ques` deletion, and the existing deduplication order.
- Read each live-photo `videId` once during deduplication and incoming append.
- Do not allocate replacement filtered arrays, predicate closures, or per-item callback invocations.
- Add an idempotent, fail-closed optimizer transform and Node runtime coverage for every response filter mode.

## Expected structural effect
Eliminates predicate-function creation and indirect per-element callback calls on the reviewed routes. In image-feed responses, the removed hashtag predicate closure was created once per note with a hash-tag array. The helper also avoids writing the array length when no item was removed.

## Safety and measurement boundary
No response trigger, script URL, `requires_body` flag, MITM hostname, response field condition, allowlist, or mutation intent was changed. Runtime fixtures assert stable output and preserved null-item behavior. This is a structural allocation/call-overhead reduction; no real-device CPU, battery, temperature, or response-latency improvement is claimed without iPhone measurements.
