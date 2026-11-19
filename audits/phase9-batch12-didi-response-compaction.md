# Phase 9 Batch 12 — Didi response array compaction

## Scope

The active Didi response script from R-Store contains seven assignments that replace an existing array with \`Array.filter(...)\`. The production rule builder retains either the two reviewed Didi triggers after local cleanup or all four original triggers when the supplemental cleanup source is absent.

## Runtime change

- Vendor the current R-Store \`didi.js\` snapshot through a reproducible optimizer pinned to the upstream commit used by each build.
- Replace all seven filter assignments with a stable, in-place read/write compaction pass. The helper preserves retained item order and original read indexes.
- Make the empty-body completion terminal so it cannot fall through into \`JSON.parse\`.
- Route only the existing Didi script-path URLs in the \`[Script]\` section to the local generated file. Accept only the verified two- or four-trigger inventory and fail closed on drift.
- Preserve all URL expressions, tags, \`requires-body\`, filtering predicates, allowed fields, MITM and other policy sections.

## Regression coverage

Unit tests verify the exact seven-call transformation, idempotency, source-inventory drift rejection and two/four trigger migration. Node VM tests disable \`Array.prototype.filter\` and exercise scene-list filtering, homepage/profile allowlists, OTA banner removal, and the empty-body path.

The optimization removes temporary result arrays from the seven reviewed filters. The deployed plugin's current retained Didi paths are covered by the same source; no measured device battery or CPU percentage is asserted.
