# Phase 7 Batch 2 — Tencent HTTPDNS false-positive protection

## Proposed change

Exclude the ZhangLe Cai Fu Tong app-specific HTTPDNS block from the merged output, because the user does not use that app:

\`\`\`loon
request if ${url} ~= /^https?:\/\/119\.29\.29\.\d+\/d/ then reject(200)
\`\`\`

Upstream source: [fmz200/wool_scripts — blockAdsV2.plugin](https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAdsV2.plugin), current source line 7559 at review time.

## Evidence

Tencent Cloud's official HTTPDNS documentation identifies the \`/d\` path as its HTTPDNS query API and documents current service entry IPs:

- HTTP: \`119.29.29.98\`
- HTTPS: \`119.29.29.99\`

Tencent's product documentation also says the legacy \`119.29.29.29\` service IP was retired effective 2022-01-01. The current upstream matcher uses \`119.29.29.\\d+\`, so it matches both current service IPs, not only the retired address.

Official references:

- https://cloud.tencent.com/document/product/379
- https://cloud.tencent.com/document/product/379/95497
- https://cloud.tencent.com.cn/document/product/379/3522

Also remove the exact `119.29.29.*` MITM hostname declaration contributed by the same blockAdsV2 source section. The merger records this separately as `mitm_exclusions`; if another independent source declares the same hostname, that other source is not filtered.

## Exact scope and safety

- Only the exact normalized matcher \`^https?://119\\.29\\.29\\.\\d+/d\` with action \`reject(200)\` from the blockAdsV2 Rewrite feed is excluded.
- Other paths on \`119.29.29.98\`, other IP addresses, and different actions are not excluded.
- The paired `119.29.29.*` MITM wildcard is removed only from the blockAdsV2 source contribution; no other source's hostname declaration, other Rewrite, Script, Rule, source priority, or plugin setting is changed.
- The exclusion is recorded in \`rule-provenance.json\` under \`rewrite_exclusions\`, including the original line and source line number.
- A regression test verifies that the broad HTTPDNS matcher disappears while an unrelated path on the same IP remains.

## Review and rollback

This PR changes runtime rule behavior and must be reviewed by the repository owner before merging. To roll back, revert this PR; the upstream source remains unchanged and the exclusion can be removed from the merger.


## User-specific scope confirmation

The upstream Loon source places the Rewrite matcher and 119.29.29.* MITM declaration in the ZhangLeCaiFuTong.lpx feed. The merged blockAdsV2 copy is grouped under # > 涨乐财富通. The user confirmed they do not use this app, so both contributions are excluded. The MITM filter is source-specific: an identical hostname contributed by another independent source remains eligible for inclusion.
