# Taobao splash item specialized updates

## Scope

Reduce per-item function-call overhead in the Taobao splash response traversal.

## Change

Replace the 15 generic `setIfDifferent` calls made for each splash creative with one specialized `normalizeSplashItem(item)` call. The helper performs the same strict inequality checks and writes the same values, sets the shared `modified` flag only when a value changes, and retains the original truthy checks before clearing `imgUrl` and `videoUrl`.

The generic setter remains available for the other Taobao response paths. Route selection, JSON parsing, traversal order, and lazy serialization are unchanged.

## Validation

- Runtime proxy instrumentation verifies each of the 15 target properties is read once per creative and all required writes still occur.
- Existing splash mutation tests continue to verify target values and lazy serialization.
- The optimizer is idempotent and fails closed when the expected helper structure drifts.
- Repository invariants require the specialized helper and forbid the old per-field setter calls in the splash hot loop.

## Limits

This reduces per-item helper invocations from up to 15 to one. It does not establish device-level battery, thermal, or end-to-end latency improvements.
