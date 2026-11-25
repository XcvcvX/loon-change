# Phase 10 batch 38 — BaiduMap multi-Ads segment reconstruction and Taobao residual audit

## BaiduMap reconstruction model
- Treat every messageHead entry as a segment descriptor indexed by its original header index.
- Allow multiple Ads entries; each modified Ads segment gets its own encoded replacement at the same header index.
- Require exactly one Result segment for a rebuild. Duplicate Result descriptors, invalid bounds, overlapping segments, or malformed replacement bytes fail closed without emitting a rebuilt response.
- Sort a temporary descriptor list by original payload offset, preserve all inter-segment gaps and trailing bytes, and update each descriptor's new offset/length while retaining original messageHead ordering.
- Keep unchanged Ads, Result, and unknown segment payloads as byte views; allocate the rebuilt payload once.
- Re-encode RepHead once with a fixed-width MD5 placeholder, hash the complete rebuilt payload, and patch the encoded header in place.

## Compatibility coverage
- Exercise zero, one, two, and three Ads headers.
- Include out-of-order messageHead descriptors, unknown segments, preserved gaps/trailing bytes, and replacement-length changes.
- Assert exact payload order, updated offsets/lengths, MD5 correctness, and exactly one RepHead encode.
- Reject duplicate Result headers, overlaps, and out-of-range segments. Repeated Ads headers remain supported.

## Taobao residual audit
- The remaining cloud-video duration/respTimeInMs fields already use cached locals and a single JSON parse/conditional stringify.
- Splash traversal already caches section/item counts and nested references; Poplayer caches response objects and clears arrays in place.
- No additional property-cache change is justified without a demonstrated duplicate access in a hot response path.
