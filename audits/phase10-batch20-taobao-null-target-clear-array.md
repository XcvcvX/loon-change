# Taobao null-target clearArray fast path

## Scope

Remove short-lived fallback object allocations from Taobao video and Poplayer response cleanup when optional response objects are absent.

## Change

The shared `clearArray` helper now returns immediately for nullish targets. Call sites pass the cached optional object directly instead of evaluating `target || {}` for every cleanup field. This preserves the prior no-op behavior for missing video, Poplayer, and main-resource objects while avoiding temporary empty-object creation. Existing property caching and array mutation behavior remain unchanged.

## Validation

- Optimizer is idempotent and fails closed if the helper or any of the five call sites drift.
- Runtime regression covers missing video and Poplayer objects and confirms pass-through without serialization.
- Runtime invariants forbid the old fallback-object call forms.

## Limits

The change removes up to five transient fallback object literals on the affected routes when their corresponding objects are absent. It does not establish device-level CPU, battery, thermal, or latency improvement.
