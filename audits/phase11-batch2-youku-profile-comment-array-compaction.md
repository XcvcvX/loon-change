# Phase 11 batch 2 — Youku profile and comment in-place compaction

## Scope
- Runtime: `scripts/cntv/cntv.js`
- Active response routes: `columbus.uc.query/` (Youku personal center) and `columbus.ycp.query/` (Youku playback comments)
- Shared local script fan-out: 26 CNTV/iQIYI/Mango TV/Youku response trigger references.

## Finding
The two Youku branches still rebuilt filtered arrays:
- Personal-center response created an outer `newNodes` array and up to two nested `newII` arrays.
- Playback-comment response created an outer `newNodes` array and up to two nested `newItems` arrays.

These are response-body transformations over potentially multi-level node lists. The replacements are temporary copies and add allocations proportional to retained node counts.

## Change
- Compact the existing parent and child arrays with bounded read/write indices.
- Preserve each branch's exact ID/type exclusions, allowlists, parent retention, and original item order.
- Cache the selected arrays and loop lengths locally; do not add callbacks, temporary arrays, sets, or push operations.
- Extend `tools/optimize_cntv.py` so the upstream-sync build regenerates both optimizations and fails closed if either source branch drifts.
- Add optimizer idempotence/drift checks plus Node runtime fixtures for both routes. Runtime tests disable `Array.prototype.push`, verify output content/order, and assert one response parse and one serialization.

## Expected allocation effect
Eliminates up to three replacement arrays on a matching personal-center response and up to three on a matching comment response (depending on whether the relevant nested lists exist). The arrays already present in the parsed response are reused. This is a structural allocation reduction, not a measured iPhone CPU, battery, temperature, or latency result.

## Safety
No trigger matcher, script URL, `requires_body` setting, MITM hostname, response allowlist, or unrelated CNTV route was changed. The optimizer validates exact old branch content on first migration and the expected marker/loop structure on subsequent upstream rebuilds.
