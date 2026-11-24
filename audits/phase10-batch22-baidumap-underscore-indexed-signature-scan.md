## BaiduMap underscore-indexed Ads signature scan

### Scope
Reduce JavaScript interpreter work in the common non-target Ads preflight path without changing target matching.

### Change
Both supported signatures contain an underscore: _banner and splash_screen1040. The preflight now uses Uint8Array.indexOf(95, fromIndex) to jump between underscore candidates, then performs exact byte comparisons. The scan remains bounded and conservatively returns true for invalid bounds. False positives still only trigger the existing Protobuf decoder; target decoding and mutation are unchanged.

### Validation
- Existing target, non-target, multi-content and rebuild regressions remain.
- Added boundary fixtures and 500 deterministic randomized comparisons against the previous byte-by-byte reference.
- Static invariants require native underscore indexing and forbid the former per-byte JavaScript loop.

### Limits
This reduces JavaScript-level loop iterations when underscores are sparse. Actual speedup depends on JavaScriptCore and payload distribution; no device-level battery, thermal, CPU or latency improvement is claimed without measurements.
