# Phase 8 Batch 1 — Bilibili response-array compaction

## Scope

Optimize the repository-owned Bilibili JSON response script only. No trigger URL, response field, ad-filter predicate, MITM hostname, upstream source, or plugin priority is changed.

## Runtime changes

- Cache the source array length once per compaction loop instead of re-reading `length` on every iteration.
- In the shared `filterInPlace` helper, skip writing an element back when its read and write indices are identical.
- Apply the same no-op-write guard to the nested account-section compaction and the vertical feed compaction loops.
- Preserve stable ordering and the existing allowlists / exclusions.

## Why this is safe

The compaction algorithm still visits each original array element once, keeps the same elements in the same order, truncates only the removed tail, and writes a kept element only when it actually moves left. The transform does not change any predicate or response mutation.

## Regression coverage

`test_bilibili_json_performance.py` executes the real script in a Node VM with instrumented arrays. It verifies:
- unchanged feed arrays perform zero numeric-index writes;
- when the first item is removed, only the two shifted kept items are written;
- unchanged vertical-feed arrays perform zero numeric-index writes;
- output membership and order remain unchanged.

The checks validate array-write reduction, not absolute CPU time or device-level battery savings. Real-device Loon testing remains necessary to quantify end-to-end impact.
