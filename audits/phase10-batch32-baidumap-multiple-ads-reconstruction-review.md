# Phase 10 batch 32 — BaiduMap multiple Ads segment reconstruction review

## Review scope
Reviewed the current \`scripts/baidumap/baidu-map-protobuf.js\` Ads segment loop and \`assembleBaiduResponse\` rebuild helper, including the existing single-segment runtime fixture.

## Findings
- The scan loop iterates every \`messageHead\` entry and may decode more than one entry named \`Ads\`.
- When a segment is modified, the loop assigns its encoded bytes to the single response-wide \`newAds\` variable. A later modified Ads segment replaces the earlier encoded bytes.
- The rebuild helper assumes \`messageHead[0]\` is the Result header and \`messageHead[1]\` is the Ads header. It updates only those two entries and builds the payload as exactly \`newResult + newAds\`.
- Consequently, the current implementation is only safe for the supported one-Result/one-Ads layout. It is not a general multi-Ads reconstruction implementation. Additional segments, reordered headers, or repeated Ads headers can cause metadata/payload mismatch or dropped bytes during rebuild.

## Decision
No multi-Ads source change is made in this batch. Do not add an early break or merely retain the last encoded Ads segment. A safe extension requires a complete segment model that preserves every original payload slice, replaces each modified Ads slice independently, recomputes every affected offset and length, preserves header ordering and unrelated segment bytes, then recalculates the body MD5.

## Required future validation
- Runtime fixtures with 0, 1, 2, and 3 Ads headers, including modified and unmodified mixtures.
- Result and Ads headers in noncanonical order, plus unrelated intervening segments.
- Differential verification of decoded header metadata, byte-exact payload preservation, every segment's offset/length, and final MD5.
- Malformed, overlapping, out-of-range, and duplicate-header fixtures must fail closed without returning a partially rebuilt response.

## Outcome
The multi-Ads reconstruction remains an explicit compatibility limitation; the current single-Ads path is left unchanged rather than risking response corruption.
