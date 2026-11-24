# Phase 10 batch 25 — Weibo hot-loop scalar membership

## Scope
Replaced 15 array-literal membership checks in the R-Store Weibo response handler with scalar strict-equality comparisons across card-list, comment, profile, search, and timeline paths.

## Performance rationale
The previous expressions created short array literals and invoked `.includes(...)` each time the condition ran. Several checks execute inside nested card/group loops. Direct comparisons remove those temporary arrays and method calls.

## Safety
- Preserved each member value, strict equality, comparison order, optional-chain access, and positive/negative condition.
- Did not alter response traversal, filtering order, mutation, serialization, or URL dispatch.
- Optimizer uses exact occurrence counts, a unique marker, idempotence checks, and fail-closed drift detection.

## Validation
Static regression checks verify the transformed expressions and absence of array-literal membership checks. Existing Node runtime tests cover card-list filtering, comment filtering, feed compaction, and lazy serialization. No device-level CPU, battery, thermal, or latency measurements are claimed.
