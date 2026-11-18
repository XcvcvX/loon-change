# Phase 9 Batch 2 — BaiduMap binary response allocation

## Findings

### BaiduMap (active local response script)

The BaiduMap binary response handler decoded the Protobuf Ads section, then allocated a temporary Result+Ads concatenation solely for MD5. It subsequently allocated the final response buffer and copied both sections again. In the Quantumult X branch it also sliced the just-created output ArrayBuffer, causing another full-size copy.

Changes:
- Reuse an incoming `Uint8Array` as a view instead of copying it through `new Uint8Array(existingTypedArray)`.
- Allocate one final payload buffer, place Result and rewritten Ads directly into it, and calculate MD5 over a zero-copy `subarray()` view.
- Encode the RepHead once with a fixed 32-character MD5 placeholder to determine its stable size, then encode the final MD5 and write the header into the same output buffer.
- Return the owned ArrayBuffer directly in the Quantumult X branch; the new output buffer always starts at byte offset zero.
- Guard the fixed-size header assumption so a schema/hash contract change fails explicitly instead of silently corrupting the binary offsets.

This removes the separate Result+Ads temporary buffer and the final Quantumult X ArrayBuffer slice copy. The final response still requires one output allocation and copies the two payload sections once.

### Taobao (active local response script)

Audit found one JSON parse and one stringify per matching response, no allocating `filter()`/`map()`, and O(1) clearing of ad-only arrays. The remaining splash-section/item traversal performs required field mutations. No speculative loop rewrite was made.

### Didi (local script is not active)

The current plugin's four Didi response triggers point to the upstream R-Store `didi.js`, not `scripts/didi/didi-ads.js`. Editing the local file would therefore have no runtime effect. The local helper already uses in-place filtering; defer a live Didi optimization until the plugin is intentionally switched to the repository-owned handler and parity is established.

## Regression coverage

`test_baidumap_binary_performance.py` executes the actual response-assembly helper with binary fixtures and checks payload order, MD5, RepHead lengths/offsets, and the no-intermediate-concatenation path. Static checks verify typed-array reuse and direct ArrayBuffer return.

No device-level CPU/battery percentages are claimed. Loon/Quantumult X real-device validation remains necessary for end-to-end performance and binary compatibility.
