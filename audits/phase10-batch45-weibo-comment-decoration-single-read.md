# Phase 10 batch 45 — Weibo comment decoration single-read cache

## Change
- Cache the four frequently removed decoration fields on standard comment items before truthy checks and deletion.
- Apply the same single-read pattern to root comments.
- Cache the user and reply-comment references before removing reply-list icons and badges.
- Cache the root-comment reference and bubble before deletion.
- Preserve all existing truthiness conditions, cleanup targets, filtering, stable order, and `modified` signaling.
- Add idempotent/fail-closed optimizer coverage and getter-count runtime regressions.

## Performance rationale
- The `/2/comments/build_comments` path can process large comment collections.
- The previous truthy check followed by a delete target caused duplicate reads of the same nested property.
- The updated logic reads each targeted property once and reuses the object reference; it introduces no new collection or callback.

## Validation
- Getter-count tests cover standard comments, root comments, reply comments, and the standalone rootComment object.
- Existing comment retention and avatar cleanup tests remain in place.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
