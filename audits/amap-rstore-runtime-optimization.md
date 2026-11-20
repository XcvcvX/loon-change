# Amap R-Store response runtime optimization

- Upstream: `zirawell/R-Store` commit `d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`
- Migrates all 14 active response hooks found in the pinned R-Store all-in-one feed; all keep their original matchers and `requires-body=true`.
- Adds a pre-parse route allowlist covering all 14 upstream endpoint families; unrelated paths pass through without JSON.parse.
- Fixes the upstream empty-body branch so it terminates before JSON.parse.
- Replaces 11 allocating Array.filter assignments with stable in-place compaction; existing keep/drop predicates and order are retained.
- Keeps all response field mutations and MITM scope unchanged.
- Adds a reproducible source optimizer, fail-closed 14-trigger migration, and Node VM regression tests.
- Runtime savings are structural; no device-side CPU/battery percentage is claimed.
