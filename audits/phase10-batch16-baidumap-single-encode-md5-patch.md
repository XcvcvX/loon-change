# BaiduMap Protobuf single-encode MD5 header patch

## Scope

Avoid the second Protobuf encoding of the decoded `RepHead` during response reconstruction.

## Change

The rebuild path now encodes the header once with the fixed-width 32-character MD5 placeholder. After assembling the unchanged Result and rewritten Ads payloads, it computes the payload digest and patches the unique 32-byte ASCII placeholder directly in the encoded header buffer.

The code validates the digest format, requires exactly one placeholder, and fails closed if the placeholder is missing or ambiguous. The header length and payload offsets therefore remain unchanged, while the second Protobuf encode and its temporary output allocation are removed.

## Validation

- Runtime assembly regression verifies payload byte order, Result length, Ads offset/length, and MD5 integrity.
- The test encoder is instrumented to assert exactly one RepHead encode per rebuild.
- Static invariants require the single-encode path and in-place digest patch.

## Limits

This removes one Protobuf header encode and its temporary encoded buffer from the BaiduMap rebuild path. It does not reduce the no-op decode path, and no device-level battery, thermal, or latency improvement is claimed without on-device measurements.
