# Pinduoduo redundant query matcher consolidation

## Scope

Remove seven Pinduoduo request rules that only add a literal query-string condition to an existing broader matcher with the same URL prefix and the same `reject_dict(200)` action.

## Change

The broader patterns are anchored at the API host/path prefix and are not end-anchored, so they already match both bare endpoints and URLs with query parameters. Each narrower `\\?` variant duplicates a rule evaluation without changing the action or matching any additional request. The seven narrow rules are removed; broader matchers remain unchanged.

The existing order-response single-pass cleanup is preserved. Other applications' rules, Pinduoduo rules with different actions, and response transformations are untouched.

## Validation

- Optimizer requires exactly seven Pinduoduo narrow matchers and one corresponding broad matcher for each; inventory drift fails closed.
- Tests verify query-bearing URLs still match broad rules, narrow rules disappear, unrelated Amap rules remain untouched, and repeated optimization is idempotent.
- Plugin invariants forbid reintroducing all seven narrow rules.

## Limits

This removes seven redundant request matcher evaluations from the aggregate plugin. No device-level battery or thermal improvement is claimed without measurements.
