# Phase 10 batch 58 — Make Weibo removeAvatar helper boundary comment-independent

## Problem
The post-merge sync workflow progressed through Xiaohongshu and Weibo topic-group generation, then failed in `optimize_remove_avatar_property_cache` with a helper boundary drift. That optimizer depended on matching the exact comment text immediately following `removeAvatar`; upstream currently appends extra punctuation/text to that comment.

## Fix
- Locate the cached-user `removeAvatar(data, user = data?.user)` function body using the optimizer's JavaScript-aware brace matcher.
- Replace only the function body and leave following comments and functions intact.
- Keep the expected source-field list fail-closed, and preserve the runtime cached-field implementation.

## Regression coverage
- Add a fixture with the same helper followed by the upstream-style `// 移除信息流关注按钮,推广,热评` comment.
- Assert transformation, required cache fields, preserved comment, and idempotence.

## Validation
- Re-run the multi-source sync workflow after merge; previous run stopped before syntax and regression-test stages.
- No device-level CPU, battery, thermal, or latency measurements are claimed.
