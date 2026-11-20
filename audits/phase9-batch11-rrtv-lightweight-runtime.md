# Phase 9 Batch 11 — RRTV lightweight runtime and response fast paths

## Finding

The active R-Store RRTV response handler is referenced by nine response triggers. Its upstream snapshot is 26,081 bytes and embeds a general-purpose MagicJS runtime with storage, networking, encoding, notification and other APIs that the RRTV response body does not call. The response handler only uses the request/response objects, two logging methods and completion. Video and drama responses also used four sequential global regular-expression replacements; the homepage handler always serialized JSON, even when no target section was removed.

## Runtime change

- Replace the unused MagicJS framework with a minimal Loon response adapter exposing only `isResponse`, `request`, `response`, `logError`, `logWarning` and `done`.
- Add a terminal empty-body guard before route handling.
- Compact the homepage section array in place, preserving retained-item order and the existing drop predicate for `AD`, `SINGLE_IMAGE` and `SHORT_VIDEO`.
- Skip JSON serialization for already-clean homepage responses and already-empty `ad/getAll` lists.
- Combine the four playback-flag regular-expression passes into one global scan. Return the original response when none of the four flags needs changing.
- Keep the original route predicates and payload replacement data unchanged. The plugin's nine response matchers, `requires-body=true` declarations and MITM scope are not edited.

## Size and regression coverage

The checked-in optimized response script is 14,207 bytes versus the 26,081-byte upstream snapshot: 11,874 fewer bytes (about 45.5%). This is a script-size/startup parsing reduction, not a measured device CPU or battery percentage.

`test_rrtv_performance.py` exercises the runtime in a Node VM. It covers empty-body early exit, in-place homepage compaction and no-op serialization, ad-list cleanup, one-pass video flag rewriting, unchanged-video pass-through, navigation-tab payload, entitlement payload, and unmatched-route pass-through. Optimizer tests protect the nine-trigger inventory, idempotence and fail-closed behavior for partial or mixed URL inventories.

Upstream snapshot used for this batch: `zirawell/R-Store@46b5418b427525e3858eaf8be38c9a3f55e3692e`.
