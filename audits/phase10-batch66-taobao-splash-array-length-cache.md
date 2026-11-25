# Phase 10 · Batch 66 — Taobao splash array-length single-read cache

## Scope
The active Taobao splash response traversal in `scripts/taobao/taobao.js`, covering the section array and each section's `taobao-splash.data` item array.

## Finding
The indexed traversal already cached loop bounds, but each array length was read once in the non-empty guard and again when assigning the cached loop bound. This caused two length reads per section array and two per splash item array.

## Change
- Use an array-type-guarded ternary to read `sections.length` once into `sectionCount`.
- Use the same pattern to read each valid `splashItems.length` once into `itemCount`, retaining the empty-array early continue.
- Preserve array validation, section/item traversal order, per-item normalization, mutation detection, and serialization behavior.
- Extend the optimizer with a separate marker-guarded, idempotent transformation that fails closed on shape drift.
- Add runtime Proxy getter-count coverage across multiple sections, including an empty splash array.

## Validation boundary
The runtime fixture verifies one `sections.length` read and one `splashItems.length` read per section. It does not measure device-side CPU, battery, thermal, or response-latency changes.
