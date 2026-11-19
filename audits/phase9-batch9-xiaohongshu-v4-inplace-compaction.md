# Phase 9 Batch 9 — Xiaohongshu v4 in-place feed compaction

## Finding

The active Xiaohongshu v4 response handler still allocated replacement arrays in several response paths: search results, two follow-feed variants, homefeed, image-feed tags, and comment-cache deduplication. The homefeed path built a second array while retaining only ordinary notes; comment-cache updates used `concat()` followed by `filter()`, creating two additional arrays.

## Runtime change

- Add one stable `compactInPlace` helper that preserves retained item order and avoids same-index writes.
- Compact search results and follow-feed allowlists directly in their parsed response arrays.
- Compact homefeed in place while preserving the prior keep/drop conditions, retained null/undefined entries, and `related_ques` removal.
- Compact `interact_vote` tags in place.
- Append newly extracted comment live-photo/video entries into the existing cache array, then deduplicate that array in place with the same first-occurrence-wins behavior.
- Keep response triggers, ad predicates, cache keys, note IDs, video selection, and output payload fields unchanged.

## Regression coverage

`test_xiaohongshu_v4_performance.py` now disables `Array.prototype.filter` inside the Node VM and exercises search, both follow-feed routes, homefeed, image-feed tags, and comment live-photo cache deduplication. Existing v4 video-feed, cache, and download-permission tests remain in place.

The change removes transient array allocations; it does not change the selected items or cache ordering. No device CPU/battery percentage is claimed without on-device Loon measurement.
