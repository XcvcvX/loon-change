# Didi URL route dispatch cache

## Scope

Cache the four supported response-route predicates once per request and reuse those booleans for both the pre-parse allowlist and the post-parse dispatch branches.

## Change

The script computes scene-list, homepage-core, info-list, and user-center route flags once. The JSON.parse guard and corresponding response handlers reuse those flags, avoiding repeated URL substring checks on supported responses. Unrelated responses still exit before JSON.parse.

## Validation

- Focused source test asserts each route substring check occurs exactly once and all four dispatch branches use cached booleans.
- Existing runtime response tests continue to exercise the scene-list handler and pre-parse no-op path.
- Optimizer transformation is idempotent and fails closed if route anchors or expected branch counts drift.

## Limits

This reduces repeated URL substring checks and route-dispatch work at source level. No device-level battery, thermal, or latency measurements are claimed.
