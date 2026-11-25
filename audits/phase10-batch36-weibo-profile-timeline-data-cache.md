# Phase 10 batch 36 — Weibo profile timeline nested data cache

## Change
- Cache `item?.data` once for each top-level profile-timeline item.
- Cache `ii?.data` once for each nested feed/card item.
- Reuse the references for the existing break/continue predicates, ad cleanup, vote cleanup, birthday-feed filtering, and card-field deletion.
- Keep the original item order, filtering conditions, nested traversal, and mutation tracking unchanged.
- Reapply the exact transform through the Weibo upstream optimizer and fail closed on source drift.

## Validation
- Static regression checks enforce one cached reference declaration at each loop level and reject repeated property chains.
- Existing Weibo runtime fixtures remain in place; this pass does not claim a measured device-side CPU or battery improvement.
