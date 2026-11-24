# Phase 10 Batch 3 — Xiaohongshu comment-cache lookup

## Change

The Xiaohongshu comment response helper caches parsed `picture.video_info` objects in a `Map`. Previously, each picture performed `Map.has(key)` and then `Map.get(key)`; cache misses also performed the separate lookup before parsing and inserting.

The helper now performs one `Map.get(key)`. When the result is `undefined`, it parses the original JSON string and stores the parsed value. JSON parsing cannot produce JavaScript `undefined`, so that value remains an unambiguous cache-miss sentinel. The same source string still shares one parsed object across pictures.

## Behavior and cost boundary

- Preserve the exact raw-string cache key, parsed object, stream selection, output order, and live-photo record format.
- Preserve the number and timing of `JSON.parse` calls: once per distinct `video_info` string encountered in the classified comment nodes.
- Replace two Map probes on a cache hit with one; replace the miss-path `has + set + get` sequence with `get + parse + set`.
- No response route, cleanup behavior, persistent-storage key, or serialization boundary changes.
- The optimizer template is updated together with the checked-in runtime so a later upstream regeneration reapplies the change; optimizer idempotence and source-drift checks remain in force.

## Regression coverage

The Node VM test harness counts `Map.get` and `Map.has` calls. A repeated-`video_info` fixture asserts three reads for three pictures, zero `has` calls, one inner JSON parse for the shared string, and unchanged live-photo identifiers. The existing nested-comment fixture also asserts its original parse count and now checks the cache access pattern.

## Cross-application review

### Pinduoduo homepage

The active `/api/alexa/homepage/hub` response route has one JQ transformation. Its `map(select(...))` operations build allowlisted arrays while preserving the allowed tab/module order; replacing them with deletion or a generic in-place rewrite is not proven equivalent with the current fixtures. No second response-body handler is applied to the same endpoint. No production change was made.

### Douyin / ByteDance

The active `is.snssdk.com/api/ad/union/sdk` trigger currently points to the generic upstream `AntiAd/adsense.js` script. Its explicit route branches and notification are Tencent News-specific, but the fallback also nulls `body.adList` on any matched response that contains that property. Without a captured Douyin response fixture, it is not safe to remove or narrow the trigger, nor to assert that it is a dedicated Douyin handler. Other Pangle/Pangolin rules in the reviewed plugin are predominantly request-stage blocks. No response-body parsing was added.

### Baidu Map

The local Protobuf handler already defers the target Result byte view until an Ads mutation is required, returns the original response when no eligible Ads mutation occurs, and only reuses the Result payload slice for reconstruction. Remaining broad `Object.keys` usage is within bundled Protobuf runtime code. Without a protocol fixture and a focused profile, changing that runtime would be speculative. No production change was made.

## Validation boundary

The added VM assertions measure helper-level Map access and parse counts only. They are not iPhone CPU, energy, memory, latency, or thermal measurements; no device-level percentage improvement is claimed.
