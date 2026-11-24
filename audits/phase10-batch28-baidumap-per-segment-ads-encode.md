# BaiduMap Ads per-segment mutation gate

## Change

The Ads response loop previously used the response-wide `modifiedAds` flag to decide whether to encode the current Ads message. Once an earlier Ads segment changed, a later segment containing a target signature could be encoded even when that later segment itself had no field mutation. This caused an unnecessary Protobuf encode and could replace the pending encoded payload with an unchanged segment.

The loop now tracks `adsSegmentModified` locally for each Ads segment. It sets the response-wide flag and encodes the current segment only when that segment's own start/end fields were actually changed.

## Semantics and scope

- Existing target creative matching and start/end replacement values are unchanged.
- Response-wide `modifiedAds` remains the final signal for whether the response needs rebuilding.
- Non-mutated Ads segments no longer trigger a redundant encode or overwrite the pending encoded bytes.
- This focused change does not claim to implement arbitrary multi-Ads payload reconstruction. The existing response assembler's header layout assumptions remain unchanged and require a separate compatibility project.

## Validation

The BaiduMap performance test asserts the local mutation gate and ensures encoding is gated by the current segment rather than the response-wide flag. Full CI remains the merge gate.
