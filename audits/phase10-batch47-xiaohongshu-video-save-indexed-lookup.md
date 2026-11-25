# Phase 10 batch 47 — Xiaohongshu video-save indexed lookup

## Change
- Cache the video-save response's `data` object and `note_id` once.
- Cache the stored video-feed length once and replace the iterator loop with an indexed scan.
- Preserve forward order and stop at the first matching note ID.
- Reuse the cached response-data object when updating `download_url` and clearing the existing download-disable fields.
- Extend the upstream optimizer to migrate both pre-existing save-loop forms and validate the new shape idempotently.

## Performance rationale
- The previous loop reread `obj.data.note_id` once per candidate and reread `obj.data` for the download URL and disable-state updates.
- The new loop performs one response-data lookup, one note-ID read, one cached feed-length read, and indexed item reads only until the first match.
- No map or secondary lookup cache is allocated; the existing persisted feed format is unchanged.

## Validation
- Node runtime getter/proxy instrumentation checks one response-data read, one note-ID read, one feed-length read, and early termination after the matching second record.
- Regression also verifies the URL replacement and existing download-disable response behavior.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
