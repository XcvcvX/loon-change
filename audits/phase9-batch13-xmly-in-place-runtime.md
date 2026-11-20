# Phase 9 Batch 13 — Ximalaya in-place filters and lazy response serialization

## Finding

The active R-Store Ximalaya handler is referenced by five response triggers. The 3,150-byte upstream handler parses a matching response in one of five route branches, allocates six replacement arrays with `Array.filter`, and serializes every recognized response even when no retained payload data changes.

## Runtime change

- Dispatch the five supported Ximalaya routes before JSON parsing; unrecognized paths return without parsing.
- Parse each supported response once.
- Replace all six array filters with stable in-place compaction.
- Reuse module-level `Set` instances for the three retained category types and three home-entry IDs.
- Track whether any response data changed; skip `JSON.stringify` for already-clean responses.
- Keep all five plugin matchers, tags and `requires-body=true` declarations unchanged; only migrate their script asset URL.

## Coverage and limits

`test_xmly_performance.py` exercises all five endpoints, array keep/drop behavior, top-header deletion, clean pass-through, empty and invalid JSON, one-parse/one-stringify bounds, and guards against any use of `Array.filter` or `Array.map`.

The changes reduce temporary array allocation and avoid serializing already-clean responses. No on-device CPU/battery percentage is claimed.

Upstream snapshot: `zirawell/R-Store@d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`.
