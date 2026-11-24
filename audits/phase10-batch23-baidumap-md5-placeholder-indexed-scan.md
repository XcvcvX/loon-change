# BaiduMap Protobuf MD5 placeholder indexed scan

## Scope

Reduce JavaScript-side scanning work on the response-rebuild path when locating the fixed-width MD5 placeholder in the encoded RepHead.

## Change

The prior helper tested every byte offset as a possible start of the 32-byte ASCII-zero placeholder. The updated helper uses the typed-array native `indexOf(0x30)` to jump directly between candidate start bytes, then retains the exact 32-byte equality check.

The scan still:
- accepts only a complete 32-byte placeholder within the encoded header;
- rejects missing or multiple placeholders;
- patches the digest in place without a second Protobuf encode;
- preserves the encoded header length and payload offsets.

## Validation

- Existing runtime assembly regression verifies the final payload bytes, Result length, Ads offset/length, MD5 digest, and exactly one RepHead encode.
- Added static assertions for native candidate indexing and the existing fail-closed checks.
- Optimization invariants prevent the byte-by-byte outer scan from returning.

## Limits

This only affects the relatively uncommon BaiduMap response-rebuild path. It avoids JavaScript checks at non-candidate byte offsets, but no device-level CPU, battery, latency, or thermal improvement is claimed without on-device measurements.
