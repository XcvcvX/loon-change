# BaiduMap Protobuf RepHead header cache

## Scope

Reduce repeated access to the decoded `RepHead.messageHead` collection in the binary response scan and rebuild helper.

## Change

The scan now reads `repHeadMessage.messageHead` once, caches its length, and indexes the cached array. The rebuild helper also caches the collection and the Result/Ads entries before updating offsets and lengths. This removes repeated nested property-chain evaluation from the response-header hot path without changing field order or the existing two-entry assembly contract.

## Validation

- Source invariants require the cached collection, cached loop length, and cached Result/Ads entries.
- Focused tests assert the scan no longer reads the nested collection or its length in the loop condition and that assembly updates use the cached entries.
- Existing binary runtime tests continue to cover unchanged-response pass-through, allocation counts, payload order, protobuf header metadata, and MD5 integrity.

## Limits

This is a source-level reduction in repeated property access during BaiduMap Protobuf header traversal and rebuild. It does not alter Protobuf decoding/encoding, binary payload layout, or response semantics. Device-level battery, thermal, and latency changes have not been measured.
