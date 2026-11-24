# Xiaohongshu best-stream selection without per-call closure

## Scope

Optimize `selectBestStream`, which is invoked for each video-feed item and also while extracting comment media URLs.

## Change

The prior implementation created a local `choose` arrow function every time `selectBestStream` ran, then called it for H.265 and, only when no H.265 result existed, H.264. The replacement uses a two-pass scalar loop over the two source lists directly. It does not create a callback closure, a temporary list, or a candidate copy.

Selection semantics stay the same: H.265 remains preferred whenever it contains a usable URL; otherwise H.264 is considered. Within a codec, the largest pixel count wins, bitrate breaks resolution ties, and the first item wins exact ties.

## Validation

- Optimizer idempotence and fail-closed checks require the marked two-pass structure and reject closure-based regressions.
- Runtime fixtures cover H.265 preference, H.264 fallback for empty and unusable H.265 lists, resolution ordering, bitrate tie-breaking, and stable exact-tie behavior.
- Repository-wide tests, JavaScript syntax checks, and generated-asset invariants remain required.

## Limits

This removes one per-call helper-closure allocation at source level; it is not a measured device-level battery, heat, or latency result.
