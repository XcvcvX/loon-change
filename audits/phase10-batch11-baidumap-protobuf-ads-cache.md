# BaiduMap Protobuf Ads array and field access cache

## Scope

Optimize the decoded `Ads.content` scan in `scripts/baidumap/baidu-map-protobuf.js`.

## Change

Cache the decoded content array and its length before the scan rather than reading `adsMessage.content` and `.length` during each iteration. For qualifying banner/splash entries with both own `start` and `end` fields, cache those numeric values once before comparing them with the replacement timestamps.

The Protobuf schema, field matching, own-property checks, mutation values, repeated-field order, binary layout, MD5 calculation, and no-op pass-through behavior are unchanged.

## Validation

- Source invariants require the cached array, length, item, start and end locals, and forbid the repeated property expressions.
- Runtime tests instrument the decoded Ads message and each decoded Content item with getters/proxies. A 64-entry fixture verifies one collection-property read and one read each of `start` and `end` per eligible item.
- Existing tests continue to validate byte-view counts, no-op behavior, rebuilt payload order, MD5, and header metadata.

## Limits

This is a source-level reduction in repeated property reads during the Protobuf ad scan. Device-level battery, thermal, and latency changes have not been measured.
