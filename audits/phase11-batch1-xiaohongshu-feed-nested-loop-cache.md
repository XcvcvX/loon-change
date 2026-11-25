# Phase 11 batch 1 — Xiaohongshu feed nested-loop property cache

## Scope
- Cache response references and array lengths in splash configuration, image feed, and V3 video feed handlers.
- Replace image-download callback iteration and copy-option predicate scans with indexed loops.
- Preserve existing field mutations, copy-option insertion, hashtag filtering, and live-photo cache behavior.
- Limit changes to the Xiaohongshu response script, its reproducible optimizer, and deterministic tests.

## Runtime counter verification
Node.js regression tests wrap target arrays in Proxies and count length reads while handlers execute:
- Image feed: outer data and note-list lengths are each read once; each note's function-switch and copy-option arrays are each read once.
- Splash config: ads-group length is read once; each group's ads length is read once.
- Assertions verify download flags, copy-option insertion, hashtag filtering, and splash timestamps.

## Remaining scope
- Taobao already has a supported-route pre-parse guard, route/object caches, array-length snapshots, and single-read cloud-video properties. The next Taobao step should be fixture-based profiling of larger response payloads, not another speculative rewrite.
- Pinduoduo's current response optimization consolidates shipping/order cleanup into one native JSON handler. Query matcher consolidation is separate and does not traverse response bodies; no extra large-response JSON walker is warranted without a concrete response handler.
- No standalone Douyin response script was identified in the current main-tree inventory. Revisit when a concrete active response handler is found.

## Safety
No Taobao or Pinduoduo behavior changes in this batch. The Xiaohongshu optimizer validates exact marker/structure invariants and fails closed on drift.
