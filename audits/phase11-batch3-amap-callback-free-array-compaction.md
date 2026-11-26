# Phase 11 batch 3 — Amap callback-free response-array compaction

## Scope
- Runtime: scripts/amap/amap.js
- Upstream regeneration: tools/optimize_amap.py
- Existing local response-hook fan-out remains unchanged (14 trigger references).

## Finding
The Amap response handler already compacted arrays in place, avoiding replacement arrays created by Array.filter(). However, 13 compaction call sites still supplied inline predicate callbacks to a generic helper. Each matching response created short-lived callback functions, and the helper performed an indirect function call for every array element. It also reread the array length after the traversal.

## Change
- Replace the callback-based helper with explicit mode-dispatched loops. Dispatch occurs once per array; each element is tested directly in its selected loop.
- Cover all reviewed modes: navigation cards, map-business cards, schema filtering, dynamic route ads, music cards, profile cards, nearby modules, search-result cards, and both suggestion-list shapes.
- Cache the array length once inside the helper. Retain stable in-place compaction and the same allowlists/exclusions.
- Keep suggestion-item references local within the direct loops.
- Extend the upstream optimizer with a marker, exact mode-inventory checks, idempotence, and fail-closed validation so scheduled upstream refreshes reproduce the change.
- Add static and Node runtime regression coverage for mode coverage, stable ordering, retained cards, route filtering, and suggestion filtering.

## Expected runtime effect
Removes 13 per-response predicate callback creations and per-element callback invocations on Amap array-compaction paths. Each compaction helper invocation now reads the array length once. No replacement filtered arrays are introduced. JSON parsing and serialization behavior is unchanged; mutation-aware lazy serialization remains in place.

## Safety and measurement boundary
No response route, trigger matcher, script URL, requires_body value, MITM hostname, filter allowlist, or response field mutation was intentionally changed. Output order and retained item order are preserved by read/write compaction. Node fixtures validate structural behavior only; no real-device CPU, battery, temperature, or latency improvement is claimed without iPhone measurements.
