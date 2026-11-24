# Taobao clearArray property access caching

## Scope

Optimize the shared `clearArray(target, key)` helper in the Taobao response script. It is used for cloud-video `resources/caches` and Poplayer `images/videos` arrays.

## Change

The helper previously evaluated `target[key]` separately for `Array.isArray` and `.length`. It now loads the property once into `current`, then checks the local reference before clearing the original property.

This removes one repeated object-property read for each array-valued target processed, without changing the array clearing condition, replacement behavior, or mutation tracking.

## Validation

- Optimizer is idempotent and fails closed when the cached local reference is altered or repeated property reads return.
- Runtime proxy instrumentation verifies exactly one read each for `res.images`, `res.videos`, and `mainRes.images`, while asserting all arrays are still cleared and Poplayer is disabled.
- Existing parse/stringify count tests continue to verify lazy response serialization and unrelated-route pass-through.

## Limits

This is a small source-level reduction in property reads; no device-level battery, thermal, or latency gain is claimed.
