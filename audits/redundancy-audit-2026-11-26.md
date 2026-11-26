# Repository redundancy audit — 2026-11-26

## Scope and method

Audited the `main` tree at commit `3adddca58e05db6613133309227c03d91d015225` (2026-11-26), before this cleanup.

The review checked:
- Whether each report under `audits/` is linked from the audit index.
- Whether repository files have identical Git blob contents.
- Whether runtime JavaScript assets are referenced by the published `allAdRewrite.plugin`, build/sync workflows, tests, or project documentation.
- Whether apparently old runtime assets have an active replacement in the current plugin or consolidated script.
- Whether root JSON files, source snapshots, patch files, and test compatibility aliases are used by CI/build paths.

This is a static reference and workflow audit. It does not claim device-side behavior or performance measurements.

## Findings

### Removed as orphaned runtime assets

| File | Evidence |
|---|---|
| `scripts/jingdong/jd-welcome.js` | No reference from the published plugin, workflows, tests, or docs. The active `scripts/jingdong/jd.js` handler explicitly handles `functionId=welcomeHome`; the plugin's JD response trigger points to this consolidated runtime. |
| `scripts/pupu/pupu-splash.js` | No reference from the published plugin, workflows, tests, or docs. The current plugin handles Pupu response endpoints using native response rules; its CI tests protect the checked-in local Pupu handlers and ensure there is no duplicate Romeo trigger. |

These two files were therefore dead copies rather than current build inputs or published runtime dependencies. Their deletion does not change `allAdRewrite.plugin`, active script URLs, MITM hostnames, or rule behavior.

### Retained after test/reference verification

- `scripts/didi/didi-ads.js`: retained. Although it is not a current production trigger, it is directly read by `tests/test_runtime_performance_audit.py` and `tests/test_baidumap_binary_performance.py` through the `tests/scripts` compatibility alias. The fixtures exercise legacy Didi paths including `pInTripLayout` and `common/v5`, which are not all represented in the current `scripts/didi/didi.js` handler. Deleting it would remove a regression fixture and silently discard coverage for those legacy route behaviors. It is not counted as an orphan.
- `patches/amap-rucu6-performance.patch`: retained; `.github/workflows/sync.yml` explicitly runs `git apply --check` and then applies this patch to the staged Amap source.
- `audits/`: retained; all 84 historical reports were linked from `audits/README.md`, with no missing links and no unindexed report files. The two similarly titled Xiaohongshu flat-stack reports describe separate batches and different optimizer/validation details; neither has identical blob content.
- `source-report.json`, `rule-provenance.json`, and `rule-history.json`: retained as previous-run baselines consumed by the sync workflow and provenance/risk-history tools.
- `romeo_resource_map.json`: retained as the mapping input for the Romeo staging tool and its tests.
- `optimization_invariants.json` and `optimization_output_invariants.json`: retained as fail-closed guard manifests used by optimization validation and tests.
- `sources/amap/`, `sources/alipayAdBlock/`, `sources/romeo_legacy/`, `sources/spotify/`, and corresponding `scripts/` assets: retained because build/sync steps stage, validate, patch, or integrate them.
- `scripts/cnftp/cnftp.js` and the non-R-Store Xiaohongshu source script: retained despite not being referenced by the current checked-in plugin snapshot, because the sync workflow regenerates them from pinned/upstream sources and the curated tests cover their optimizer/runtime behavior.
- `scripts/xiaohongshu/xiaohongshu-v4.js`: retained for now as a standalone legacy/test asset; it is not referenced by the current plugin, but it has a dedicated regression test and a workflow syntax check. Removing it would require an intentional retirement of that test-only compatibility surface, not just deleting an unnoticed orphan.
- Small entries under `tests/` that point back to repository resources: retained as compatibility aliases required by the relocated legacy test suite's path assumptions.

## Audit totals

At the audited revision:
- 246 tracked files across the repository.
- 85 files in `audits/`, including its index (84 report documents).
- 0 broken audit-index links.
- 0 unindexed audit reports.
- 0 duplicate Git blob contents across tracked files.
- 2 orphan runtime JavaScript assets removed by this cleanup.

After adding this report, the repository gains one audit record while losing two orphan scripts (net change: minus one tracked file). The Didi legacy file is preserved unchanged.

## Safety boundary

No production plugin content, script trigger, rule, MITM entry, source mapping, optimization implementation, or generated runtime asset was edited. The only runtime deletions are the two verified unreferenced files; the Didi regression fixture remains intact.
