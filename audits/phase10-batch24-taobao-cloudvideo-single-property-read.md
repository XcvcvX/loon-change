# Taobao cloud-video single-read property updates

## Scope

Reduce repeated property access in the supported cloud-video response path.

## Change

The duration and response-time values were previously read once by the truthiness guard and again by the generic `setIfDifferent` helper. The optimized path caches each value in a local constant, preserves the original truthiness gate and strict comparison, and performs the same string assignment only when the value differs.

The `resources` and `caches` array clearing behavior is unchanged.

## Validation

- Node runtime test wraps both fields with accessors and verifies exactly one getter read per field while checking the final values.
- A falsy-value regression verifies numeric zero and empty-string values remain untouched and the response is passed through without serialization.
- Optimizer idempotence and fail-closed drift checks cover the new marker.
- Optimization invariants require the cached reads and forbid the old generic setter calls for these two fields.

## Limits

This removes two repeated property reads on the cloud-video route only. No device-level CPU, battery, latency, or thermal improvement is claimed without on-device measurements.
