# Phase 10 batch 56 — Scope Weibo topic-group optimizer validation

## Problem
The repository's sync workflow regenerated the latest R-Store Weibo script but failed in `optimize_topic_group_nested_data_cache`. Its postcondition scanned the entire script for old nested-loop patterns; unrelated active response routes still legitimately use `for (let ii of item.items)` and `removeAvatar(ii?.data)`, so the topic-group check produced a false positive.

## Fix
- Scope route boundaries and all old-pattern checks to `/2/statuses/container_timeline_topic`.
- Keep the exact nested-topic-group transformation and fail-closed anchor checks unchanged.
- Leave similarly shaped code in other response routes untouched.

## Regression coverage
- Existing topic-group cache idempotence and damaged-cache checks now inspect only the target route block.
- Add a fixture appending a legal old-style nested loop outside the topic route and verify the optimizer does not misclassify it.

## Validation
- Re-run the repository sync workflow after merge; the previous run stopped before syntax and unit-test stages.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
