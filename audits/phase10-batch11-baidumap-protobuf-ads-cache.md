# BaiduMap Protobuf Ads collection cache

## Scope

Optimize the decoded `Ads.content` scan in `scripts/baidumap/baidu-map-protobuf.js`.

## Change

Cache the decoded `Ads.content` array and its length before the scan rather than repeatedly evaluating `adsMessage.content` and `adsMessage.content.length` in the loop condition and item access. For an array of N entries, this changes the collection-property access pattern from 2N+1 reads to one read, plus one cached length read.

The per-item date checks retain their original access pattern: `start` and `end` are each read once for qualifying entries. No date-field read reduction is claimed. The Protobuf schema, field matching, own-property checks, mutation values, repeated-field order, binary layout, MD5 calculation, and no-op pass-through behavior remain unchanged.

## Validation

- Source invariants require the cached array and length, and forbid repeated `adsMessage.content` property expressions in the loop.
- Runtime tests instrument the decoded Ads message and Content items with getters/proxies. A 64-entry fixture verifies one `Ads.content` property read for the entire scan. The date-field counters preserve the existing one-read-per-field behavior on qualifying entries.
- Existing tests continue to validate byte-view counts, no-op behavior, rebuilt payload order, MD5, and header metadata.

## Limits

This is a source-level reduction in repeated collection-property reads during the Protobuf ad scan. Device-level battery, thermal, and latency changes have not been measured.
