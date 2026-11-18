# Phase 8 Batch 2 — CNTV/iQIYI/MGTV/Youku response hot path

## Scope

The R-Store `cntv.js` handler is referenced by 26 response triggers spanning iQIYI, Mango TV and Youku. The upstream script is approximately 29 KB and contains 11 array `.filter()` assignments plus one unconditional JSON parse after an empty-body completion call.

## Changes

The generated snapshot is pinned to upstream R-Store commit `d0f4dd305bade7cc6a38e3445a768d72aaea0e5b` for this review; CI regenerates it from the current upstream commit and re-runs the inventory checks.

- Vendor a reproducible local snapshot pinned to the R-Store commit used by the build.
- Replace all 11 `array = array.filter(predicate)` operations with stable in-place compaction. This removes the temporary result arrays while preserving predicate and ordering.
- Add a same-index write guard so already-retained elements are not written back unnecessarily.
- Fix the empty-body guard so `$done({})` is terminal and JSON parsing is skipped.
- Route all 26 existing response triggers to the local snapshot. Trigger patterns, tags, `requires-body=true`, MITM scope and ad predicates remain unchanged.

## Regression coverage

Node VM tests disable `Array.prototype.filter` and execute representative iQIYI, MGTV and Youku payloads. They verify output membership/order, tab index repair, one JSON parse per non-empty response, and zero JSON parses for empty bodies. Migration tests fail closed unless all 26 expected trigger references are present.

The optimization reduces known temporary array allocations and unnecessary array writes; it does not claim a measured percentage reduction in device CPU or battery use.
