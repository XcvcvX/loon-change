# Phase 10 batch 27 — Xiaohongshu v4 video-feed function-entry scan

## Scope
The v4 video-feed response checked download-button presence with Array.prototype.some and an inline callback, then re-read the nested function_entries property to append the button when absent.

## Change
- Cache the function_entries array reference once per feed item.
- Replace the callback-based some scan with a direct loop that stops at the first video_download entry.
- Preserve the original non-empty-array gate, strict type comparison, insertion position, and no-duplicate behavior.

## Validation
Added optimizer idempotence/fail-closed coverage and a Node runtime fixture for present, missing, empty, and absent function-entry arrays. No device-level CPU, battery, thermal, or latency measurements are claimed.
