# Phase 9 Batch 8 — BaiduMap protobuf no-op fast path

## Finding

The BaiduMap binary response handler already reuses the incoming Uint8Array, keeps the unchanged Result segment as a zero-copy view, and assembles changed payloads in one allocation. However, it still re-encoded the Ads protobuf, recalculated MD5, rebuilt the complete binary response and rewrote the header even when the decoded Ads list contained no target banner/splash item requiring a field change.

## Runtime change

- Keep the existing binary trigger, protobuf schema, target type predicates, required start/end field checks and target timestamp values.
- Decode Ads once to inspect the existing content list.
- Set a mutation flag only when a matching item's start/end values differ from the existing target values.
- When Ads exists but no field changes, return `$done({})` and preserve the original response bytes; skip Ads encode, MD5, output allocation and header rewrite.
- When a target field changes, retain the existing one-allocation assembly path and MD5/header validation.

## Regression coverage

`test_baidumap_binary_performance.py` adds Node VM fixtures for non-target Ads, already-clean target Ads and changed target Ads. The first two must pass through without a replacement body; the changed case must still rebuild a valid response with the exact target timestamps and a 32-character MD5. Existing tests continue to protect byte order, offsets, lengths and hash correctness.

The optimization does not change MITM hosts, URL matching, binary-body mode, protobuf field targets or the ad-selection predicate. Savings apply only to already-clean/no-target binary responses; no device CPU or battery percentage is claimed without Loon on-device measurement.
