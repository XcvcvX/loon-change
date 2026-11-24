# Phase 10 Batch 11 — Didi nested traversal property cache

## Scope

- Cache `show_data.length` before indexed traversal.
- Read each block's `scene_ids` property once and reuse the local reference for validation and compaction.

## Behavior

Filtering predicates, retained order, and non-array `scene_ids` values are unchanged. No route or serialization behavior changes.

## Validation

A response runtime fixture covers multiple blocks, filtered and retained IDs, and a non-array value. The optimization invariant requires the cached accesses and forbids the previous repeated reads.

## Expected benefit

One array-length lookup per show-data response instead of one per loop condition; one `scene_ids` property lookup per block instead of two. Device battery and thermal impact has not been measured.
