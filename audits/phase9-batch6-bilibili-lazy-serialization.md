# Phase 9 Batch 6 — Bilibili lazy response serialization

## Findings

The active repository-owned Bilibili JSON handler serves multiple response families through several local triggers. It compacts arrays in place, but always serialized the parsed object at the common exit even when the response already matched the desired tab, feed, profile, splash, PGC, or live-room state.

## Runtime change

- Keep every existing URL branch, ad predicate, field target value, and stable-order filter unchanged.
- Track array membership changes only when the compacted length changes; track tab sorting only when the filtered order is not already canonical.
- Track key deletion and field reset operations so already-clean responses are allowed through untouched.
- Return `$done({})` when no serialized content changed; keep one `JSON.stringify` when a cleanup actually changes the response.
- Preserve the existing same-index write guard in feed compaction and avoid creating any additional response arrays.

## Regression coverage

`test_bilibili_json_performance.py` now counts JSON parse/stringify calls in its Node VM. It checks no-op feed/story, tab, profile, splash, search, PGC, and live-room fixtures (one parse and zero stringify calls), plus changed tab/profile/live cases (one parse and one stringify call) and confirms the expected cleanup output. Existing array write-count tests continue to verify that kept feed items are not written back to identical positions.

No URL trigger, MITM hostname, ad-filter predicate, or field target value was widened. The change removes full-body serialization for already-clean Bilibili responses; it does not claim measured device CPU or battery percentages without on-device Loon measurements.
