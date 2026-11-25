# Phase 10 · Batch 64 — Weibo deep-comment adType single-read cache

## Scope
Active `/2/comments/build_comments` response, specifically the top-level `datas` comment-item filtering path used before deep-comment decoration cleanup.

## Finding
The existing filter compared `item?.adType` against three exclusion labels in a short-circuit OR expression. For ordinary JSON objects this repeated the same property lookup up to three times per comment item.

## Change
- Read `item?.adType` once into a loop-local scalar and compare that scalar against the same three labels.
- Preserve the exact three excluded labels, comparison order, short-circuit result, in-place compaction, retained item ordering, and modified-flag behavior.
- Keep the change narrowly scoped to the `datas` branch; root-comment and reply-comment handling remain unchanged.
- Add a marker-guarded, idempotent optimizer that fails closed if the expected upstream expression drifts.
- Add runtime getter-count coverage for each of the three excluded labels and a retained ordinary comment, plus output-equivalence assertions.

## Validation boundary
This is a structural reduction of repeated property access, not evidence of measured device-side CPU, battery, latency, or thermal improvement. The complete repository test suite remains the merge gate.
