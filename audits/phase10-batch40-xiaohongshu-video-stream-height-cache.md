# Phase 10 batch 40 — Xiaohongshu video stream height cache

## Change
- Keep the existing single-pass H.265 stream selection and stable first-item tie behavior.
- Cache each candidate's numeric height once and retain the current best numeric height in a scalar.
- Remove repeated conversion/read of the selected stream's height on every subsequent candidate.
- Extend the optimizer's exact transformation and regression assertions.

## Performance rationale
- The video-feed path may compare multiple H.265 renditions per note. The previous loop converted the candidate height and re-read/reconverted the selected height for every valid candidate.
- The new loop performs one numeric conversion per valid candidate and one scalar comparison, without sorting, filtering, callbacks, or extra arrays.

## Validation
- Existing runtime fixture verifies that the highest-height stream remains selected.
- Static regression assertions verify the cached-height path and absence of repeated selected-height conversion.
- First item is still retained on equal heights because the comparison remains strictly greater-than.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
