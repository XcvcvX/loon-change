# Xiaohongshu imagefeed array-frame length cache

## Scope
- Runtime: `scripts/xiaohongshu/xiaohongshu.js`
- Path: imagefeed image-quality enhancement and compact live-photo extraction traversal

## Change
Cache the array length in each traversal stack frame. The root frame records the input array length once, and each nested array frame records its own length once when pushed. The array branch compares its cursor with the cached frame length instead of reading `value.length` on every loop iteration.

## Behavior and safety
- Preserve depth-first traversal order, image URL rewriting, original-quality first-match behavior, and live-photo cache extraction.
- Object traversal continues to use its already-cached `Object.keys` array.
- The traversal mutates string properties only; it does not append/remove array entries, so snapshotting each array length at frame creation preserves the prior iteration boundary.
- Optimizer is idempotent and fails closed on marker/structure drift.

## Verification
- Add static optimizer/idempotence/drift tests.
- Add Node runtime Proxy instrumentation to assert exactly one `length` getter read per traversed array frame, while verifying transformed URLs remain correct.

This is a structural reduction in repeated property reads. No device-side CPU, battery, thermal, or frame-time benchmark is claimed.
