# Taobao splash-home object access cache

## Scope

Avoid repeating the nested response-object traversal that locates the splash-home container.

## Change

The splash route now resolves `obj?.data?.containers?.splash_home_base` once into `splashHome` and reuses that reference for the truthiness guard and `base.sections` lookup. The route gate, truthiness behavior, section traversal order, item mutations, and lazy serialization remain unchanged.

## Validation

- Idempotent, fail-closed optimizer transform.
- Runtime getter-count regression asserts one read of `splash_home_base` for an empty splash response.
- Invariants reject the previous repeated traversal.

## Limits

This removes one repeated nested property traversal on splash responses. No device-level CPU, battery, thermal, or latency improvement is claimed.
