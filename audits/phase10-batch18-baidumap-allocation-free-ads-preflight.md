# BaiduMap Protobuf allocation-free Ads preflight

## Scope

Reduce per-response allocations on the common path where the Ads payload contains no creative type targeted by the existing date rewrite.

## Change

Before constructing a Protobuf Ads message, scan its wire-format envelope and each Content.type byte string directly in the original response buffer. If neither `_banner` nor `splash_screen1040` occurs, skip `subarray()` creation and Protobuf decoding entirely. If the scanner encounters malformed bounds or an unsupported wire type, it conservatively falls back to the existing Protobuf decoder. Target matches continue through the unchanged decode, mutation, encode, MD5, and response assembly path.

## Validation

- Runtime fixtures cover both target type families and ordinary non-target types.
- Non-target fixtures assert zero Ads message/property reads and only the existing RepHead byte view.
- Existing changed-target, already-clean-target, missing-Ads, MD5, and response assembly regression tests remain in place.
- Static invariants require the preflight to run before Ads payload view creation.

## Limits

This reduces temporary views and decoded Protobuf object allocation only for non-target Ads payloads. No on-device CPU, battery, thermal, or latency improvement is claimed without device measurements.
