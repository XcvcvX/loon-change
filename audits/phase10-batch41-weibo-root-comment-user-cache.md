# Phase 10 batch 41 — Weibo root-comment user reference cache

## Change
- Cache the root-comment `user` object once per comment item.
- Pass the cached user reference to `removeAvatar` instead of allowing its default parameter to read `item.user` again.
- Cache the user's name once before checking the existing excluded account names.
- Preserve the excluded names, avatar cleanup, comment order, and filtering behavior.
- Add an idempotent, fail-closed optimizer transformation and regression assertions.

## Performance rationale
- Removes repeated nested `item.user.name` reads in the `root_comments` fallback path.
- Avoids a second `item.user` lookup through the `removeAvatar` default parameter.
- Keeps the same linear traversal and does not allocate additional collections.

## Validation
- Existing runtime fixtures continue to exercise root-comment filtering and avatar cleanup.
- Added optimizer structure, idempotence, and fail-closed regression assertions.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
