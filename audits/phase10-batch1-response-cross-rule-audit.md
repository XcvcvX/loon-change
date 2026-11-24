# Phase 10 Batch 1 — high-frequency response cross-rule audit

## Scope

Read the current `main` plugin and repository-owned response handlers for Taobao, Pinduoduo, Xiaohongshu, Amap, and Baidu Map. The audit distinguishes response-phase transformations from request-phase rejects and treats route similarity as insufficient evidence of duplicate processing.

## Taobao

- Existing PRs #459 and #460 already removed the extra Kelee response handlers, classified cloud-video/splash/Poplayer routes once, and reduced splash traversal allocations.
- This batch caches the cloud-video `data` reference once and the Poplayer `res`, `mainRes`, and `enable` values once. The existing mutation helpers, truthiness checks, array clearing, and lazy serialization remain unchanged.
- No additional parse/stringify pass is introduced. The optimizer has exact source anchors, idempotence checks, and fail-closed drift checks.

## Pinduoduo

- Home response cleanup is isolated to `/api/alexa/homepage/hub`.
- Personal-center response cleanup is split between the no-query `/api/philo/personal/hub` route and the query-bearing variant. Their URL matchers are disjoint; they are not two transformations of the same response.
- Order-detail-group cleanup (`/api/caterham/v3/query/order_detail_group`), generic order response cleanup (`/order/`), and order-list button cleanup (`/api/aristotle/order_list_v4`) target distinct endpoints.
- The shipping-specific duplicate transformation was already removed by PR #448; the remaining generic order rule performs the retained cleanup once.
- Several similar request-stage rules exist with different actions or match scopes (for example `reject(404)` versus `reject_dict(200)`). They were not collapsed because that could change request behavior. No further response rule was removed.

## Xiaohongshu

- The active plugin triggers the repository-owned `scripts/xiaohongshu/xiaohongshu-rstore.js` for the reviewed routes; the older `xiaohongshu.js` file is not the active trigger for this plugin snapshot.
- The comment-tree path already combines cleanup and media extraction into one iterative traversal and no longer uses a visited WeakSet.
- Video-stream selection uses a single-pass best-stream scan rather than a sorted temporary array.
- A remaining candidate is visible in the image-feed path: the top-level `images_list` is first traversed to build the live-photo cache, then traversed again by `imageEnhance`. This batch records it for a separate behavior-equivalence change; the two traversals were not fused without dedicated fixtures for nested image objects and image-quality modes.

## Douyin / ByteDance

- The current plugin snapshot contains no clearly app-specific Douyin response handler or repository-owned Douyin response script.
- The `is.snssdk.com/api/ad/union/sdk` response trigger points to the generic upstream `adsense.js`, whose visible route logic is centered on Tencent News hosts and Tencent News notifications. This is not sufficient evidence that it is a Douyin response handler.
- ByteDance/Pangolin endpoints elsewhere in the plugin are primarily request-stage rejects. They do not justify adding or modifying response-body parsing. No change was made until an actual Douyin response URL/body pair can be attributed confidently.

## Amap and Baidu Map

- Amap's active local response handler has one response JSON parse/stringify site, no `.filter()`, `.map()`, `.forEach()`, or `Object.keys()` allocations in its main handler, and already caches nested routeInfo/routePlan references. No additional safe repeated traversal was identified in this pass.
- Baidu Map's Protobuf handler already defers the Result payload view until an Ads mutation requires it and creates views only for the target Result/Ads fields. Remaining `Object.keys()` occurrences are in bundled Protobuf runtime code; broad edits there are not justified without profiling and protocol fixtures.

## Validation boundary

Static source inspection establishes the current route inventory and candidate work only. CI regression tests validate the Taobao transformation and optimizer repair path. No iPhone CPU, battery, latency, or memory percentage is claimed; real-device traffic and thermal measurements remain necessary for those claims.
