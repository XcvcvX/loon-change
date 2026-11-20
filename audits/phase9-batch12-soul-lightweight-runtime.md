# Phase 9 Batch 12 — Soul lightweight runtime and lazy response serialization

## Finding

The active R-Store Soul handler is referenced by nine response triggers. The upstream source snapshot is 15,143 bytes and embeds a general-purpose `Env` runtime with storage, networking, notification, filesystem and compatibility helpers that the response handler does not use. The actual handler only needs the request URL, response body, JSON parsing/serialization, a small amount of logging and `$done`.

Several cleanup paths allocated replacement arrays with `Array.filter` / `Array.map`, while every response was serialized even when no field changed. The matched VIP information routes also commonly pass through unchanged; those responses need no re-serialization.

## Runtime change

- Replace the unused general-purpose `Env` wrapper with a response-only handler.
- Add an empty-body fast path and fail open on malformed JSON, preserving the original response rather than serializing the invalid body as a JSON string.
- Compact the game-card, core-card and nested second-card arrays in place while preserving order and the existing eight-title removal list.
- Preserve the existing `coreCards.style === 2` to `1` rewrite and `chat/limitInfo.data.limit = false` behavior.
- Track mutations and call `JSON.stringify` only when a field or array actually changes.
- Keep the nine plugin URL matchers, tags and `requires-body=true` declarations unchanged; only migrate their script asset URL.

## Coverage and limits

`test_soul_performance.py` runs the handler in a Node VM. It checks the no-body / invalid-JSON pass-through paths, delete-data behavior, limit flag updates, all three game-card compaction levels, style normalization, and no-op serialization. It also forbids `Array.filter` and `Array.map` at runtime.

The optimization reduces per-invocation JavaScript runtime parsing and temporary array creation; this is not a measured on-device CPU or battery percentage. The AES/decompression-heavy 163music handler was deliberately left unchanged in this batch because its cryptographic payload protocol needs separate end-to-end regression fixtures.

Upstream snapshot: `zirawell/R-Store@d0f4dd305bade7cc6a38e3445a768d72aaea0e5b`.
