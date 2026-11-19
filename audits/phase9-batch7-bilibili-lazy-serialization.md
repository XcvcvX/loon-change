# Phase 9 Batch 7 — Bilibili lazy response serialization

## Findings

The active Bilibili local response script is shared by multiple response trigger groups covering tabs, profile, feed, splash, PGC and live-room payloads. It used stable in-place compaction for several arrays, but still serialized every matched JSON response even when all fields and arrays were already in the expected state.

## Runtime change

- Retain every existing URL branch, ad predicate, VIP field, timestamp, list whitelist and output field target.
- Track array compaction by actual length changes, and track field deletion/reset only when the JSON-visible value changes.
- For navigation tabs, skip `Array.sort()` when the filtered list is already in canonical order; when sorting is required, keep the existing allowlist comparator and stable order.
- Return `$done({})` for unchanged matched responses and serialize once only when a cleanup mutation changes the response.
- Keep the existing same-index write guard for feed compaction.

## Regression coverage

`test_bilibili_json_performance.py` now tracks JSON.parse/JSON.stringify in the Node VM. No-op fixtures cover feed/story, tab navigation, iPad/profile pages, VIP status, splash, search, PGC modules and live-room data (one parse, zero stringify). Changed fixtures validate tab filtering/sorting, profile/VIP cleanup and live-room cleanup (one parse, one stringify). Existing feed tests continue to check zero same-index writes and the exact number of shifted array writes.

No response URL matcher, MITM hostname or ad-removal predicate was expanded. This removes response serialization for already-clean Bilibili payloads and avoids unnecessary sort work on already ordered tabs; device CPU/battery savings are not claimed without on-device Loon measurements.
