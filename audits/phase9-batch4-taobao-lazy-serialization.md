# Phase 9 Batch 4 — Taobao lazy response serialization

## Findings

The active repository-owned Taobao response script parsed each matched body once and always called `JSON.stringify`, including responses where no ad-related field was present and no object mutation occurred. Because the handler covers cloud-video configuration, Taobao splash payloads and Alibaba poplayer JSON, unchanged responses could still pay for a full response serialization and a replacement body string.

## Runtime change

- Keep the existing single `JSON.parse` and all URL branches, field predicates, values, and mutation order unchanged.
- Track whether a targeted field was actually modified.
- Return `$done({})` for unchanged responses so Loon retains the original body without allocating a serialized copy.
- Serialize once only when an existing ad-cleanup mutation has occurred.
- Preserve the empty-body fast path.

## Regression coverage

`test_baidumap_binary_performance.py` now executes the real Taobao script in a Node VM and tracks parse/stringify calls. It verifies zero stringify calls for no-op video, splash, and poplayer responses; one stringify for each changed response; and preservation of the original video, splash, and poplayer cleanup output.

No response matcher, MITM hostname, script trigger, or ad-removal predicate was changed. This removes a full JSON serialization/string allocation on no-op responses; real-device CPU/battery savings are not quantified without Loon device measurements.
