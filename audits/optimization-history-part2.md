# 历史优化审计记录（第二部分）

> 由原 audits/ 独立报告合并，正文保留。原始文件名作为小节标识。


---

<!-- 原文件：audits/phase9-batch2-baidumap-binary-performance.md -->

# Phase 9 Batch 2 — BaiduMap binary response allocation

## Findings

### BaiduMap (active local response script)

The BaiduMap binary response handler decoded the Protobuf Ads section, then allocated a temporary Result+Ads concatenation solely for MD5. It subsequently allocated the final response buffer and copied both sections again. In the Quantumult X branch it also sliced the just-created output ArrayBuffer, causing another full-size copy.

Changes:
- Reuse an incoming `Uint8Array` as a view instead of copying it through `new Uint8Array(existingTypedArray)`.
- Allocate one final payload buffer, place Result and rewritten Ads directly into it, and calculate MD5 over a zero-copy `subarray()` view.
- Encode the RepHead once with a fixed 32-character MD5 placeholder to determine its stable size, then encode the final MD5 and write the header into the same output buffer.
- Return the owned ArrayBuffer directly in the Quantumult X branch; the new output buffer always starts at byte offset zero.
- Guard the fixed-size header assumption so a schema/hash contract change fails explicitly instead of silently corrupting the binary offsets.

This removes the separate Result+Ads temporary buffer and the final Quantumult X ArrayBuffer slice copy. The final response still requires one output allocation and copies the two payload sections once.

### Taobao (active local response script)

Audit found one JSON parse and one stringify per matching response, no allocating `filter()`/`map()`, and O(1) clearing of ad-only arrays. The remaining splash-section/item traversal performs required field mutations. No speculative loop rewrite was made.

### Didi (local script is not active)

The current plugin's four Didi response triggers point to the upstream R-Store `didi.js`, not `scripts/didi/didi-ads.js`. Editing the local file would therefore have no runtime effect. The local helper already uses in-place filtering; defer a live Didi optimization until the plugin is intentionally switched to the repository-owned handler and parity is established.

## Regression coverage

`test_baidumap_binary_performance.py` executes the actual response-assembly helper with binary fixtures and checks payload order, MD5, RepHead lengths/offsets, and the no-intermediate-concatenation path. Static checks verify typed-array reuse and direct ArrayBuffer return.

No device-level CPU/battery percentages are claimed. Loon/Quantumult X real-device validation remains necessary for end-to-end performance and binary compatibility.


---

<!-- 原文件：audits/phase9-batch3-cnftp-home-feed.md -->

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


---

<!-- 原文件：audits/phase9-batch4-taobao-lazy-serialization.md -->

# Phase 9 Batch 4 — Taobao lazy response serialization

## Findings

The active repository-owned Taobao response script parsed each matched body once and always called `JSON.stringify`, including responses where no ad-related field was present and no object mutation occurred. Because the handler covers cloud-video configuration, Taobao splash payloads and Alibaba poplayer JSON, unchanged responses could still pay for a full response serialization and a replacement body string.

## Runtime change

- Keep the existing single `JSON.parse` and all URL branches, field predicates, values, and mutation order unchanged.
- Track whether a targeted field was actually modified.
- Return `$done({})` for unchanged responses so Loon retains the original body without allocating a serialized copy.
- Serialize once only when an existing ad-cleanup mutation has occurred.
- Preserve the empty-body fast path.

## Regression coverage

`test_baidumap_binary_performance.py` now executes the real Taobao script in a Node VM and tracks parse/stringify calls. It verifies zero stringify calls for no-op video, splash, and poplayer responses; one stringify for each changed response; and preservation of the original video, splash, and poplayer cleanup output.

No response matcher, MITM hostname, script trigger, or ad-removal predicate was changed. This removes a full JSON serialization/string allocation on no-op responses; real-device CPU/battery savings are not quantified without Loon device measurements.


---

<!-- 原文件：audits/phase9-batch5-xianyu-lazy-serialization.md -->

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


---

<!-- 原文件：audits/phase9-batch6-bilibili-lazy-serialization.md -->

# Phase 9 Batch 6 — Bilibili lazy response serialization

## Findings

The active repository-owned Bilibili JSON handler serves multiple response families through several local triggers. It compacts arrays in place, but always serialized the parsed object at the common exit even when the response already matched the desired tab, feed, profile, splash, PGC, or live-room state.

