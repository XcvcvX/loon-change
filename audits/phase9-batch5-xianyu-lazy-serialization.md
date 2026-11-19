# Phase 9 Batch 5 — Xianyu lazy response serialization

## Findings

The consolidated local Goofish/Xianyu response handler is referenced by eight active response triggers. The dedicated splash route already has a body-marker fast path and serializes only when a `realTimeAd` node is removed. The other route handlers parsed their response once but always serialized the full object at the common exit, even when the response already contained the cleaned shape and none of the filters or field replacements changed it.

## Runtime change

- Keep all eight response matchers, the splash fast path, existing URL branches, ad predicates, field values, and array ordering unchanged.
- Track actual array-length changes for in-place compaction; track property deletion and field clearing only when the serialized response would differ.
- Keep the existing normalization of recycle-card `showInfo.rightTagImage`; avoid declaring a change when it is already an empty object.
- Return `$done({})` for unchanged regular responses, allowing Loon to retain the original body without allocating a serialized response string.
- Serialize once when one of the existing cleanup mutations changes the response.

## Regression coverage

`test_xianyu_jd_upstream.py` now executes the actual local script in a Node VM. Eight no-op fixtures cover nextfresh, local home, whale module, profile, circle list, nearby item detail, search, and local flow; each must parse once and stringify zero times. Eight changed fixtures cover the same routes and verify that existing removal/reset behavior still runs and serializes once. The existing splash-specific no-parse/no-ad test remains intact.

The workflow now includes this Xianyu runtime test on both pull-request and main sync checks.

No URL trigger or MITM hostname was added or widened. This change removes full-body serialization for unchanged responses on the eight active routes; actual device CPU and battery savings have not been quantified without Loon on-device measurements.
