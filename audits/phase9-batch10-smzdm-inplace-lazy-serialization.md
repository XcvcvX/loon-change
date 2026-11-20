# Phase 9 Batch 10 — SMZDM in-place response compaction and lazy serialization

## Finding

The active R-Store `smzdm.js` handler is attached to nine response triggers. Its homepage path recursively rebuilt every visited array with `map().filter(Boolean)`, and the route-specific component, function, service and row allowlists built additional replacement arrays. The handler also serialized every parsed response, even when the payload was already clean. Its empty-body branch signalled completion but continued into `JSON.parse`.

## Runtime change

- Add a stable-order `compactInPlace` helper and apply it to recursive cell-type filtering and the existing homepage, app-home, ranking, hot-tag, service and ad-row predicates. Retained items and their order remain unchanged; no `Array.prototype.map/filter` allocation remains in this script.
- Preserve the existing allowlists, cell types, field deletions, row predicates and position numbering. `fixPos` now writes only when a position differs.
- Track actual mutations. For already-clean responses, call `$done({})` and skip `JSON.stringify`; changed responses still serialize the updated object once.
- Make the empty-body guard terminal, so an empty response is completed without attempting JSON parsing.
- Generate the local handler from the current R-Store checkout and record its upstream commit. Migrate exactly nine existing SMZDM script references to the local URL; fail closed if the trigger count or source anchors drift.

## Regression coverage

`test_smzdm_performance.py` runs the actual response script in a Node VM, disables `Array.prototype.map/filter`, and covers empty bodies, nested homepage ad cells, homepage arrays and position repair, clean no-op responses, app-home allowlists, VIP field removal and footer image cleanup. It also checks idempotent local routing and rejects partial or mixed remote/local trigger inventories.

## Scope and measurement

No URL matcher, Rewrite action, MITM hostname, response-body requirement, script trigger count, or ad-selection predicate is changed. The expected savings are fewer transient arrays and no replacement-body serialization for already-clean responses. This is a code-path improvement; no device CPU/battery percentage is claimed without an on-device Loon measurement.

Upstream snapshot used for this batch: `zirawell/R-Store@d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`.