## Runtime change

- Keep every existing URL branch, ad predicate, field target value, and stable-order filter unchanged.
- Track array membership changes only when the compacted length changes; track tab sorting only when the filtered order is not already canonical.
- Track key deletion and field reset operations so already-clean responses are allowed through untouched.
- Return `$done({})` when no serialized content changed; keep one `JSON.stringify` when a cleanup actually changes the response.
- Preserve the existing same-index write guard in feed compaction and avoid creating any additional response arrays.

## Regression coverage

`test_bilibili_json_performance.py` now counts JSON parse/stringify calls in its Node VM. It checks no-op feed/story, tab, profile, splash, search, PGC, and live-room fixtures (one parse and zero stringify calls), plus changed tab/profile/live cases (one parse and one stringify call) and confirms the expected cleanup output. Existing array write-count tests continue to verify that kept feed items are not written back to identical positions.

No URL trigger, MITM hostname, ad-filter predicate, or field target value was widened. The change removes full-body serialization for already-clean Bilibili responses; it does not claim measured device CPU or battery percentages without on-device Loon measurements.


---

<!-- 原文件：audits/phase9-batch7-bilibili-lazy-serialization.md -->

# Phase 9 Batch 7 — Bilibili lazy response serialization

## Findings

The active Bilibili local response script is shared by multiple response trigger groups covering tabs, profile, feed, splash, PGC and live-room payloads. It used stable in-place compaction for several arrays, but still serialized every matched JSON response even when all fields and arrays were already in the expected state.

## Runtime change

- Retain every existing URL branch, ad predicate, VIP field, timestamp, list whitelist and output field target.
- Track array compaction by actual length changes, and track field deletion/reset only when the JSON-visible value changes.
- For navigation tabs, skip `Array.sort()` when the filtered list is already in canonical order; when sorting is required, keep the existing allowlist comparator and stable order.
- Return `$done({})` for unchanged matched responses and serialize once only when a cleanup mutation changes the response.
- Keep the existing same-index write guard for feed compaction.

## Regression coverage

`test_bilibili_json_performance.py` now tracks JSON.parse/JSON.stringify in the Node VM. No-op fixtures cover feed/story, tab navigation, iPad/profile pages, VIP status, splash, search, PGC modules and live-room data (one parse, zero stringify). Changed fixtures validate tab filtering/sorting, profile/VIP cleanup and live-room cleanup (one parse, one stringify). Existing feed tests continue to check zero same-index writes and the exact number of shifted array writes.

No response URL matcher, MITM hostname or ad-removal predicate was expanded. This removes response serialization for already-clean Bilibili payloads and avoids unnecessary sort work on already ordered tabs; device CPU/battery savings are not claimed without on-device Loon measurements.


---

<!-- 原文件：audits/phase9-batch8-baidumap-protobuf-noop.md -->

# Phase 9 Batch 8 — BaiduMap protobuf no-op fast path

## Finding

The BaiduMap binary response handler already reuses the incoming Uint8Array, keeps the unchanged Result segment as a zero-copy view, and assembles changed payloads in one allocation. However, it still re-encoded the Ads protobuf, recalculated MD5, rebuilt the complete binary response and rewrote the header even when the decoded Ads list contained no target banner/splash item requiring a field change.

## Runtime change

- Keep the existing binary trigger, protobuf schema, target type predicates, required start/end field checks and target timestamp values.
- Decode Ads once to inspect the existing content list.
- Set a mutation flag only when a matching item's start/end values differ from the existing target values.
- When Ads exists but no field changes, return `$done({})` and preserve the original response bytes; skip Ads encode, MD5, output allocation and header rewrite.
- When a target field changes, retain the existing one-allocation assembly path and MD5/header validation.

## Regression coverage

`test_baidumap_binary_performance.py` adds Node VM fixtures for non-target Ads, already-clean target Ads and changed target Ads. The first two must pass through without a replacement body; the changed case must still rebuild a valid response with the exact target timestamps and a 32-character MD5. Existing tests continue to protect byte order, offsets, lengths and hash correctness.

The optimization does not change MITM hosts, URL matching, binary-body mode, protobuf field targets or the ad-selection predicate. Savings apply only to already-clean/no-target binary responses; no device CPU or battery percentage is claimed without Loon on-device measurement.


