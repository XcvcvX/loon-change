# Xiaohongshu video-save cache reverse early-exit lookup

## Scope

Optimize the `/v10/note/video/save` response path in `scripts/xiaohongshu/xiaohongshu.js`.

## Change

The persisted `redBookVideoFeed` cache is an array populated by the v4 video-feed handler. The save handler previously scanned every array entry from front to back and assigned `download_url` on every matching ID. It now scans from the end and stops at the first match.

This preserves the previous last-match-wins behavior when duplicate note IDs exist, while avoiding reads of earlier entries once the last matching record is found. It allocates no index or temporary collection and does not alter the cache format, selected URL, disabled-download cleanup, or response serialization.

## Validation

- Optimizer is idempotent and fails closed if the reverse-loop shape or early-exit marker drifts.
- Runtime fixture contains duplicate `target` IDs and verifies the last entry still wins.
- A proxy around the parsed cache array counts numeric element reads; with the match at index 2 and one non-match after it, the reverse scan reads only two entries rather than traversing all four.
- Existing Xiaohongshu performance tests and repository-wide invariants/CI remain required.

## Limits

This is a source-level reduction in cache-array element reads for the hit case. It is not a device-level battery, thermal, or latency measurement.
