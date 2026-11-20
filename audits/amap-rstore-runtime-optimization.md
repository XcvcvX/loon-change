# Amap R-Store response runtime optimization

- Upstream: `zirawell/R-Store` commit `d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`
- Active plugin hooks migrated: 7 (AMAP, AMAP-2, AMAP-7, AMAP-10, AMAP-11, AMAP-13, AMAP-14); all retain `requires-body=true`.
- Added an explicit route allowlist before JSON parsing for the seven active endpoint families; unrelated routes pass through without parsing.
- Fixed the upstream empty-body branch so it terminates before JSON.parse.
- Replaced 11 allocating Array.filter assignments with stable in-place compaction; retained each existing keep/drop predicate and order.
- Kept all original response field mutations, endpoint patterns and MITM scope unchanged.
- Added reproducible source optimizer, fail-closed 7-trigger migration and Node VM regression tests.
- Runtime savings are structural; no device-side CPU/battery percentage is claimed.