---

<!-- 原文件：audits/phase9-batch9-xiaohongshu-v4-inplace-compaction.md -->

# Phase 9 Batch 9 — Xiaohongshu v4 in-place feed compaction

## Finding

The active Xiaohongshu v4 response handler still allocated replacement arrays in several response paths: search results, two follow-feed variants, homefeed, image-feed tags, and comment-cache deduplication. The homefeed path built a second array while retaining only ordinary notes; comment-cache updates used `concat()` followed by `filter()`, creating two additional arrays.

## Runtime change

- Add one stable `compactInPlace` helper that preserves retained item order and avoids same-index writes.
- Compact search results and follow-feed allowlists directly in their parsed response arrays.
- Compact homefeed in place while preserving the prior keep/drop conditions, retained null/undefined entries, and `related_ques` removal.
- Compact `interact_vote` tags in place.
- Append newly extracted comment live-photo/video entries into the existing cache array, then deduplicate that array in place with the same first-occurrence-wins behavior.
- Keep response triggers, ad predicates, cache keys, note IDs, video selection, and output payload fields unchanged.

## Regression coverage

`test_xiaohongshu_v4_performance.py` now disables `Array.prototype.filter` inside the Node VM and exercises search, both follow-feed routes, homefeed, image-feed tags, and comment live-photo cache deduplication. Existing v4 video-feed, cache, and download-permission tests remain in place.

The change removes transient array allocations; it does not change the selected items or cache ordering. No device CPU/battery percentage is claimed without on-device Loon measurement.


---

<!-- 原文件：audits/phase9-p0-amap-empty-body-guard.md -->

# Phase 9 P0 — Amap empty-body response guard

## Finding

The active Amap consolidated response script is referenced by ten response triggers. Its top-level empty-body condition called `$done({})` but then continued into `JSON.parse($response.body)`. An empty response could therefore still incur a failed parse after completion had been signalled.

## Change

Make the empty-body branch terminal by putting JSON parsing, all existing URL-specific mutations, and the final response completion inside the non-empty `else` block. Keep every URL matcher, ad predicate, field mutation, Protobuf-independent payload behavior and MITM scope unchanged.

## Regression coverage

A Node VM test supplies an empty body, counts JSON.parse calls, and requires exactly zero parses plus a pass-through `$done({})`. Existing Amap in-place compaction behavior tests remain unchanged and exercise non-empty payloads.

This removes the unnecessary parse attempt on empty bodies and prevents parse errors after completion. No device CPU or battery percentage is claimed without on-device measurement.


---

# Phase 9 Batch 10 — Jingdong lazy response serialization

## Finding

The consolidated Jingdong response handler parsed each matched response once but always serialized the complete object at the common exit, including already-clean splash, home, navigation, order and profile responses.

## Runtime change

- Keep all existing URL branches, allowlists, exclusions, field targets, and optional `jkds_enable` behavior unchanged.
- Track actual stable in-place array compaction, property deletion, array clearing, and field replacement.
- Return `$done({})` when the parsed response already matches the cleaned state; serialize once only after a real JSON-visible mutation.
- Keep the empty-body, invalid-JSON, and non-object pass-through guards.

## Regression coverage

`test_jd_lazy_serialization.py` executes the real script in a Node VM. It checks no-op pass-through and zero stringify calls for all seven URL families, one stringify for changed fixtures in all seven families, and the optional welcome-home exclusions. It also verifies the original cleanup outputs.

No URL trigger, MITM hostname, ad predicate, or target field value was expanded. The optimization removes a full response serialization and output-string allocation on already-clean matched responses; device CPU/battery savings remain unquantified without on-device Loon measurements.

---

# Phase 9 P0 — Xiaohongshu R-Store empty-body terminal guard

## Finding

The active local Xiaohongshu R-Store response handler called `$done({})` for an empty response body but did not stop execution. It continued into `JSON.parse(rsp_body)`, causing an unnecessary parse attempt and potentially logging an exception after the response had already been completed.

## Runtime change

- Make the empty-body branch terminal by placing URL dispatch, JSON parsing, response mutations and the final `$done` inside the non-empty `else` branch.
- Preserve every existing URL trigger, response transformation, cache key, ad predicate and output field.
- Update `optimize_xiaohongshu_rstore.py` so its already-optimized/idempotent path also restores this guard if a later upstream refresh removes it.

