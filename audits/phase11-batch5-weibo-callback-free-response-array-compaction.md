# Phase 11 batch 5 — Weibo callback-free response-array compaction

## Scope
- Runtime: `scripts/weibo/weibo-rstore.js`
- Upstream regeneration: `tools/optimize_weibo_rstore.py`
- Seven response-array compaction call sites: publisher, direct messages, page cards, topic cards, footer menus, and topic channels

## Finding and change
The Weibo response handler retained seven generic `compactInPlace(items, keep)` call sites. Each response allocated predicate closures and invoked them once per element. The new mode-dispatched helper selects a specialized indexed loop once per array and removes those closures and indirect calls. It caches array length, preserves stable in-place compaction, and updates `modified` only when the array shrinks.

## Validation and safety
The upstream optimizer now carries marker, inventory, idempotence, and fail-closed checks. No matcher, trigger, script URL, `requires_body`, MITM hostname, filtering predicate, or item ordering was changed. This is a structural reduction only; no iPhone benchmark claim is made.
