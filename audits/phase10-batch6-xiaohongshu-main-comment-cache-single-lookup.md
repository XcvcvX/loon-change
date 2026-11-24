# Phase 10 batch 6 — Xiaohongshu main comment cache single lookup

## Scope
- Align the primary Xiaohongshu comment processor with the already optimized R-Store cache lookup.
- Replace `Map.has(raw)` followed by `Map.get(raw)` with one `Map.get(raw)` per picture/video metadata string.
- Cache `null` after malformed JSON so repeated malformed values are not reparsed.
- Extend the optimizer, idempotence/fail-closed tests, runtime Map operation counters, and optimization invariants.

## Semantics
- `JSON.parse` cannot return `undefined`; therefore `Map.get(raw) === undefined` is an unambiguous cache miss.
- Valid JSON `null` and malformed JSON (cached as `null`) remain cache hits on later occurrences.
- The fixture repeats the same `video_info` string across a picture and a video, asserting two Map reads, zero Map.has calls, and one metadata parse.

## Baidu Map decision
- No protocol rewrite in this batch. The existing binary handler already avoids decoding unrelated payload fields, defers the Result view, and skips protobuf encode, MD5, and body reconstruction when Ads is absent or unchanged.
- Existing binary fixtures assert those no-op paths and the changed-ad rebuild. Further changes inside the bundled protobuf runtime lack a focused protocol fixture/profile and are deferred rather than guessed.

## Validation
- CI Node VM runtime fixture checks behavior and exact Map operation counts.
- Optimizer is idempotent and fails closed on a stale marker or reintroduced double lookup.
