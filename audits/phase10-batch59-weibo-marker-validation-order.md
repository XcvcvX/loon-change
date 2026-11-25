# Phase 10 batch 59 — Weibo route markers before postcondition validation

## Problem
The repository sync workflow failed in the Weibo following-timeline cache optimizer. The optimizer's required-token tuple included its route marker, but the fresh-source branch inserted that marker only after checking the tuple. The same ordering defect was present in the hot-timeline, flowlist/asyn, and search-timeline transforms.

## Fix
- Insert each route marker before checking the corresponding required-token tuple.
- In flowlist/asyn, insert both route-specific markers before the combined route postcondition check.
- Keep the global flowlist/asyn marker insertion and idempotent-source path intact.

## Regression coverage
- Add a source-order regression that verifies marker insertion precedes postcondition validation in all four affected optimizer functions.
- The active runtime script and its data transformations are unchanged by this generator-only fix.

## Validation
- The preceding sync run reached Xiaohongshu generation and then failed at the Weibo following-timeline cache postcondition.
- Re-run the multi-source sync workflow after merge to confirm all Weibo route optimizers can generate from the raw upstream source.
- No device CPU, battery, thermal, or latency measurements are claimed.