## Regression coverage

`test_xiaohongshu_rstore_performance.py` now executes the real script with an empty response body, counts JSON parsing, and requires exactly one `$done({})` with zero JSON.parse calls. Existing image-feed, homefeed, v4 video and deep-comment-tree fixtures continue to protect the existing transformations.

The change removes a failed parse attempt on empty bodies; it does not claim device CPU or battery percentages without on-device Loon measurements.

---

# Phase 10 P0 — Xiaohongshu single-pass comment cleanup and media extraction

## Finding

The active R-Store comment-response path traversed the entire response once in removeRedId(obj.data), then separately walked top-level comments and their direct sub-comments to normalize media types and extract Live Photo video URLs. Identical picture.video_info JSON strings were also parsed independently.

## Runtime change

- Replace the separate cleanup and extraction passes with one iterative traversal that removes red_id from the full response tree while processing only top-level comments and their direct sub-comments, matching the previous scope.
- Use a request-local Map keyed by the raw video_info string so duplicate payloads are parsed once per response.
- Keep the existing cache merge, note ID, Live Photo field names, output URL selection, and deeper-reply behavior unchanged.
- Remove the redundant inner empty-body completion check; the outer terminal guard remains the single empty-body exit.

## Regression coverage

The Node VM fixture verifies that top-level comments and direct sub-comments retain their prior transformations, deeper replies are not newly normalized, all nested red_id fields are removed, repeated video_info strings cause only one parse, and the existing deep-tree cleanup remains iterative.

This removes a redundant full-tree traversal and repeated parses of identical media payloads. It does not claim device CPU or battery percentages without on-device Loon measurements.



---

# Phase 10 P1 — Weibo feed and comment lazy response serialization

## Finding

The active local R-Store Weibo handler is referenced by ten response triggers and is a roughly 48 KB script. Its card-list and comment endpoints already compact arrays in place, but still serialized the complete parsed object for every matched response, including payloads that were already clean.

## Runtime change

- Add change tracking to the existing 32 in-place compaction loops and the shared compaction helper.
- Track the exact field deletions performed by the card-list and comment cleanup paths, including nested avatar metadata, comment decorations, and vote controls.
- For `/2/cardlist` and `/2/comments/build_comments` only, return `$done({})` when no array or field changed; serialize once when an existing cleanup actually changes the response.
- Keep all other Weibo response routes on their previous serialization path. Preserve every URL matcher, ad predicate, field target, and array ordering.
- Add the required marker and behavior checks to `optimization_invariants.json`; the upstream optimizer reproduces the guard on every sync and fails closed if the expected loop/delete inventory drifts.

## Regression coverage

The Node VM tests count JSON.parse/JSON.stringify calls. Clean card-list and comment fixtures must parse once and stringify zero times; changed fixtures must preserve their existing cleanup output and stringify once. Existing array compaction and filter behavior checks remain in place.

This removes redundant full-object serialization and its output-string allocation on already-clean card-list and comment responses. Real-device CPU and battery savings have not been quantified without Loon on-device measurements.


---

# Phase 11 P0 — BaiduMap deferred MD5 initialization

## Finding

The active BaiduMap binary response handler includes a roughly 12 KB MD5 implementation. It initialized that implementation eagerly on every matching binary response, even though hashing is only needed when a targeted ad's start/end fields actually change and the response body is rebuilt.

## Runtime change

- Move the existing MD5 implementation into a function without changing its algorithm or exports.
- Initialize it only inside the modified-Ads response branch, at the point where the final binary response is assembled.
- Responses without an Ads section, with non-target ads, or with already-clean target values now skip MD5 library initialization entirely.
- Keep protobuf decoding, ad predicates, target timestamps, response header offsets, payload bytes, and MD5 output unchanged.

## Regression coverage

The Node VM tests instrument the lazy initializer. All three no-op cases must report zero MD5 initializations; the changed-target case must report exactly one. Existing binary assembly tests continue to verify payload order, metadata lengths, and the final MD5 value.

The optimization avoids executing the MD5 implementation on no-op responses. The source code remains present for changed responses; real-device CPU and battery deltas have not been quantified without Loon on-device measurements.
