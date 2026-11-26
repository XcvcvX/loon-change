# Phase 11 batch 14 — BaiduMap protobuf segment rebuild without chunk arrays

## Scope
- Runtime: `scripts/baidumap/baidu-map-protobuf.js`
- Reproducible optimizer: `tools/optimize_baidumap.py`
- Regression coverage: `tests/test_baidumap_binary_performance.py` and `tests/test_baidumap_offset_optimizer.py`

## Finding
The multi-segment protobuf rebuild already allocated its final payload once, but it first constructed a temporary `chunks` array containing gap and segment byte views. This created per-segment bookkeeping and short-lived subarray objects before copying data.

## Change
- Compute final payload length and rewritten segment offsets/lengths in a validation pass.
- Allocate the output payload once after the final length is known.
- Copy source gaps, unchanged segment views, and replacement segments directly into final positions.
- Remove the temporary chunks array and its per-chunk bookkeeping.
- Preserve payload byte order, gaps, trailing bytes, replacement validation, overlap checks, header offsets, and MD5 calculation.
- Extend the optimizer with idempotence and fail-closed structure checks.

## Expected effect
Removes the intermediate chunks array and retained chunk references. The rebuild uses two bounded passes over segment metadata while keeping one final payload allocation. This is expected to reduce transient allocation/bookkeeping overhead for multi-segment responses.

## Validation boundary
Regression tests verify byte-for-byte reconstruction and segment metadata behavior. No iPhone CPU, memory, battery, or thermal benchmark is claimed.
