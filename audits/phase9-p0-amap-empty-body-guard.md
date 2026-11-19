# Phase 9 P0 — Amap empty-body response guard

## Finding

The active Amap consolidated response script is referenced by ten response triggers. Its top-level empty-body condition called `$done({})` but then continued into `JSON.parse($response.body)`. An empty response could therefore still incur a failed parse after completion had been signalled.

## Change

Make the empty-body branch terminal by putting JSON parsing, all existing URL-specific mutations, and the final response completion inside the non-empty `else` block. Keep every URL matcher, ad predicate, field mutation, Protobuf-independent payload behavior and MITM scope unchanged.

## Regression coverage

A Node VM test supplies an empty body, counts JSON.parse calls, and requires exactly zero parses plus a pass-through `$done({})`. Existing Amap in-place compaction behavior tests remain unchanged and exercise non-empty payloads.

This removes the unnecessary parse attempt on empty bodies and prevents parse errors after completion. No device CPU or battery percentage is claimed without on-device measurement.
