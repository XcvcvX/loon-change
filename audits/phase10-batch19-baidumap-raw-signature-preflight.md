# BaiduMap raw-signature Ads preflight

## Scope

Reduce overhead in the non-target Ads fast path introduced by the previous wire-aware preflight.

## Change

Replace the nested Protobuf wire parser and its per-call helper closures with a single bounded byte scan for the two exact ASCII signatures already used by the rewrite: `_banner` and `splash_screen1040`. This scan allocates no views, arrays, strings, or helper closures. A match anywhere in the Ads payload only causes the existing decoder to run, so unrelated-field matches are safe false positives; a valid target UTF-8 type necessarily contains its signature. Invalid caller bounds conservatively fall back to decoding.

## Validation

- Existing runtime fixtures cover target banner, target splash, ordinary content, multiple Content entries, and no-Ads responses.
- Existing changed-target and already-clean-target response behavior remains covered.
- Static tests require the bounded raw scan to run before payload-view creation and reject the former nested parser helpers.

## Limits

This reduces work in the non-target preflight path; it does not alter target mutation or response reconstruction. No device-level CPU, battery, thermal, or latency improvement is claimed without measurements.
