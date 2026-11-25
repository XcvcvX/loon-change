# Phase 10 batch 43 — Weibo removeAvatar single-read property cache

## Change
- Cache each removable top-level avatar/decoration property once before its truthy check and deletion.
- Cache each removable user decoration property once before its check and deletion.
- Preserve the existing truthiness conditions, deletion targets, `modified` signaling, and user-reference argument behavior.
- Extend the reproducible optimizer with idempotent, fail-closed transformation checks.
- Add getter-count runtime regression coverage for the high-frequency comment cleanup path.

## Performance rationale
- `removeAvatar` is used by comment cleanup, topic feeds, profile timelines, and other response paths.
- Each affected property was previously read once in the condition and again in the delete target expression.
- The transformed helper reduces each property to one value read while retaining a single in-place deletion. No arrays, callbacks, or maps are added.

## Validation
- Runtime fixture counts getter reads for all six data decoration fields and five user decoration fields.
- Existing comment fixtures continue to verify cleanup behavior and retained comments.
- No device-level CPU, battery, thermal, or latency improvement is claimed without real-device measurements.
