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

### Reclassified from production script assets to test fixtures

Three old standalone JavaScript snapshots were still referenced by regression tests. They are not current production triggers, but deleting the contents outright would destroy useful historical coverage. The files have therefore been moved unchanged from `scripts/` into `tests/fixtures/legacy/`, and all tests now read them from that explicit fixture location.

| Previous location | Test-fixture location | Why retained |
|---|---|---|
| `scripts/didi/didi-ads.js` | `tests/fixtures/legacy/didi-ads.js` | Two regression tests exercise the old response handler, including `pInTripLayout` and `common/v5` paths that are not all represented by the current consolidated Didi handler. |
| `scripts/jingdong/jd-welcome.js` | `tests/fixtures/legacy/jd-welcome.js` | A JD consolidation test keeps the optional welcome-page filter's legacy field allow/deny behavior and safe-parse coverage. The active plugin routes JD responses to the consolidated `scripts/jingdong/jd.js`. |
| `scripts/pupu/pupu-splash.js` | `tests/fixtures/legacy/pupu-splash.js` | A regression test checks the legacy handler's parse/serialize contract and endpoint-branch inventory. The published plugin currently uses native response rules for Pupu. |

Moving these files changes only repository organization. The contents are byte-for-byte preserved, no test was skipped or weakened, and no production trigger points to the test-fixture paths.

### Audited and deliberately retained elsewhere

- `patches/amap-rucu6-performance.patch`: retained; `.github/workflows/sync.yml` explicitly runs `git apply --check` and then applies this patch to the staged Amap source.
- `audits/`: retained; all 84 historical reports were linked from `audits/README.md`, with no missing links and no unindexed report files. The two similarly titled Xiaohongshu flat-stack reports describe separate batches and different optimizer/validation details; neither has identical blob content.
- `source-report.json`, `rule-provenance.json`, and `rule-history.json`: retained as previous-run baselines consumed by the sync workflow and provenance/risk-history tools.
- `romeo_resource_map.json`: retained as the mapping input for the Romeo staging tool and its tests.
- `optimization_invariants.json` and `optimization_output_invariants.json`: retained as fail-closed guard manifests used by optimization validation and tests.
- `sources/amap/`, `sources/alipayAdBlock/`, `sources/romeo_legacy/`, `sources/spotify/`, and corresponding active `scripts/` assets: retained because build/sync steps stage, validate, patch, or integrate them.
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

The cleanup adds one audit report and one fixture README, while moving three legacy snapshots out of the production `scripts/` tree. It does not discard their contents or alter the generated plugin.

## Safety boundary

No production plugin content, script trigger, rule, MITM entry, source mapping, optimization implementation, or generated runtime asset was edited. The only runtime-directory changes are moves of three test-only legacy snapshots into `tests/fixtures/legacy/`; production behavior is unchanged.
