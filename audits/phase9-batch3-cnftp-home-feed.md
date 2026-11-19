# Phase 9 Batch 3 — Youku home-feed response allocation reduction

## Findings

The repository-owned CNFTP response handler already used stable in-place compaction for Youku `columbus.home.query`, but `columbus.home.feed` still allocated an outer `newNodes1` array and a nested `newNode2` array for the homepage feed-card group.

## Runtime change

- Reuse `objData.nodes` and each `PHONE_FEED_CARD_GROUP.nodes` array.
- Remove only the two existing ad node types: `PHONE_FEED_CARD_S_AD` and `PHONE_H_UC_AD`.
- Preserve every outer node, original element order, and the existing response fields.
- Keep the existing one-parse/one-stringify response flow and all URL triggers, MITM entries, and enable behavior unchanged.

## Sync safety and regression coverage

- Extend `optimize_cnftp.py` so the same exact, fail-closed transformation is applied to fresh upstream CNFTP source before local publication.
- Reject upstream branch drift or missing expected ad-node predicates rather than guessing at a changed response schema.
- Add a Node VM fixture that executes the actual script, checks stable output membership/order, and verifies one JSON parse and one stringify.
- Add an optimizer fixture proving fresh upstream code receives the same transformation and remains idempotent.

No device-level CPU, memory, or battery percentage is claimed. The change removes two temporary arrays from the targeted home-feed branch; end-to-end impact still depends on the real response sizes and request frequency.
