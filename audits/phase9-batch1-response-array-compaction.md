# Phase 9 Batch 1 — high-fanout response-array compaction

## Scope

Optimize the repository-owned Xianyu, Meituan, Jingdong and Pinduoduo response handlers. Existing response triggers, URL matchers, MITM hostnames, enable arguments, field mutations and ad-removal predicates remain unchanged.

## Runtime changes

- Add stable in-place array compaction with a cached source length and a same-index write guard.
- Replace allocating `filter()` calls in Xianyu feed/profile/circle/search arrays, Meituan personal-center/mini-program/hotword arrays, Jingdong floor/navigation/service arrays, and Pinduoduo homepage tabs/modules.
- Fold Jingdong's optional welcome-home exclusion into the existing allowlist pass, avoiding a second full traversal while preserving the `jkds_enable` behavior.
- Replace Jingdong's identity `map()` over virtual service centers with a direct loop; nested service-list filtering remains semantically identical.
- Preserve stable ordering and all original keep/remove predicates.

## Regression coverage

`test_response_array_compaction_performance.py` executes each real script in a Node VM, disables allocating `Array.prototype.filter` and `Array.prototype.map`, and verifies one outer JSON parse plus expected output membership and ordering for representative responses.

These tests prove the targeted allocation patterns are removed and response behavior is preserved for the fixtures. They do not claim measured device-level CPU or battery percentages; real-device Loon testing is still required for end-to-end measurements.
