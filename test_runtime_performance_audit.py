import tempfile
import unittest
from pathlib import Path
from runtime_performance_audit import audit_plugin, render_markdown

class RuntimePerformanceAuditTests(unittest.TestCase):
    def test_counts_response_body_triggers_and_remote_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "http-response ^https://api.example.com/a script-path=https://raw.githubusercontent.com/org/repo/main/a.js,requires-body=true\n"
                "http-response ^https://api.example.com/b script-path=https://raw.githubusercontent.com/org/repo/main/a.js,requires-body=true\n"
                "response if ${url} ~= /^https://api.example.com/d then script(\"https://raw.githubusercontent.com/org/repo/main/c.js\") with requires_body=true\n"
                "http-request ^https://api.example.com/c script-path=https://cdn.example.com/b.js\n",
                encoding="utf-8",
            )
            (root / "sample.js").write_text(
                "const a = JSON.parse(body); const b = JSON.parse(body);", encoding="utf-8"
            )
            report = audit_plugin(plugin, root)
            summary = report["summary"]
            self.assertEqual(summary["response_script_triggers"], 3)
            self.assertEqual(summary["http_response_script_triggers"], 2)
            self.assertEqual(summary["inline_response_script_triggers"], 1)
            self.assertEqual(summary["response_script_requires_body_true"], 3)
            self.assertEqual(summary["http_response_requires_body_true"], 2)
            self.assertEqual(summary["inline_response_requires_body_true"], 1)
            self.assertEqual(summary["unique_remote_script_urls"], 3)
            self.assertEqual(summary["mutable_branch_remote_urls"], 2)
            self.assertEqual(summary["non_github_remote_urls"], 1)
            self.assertEqual(summary["local_js_json_parse_calls"], 2)
            self.assertEqual(summary["repeated_json_parse_expressions"], 1)
            self.assertIn("Response-script candidates (not per-response execution counts)", render_markdown(report))

    def test_duplicate_trigger_group_is_reported_not_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/a.js\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/a.js\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["duplicate_script_trigger_groups"], 1)
            self.assertEqual(len(report["duplicate_script_triggers"][0]["lines"]), 2)

    def test_same_response_pattern_across_different_scripts_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "response if ${url} ~= /^https://api.example.com/a then script(\"https://example.com/a.js\") with requires_body=true\n"
                "response if ${url} ~= /^https://api.example.com/a then script(\"https://example.com/b.js\") with requires_body=true\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["duplicate_script_trigger_groups"], 0)
            self.assertEqual(report["summary"]["duplicate_response_patterns_across_scripts"], 1)
            self.assertIn("Duplicate response patterns across scripts", render_markdown(report))

    def test_xiaohongshu_feed_avoids_json_round_trip_and_payload_logging(self):
        source = Path("scripts/xiaohongshu/xiaohongshu-v4.js").read_text(encoding="utf-8")
        self.assertIn("imageEnhance(images_list)", source)
        self.assertNotIn("imageEnhance(JSON.stringify(images_list))", source)
        self.assertNotIn("JSON.parse(jsonStr)", source)
        self.assertNotIn("打印原body", source)
        self.assertNotIn("写入缓存val：", source)


    def test_xiaohongshu_live_photo_cache_stores_only_required_metadata(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xiaohongshu runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("xiaohongshu", "xiaohongshu-v4.js")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const store = Object.create(null);
function run(url, body) {
  let doneResult;
  const context = {
    $loon: {},
    $request: { url },
    $response: { body: JSON.stringify(body) },
    $persistentStore: {
      read(key) { return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null; },
      write(value, key) { store[key] = value; return true; }
    },
    $done(value) { doneResult = value; },
    console: { log() {} }
  };
  vm.runInNewContext(source, context);
  return doneResult;
}
const fullImages = [
  { file_id: "ordinary", url: "https://img.example/ordinary.jpg", large_unused_metadata: "x".repeat(12000) },
  {
    file_id: "live-file", live_photo_file_id: "live-file",
    live_photo: { media: { video_id: "video-1", stream: { h265: [
      { master_url: "https://video.example/live.mp4?token=secret", width: 2160, height: 3840, bitrate: 9000000 }
    ] } } },
    unrelated_metadata: "y".repeat(12000)
  }
];
run("https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?test=1", {
  data: [{ note_list: [{ images_list: fullImages }] }]
});
const cacheKey = "fmz200.xiaohongshu.feed.rsp";
if (!store[cacheKey]) throw new Error("live-photo cache was not written");
const cache = JSON.parse(store[cacheKey]);
if (cache.length !== 1) throw new Error("cache should contain only live-photo entries");
const keys = Object.keys(cache[0]).sort().join(",");
if (keys !== "live_photo_file_id,url,video_id") throw new Error("cache retained unnecessary fields: " + keys);
if (store[cacheKey].length >= JSON.stringify(fullImages).length / 2) throw new Error("cache was not materially compacted");
const result = run("https://edith.xiaohongshu.com/api/sns/v1/note/live_photo/save", {
  data: { datas: [{ file_id: "live-file", url: "" }] }
});
if (!result || typeof result.body !== "string") throw new Error("live-photo save response was not produced");
const saved = JSON.parse(result.body);
if (saved.data.datas[0].url !== "https://video.example/live.mp4?token=secret") throw new Error("live-photo URL restoration changed");
if (saved.data.datas[0].author !== "@fmz200") throw new Error("live-photo author marker changed");
'''
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)

    def test_xiaohongshu_image_enhance_skips_unrelated_strings(self):
        import shutil
        import subprocess
        from pathlib import Path

        source = Path(__file__).with_name("scripts").joinpath("xiaohongshu", "xiaohongshu-v4.js").read_text(encoding="utf-8")
        self.assertIn('if (!value.includes("imageView2/2")) return value;', source)
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xiaohongshu runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("xiaohongshu", "xiaohongshu-v4.js")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
let result;
const context = {
  $loon: {},
  $request: { url: "https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?test=1" },
  $response: { body: JSON.stringify({ data: [{ note_list: [{
    note_text: "ordinary description imageView2 text",
    images_list: [{
      url_default: "https://img.example/a.jpg?imageView2/2/w/1080/format/jpg",
      image_id: "imageView2/2 is an opaque identifier",
      description: "This ordinary metadata string should remain unchanged"
    }]
  }] }] }) },
  $persistentStore: { read() { return null; }, write() { return true; } },
  $done(value) { result = value; },
  console: { log() {} }
};
vm.runInNewContext(source, context);
const body = JSON.parse(result.body);
const image = body.data[0].note_list[0].images_list[0];
if (!image.url_default.includes("imageView2/2/w/2160/format")) throw new Error("image URL quality rewrite was lost");
if (image.description !== "This ordinary metadata string should remain unchanged") throw new Error("unrelated metadata was modified");
if (image.image_id !== "imageView2/2 is an opaque identifier") throw new Error("non-URL token was modified");
if (body.data[0].note_list[0].note_text !== "ordinary description imageView2 text") throw new Error("note text was modified");
'''
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)


    def test_amap_suggestion_filters_use_direct_scalar_checks(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Amap runtime integration test")
        source_path = Path(__file__).with_name("sources").joinpath("amap", "rucu6_amap.js")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(body) {
  let result;
  const context = {
    $request: { url: "https://m5.amap.com/ws/shield/search_poi/sug?keywords=test" },
    $response: { body: JSON.stringify(body) },
    $done(value) { result = value; },
    console: { log() {} }
  };
  vm.runInNewContext(source, context);
  if (!result || typeof result.body !== "string") throw new Error("Amap response was not returned");
  return JSON.parse(result.body);
}
const direct = run({ tip_list: [
  { id: 1, tip: { datatype_spec: "12" } },
  { id: 2, tip: { result_type: "ad" } },
  { id: 3, tip: { result_type: "poi_ad" } },
  { id: 4, tip: { result_type: "toplist" } },
  { id: 5, tip: { task_tag: "exct_query_sug_merge_theme" } },
  { id: 6, tip: { task_tag: "query_sug_merge_theme" } },
  { id: 7, tip: { task_tag: "sp" } },
  { id: 8, tip: { result_type: "normal", task_tag: "poi" } }
] });
if (direct.tip_list.length !== 1 || direct.tip_list[0].id !== 8) throw new Error("direct suggestion filter behavior changed");
const nested = run({ city_list: [
  { city: "A", tip_list: [
    { id: 1, tip: { datatype_spec: "12" } },
    { id: 2, tip: { result_type: "ad" } },
    { id: 3, tip: { result_type: "poi_ad" } },
    { id: 4, tip: { result_type: "normal" } }
  ] }
] });
if (nested.city_list[0].tip_list.length !== 1 || nested.city_list[0].tip_list[0].id !== 4) throw new Error("nested suggestion filter behavior changed");
'''
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)



    def test_jd_person_info_floor_cleanup_uses_single_pass_and_preserves_behavior(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Jingdong runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("jingdong", "jd.js")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
let result;
const context = {
  $request: { url: "https://api.m.jd.com/client.action?functionId=personinfoBusiness" },
  $response: { body: JSON.stringify({
    floors: [
      { mId: "basefloorinfo", data: { commonPopup: {}, commonTips: [1], commonWindows: [2], floatLayer: {} } },
      { mId: "bigSaleFloor", data: { keep: true } },
      { mId: "userinfo", data: { newPlusBlackCard: {} } },
      null,
      { mId: "normalFloor", data: { keep: true } }
    ],
    others: { floors: [
      { mId: "noticeFloor", data: {} },
      { mId: "orderIdFloor", data: { commentRemindInfo: { infos: [1, 2] } } }
    ] }
  }) },
  $done(value) { result = value; },
  console: { log() {} }
};
vm.runInNewContext(source, context);
if (!result || typeof result.body !== "string") throw new Error("JD response was not returned");
const body = JSON.parse(result.body);
if (body.floors.length !== 4) throw new Error("excluded floors or null floor behavior changed");
if (body.floors[0].mId !== "basefloorinfo" || body.floors[1].mId !== "userinfo" || body.floors[2] !== null || body.floors[3].mId !== "normalFloor") throw new Error("floor order or retained entries changed");
if (body.floors[0].data.commonPopup !== undefined || body.floors[0].data.floatLayer !== undefined) throw new Error("base floor cleanup changed");
if (body.floors[0].data.commonTips.length || body.floors[0].data.commonWindows.length) throw new Error("base floor arrays were not cleared");
if (body.floors[1].data.newPlusBlackCard !== undefined) throw new Error("userinfo floor cleanup changed");
if (body.others.floors.length !== 1 || body.others.floors[0].data.commentRemindInfo.infos.length !== 0) throw new Error("others floors cleanup changed");
'''
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)

    def test_meituan_tab_area_cleanup_uses_single_pass_and_keeps_required_tabs(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Meituan runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("meituan", "meituan.js")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(tabArea) {
  let result;
  const context = {
    $request: { url: "https://apimobile.meituan.com/aggroup/indexTab" },
    $response: { body: JSON.stringify({ data: { resource: { tabArea } } }) },
    $done(value) { result = value; },
    console: { log() {} }
  };
  vm.runInNewContext(source, context);
  return result;
}
const cleaned = run([
  { tabName: "homepage", id: 1 },
  { tabName: "video", id: 2 },
  { tabName: "mine", id: 3 },
  { tabName: "xiaotuan", id: 4 },
  { tabName: "nearby", id: 5 },
  null
]);
if (!cleaned || typeof cleaned.body !== "string") throw new Error("expected a cleaned Meituan response");
const tabs = JSON.parse(cleaned.body).data.resource.tabArea;
if (tabs.length !== 4 || tabs[0].tabName !== "homepage" || tabs[1].tabName !== "mine" || tabs[2].tabName !== "nearby" || tabs[3] !== null) throw new Error("tab filtering or order changed");
const unchanged = run([{ tabName: "homepage" }, { tabName: "video" }, { tabName: "nearby" }]);
if (!unchanged || Object.keys(unchanged).length !== 0) throw new Error("missing required tab should leave response untouched");
'''
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)

    def test_same_parse_identifier_in_separate_blocks_is_not_reported_as_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text("[Script]\n", encoding="utf-8")
            (root / "separate-scopes.js").write_text(
                'if (first) { const cache = get("first"); JSON.parse(cache); }\n'
                'if (second) { const cache = get("second"); JSON.parse(cache); }',
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["local_js_json_parse_calls"], 2)
            self.assertEqual(report["summary"]["repeated_json_parse_expressions"], 0)

    def test_response_candidate_counts_explain_loom_first_match_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/a.js,requires-body=true\n"
                "http-response ^https://api.example.com/a script-path=https://example.com/b.js,requires-body=true\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["response_script_triggers"], 2)
            self.assertIn("最多选择一条 Response Script", " ".join(report["notes"]))
            self.assertIn("not per-response execution counts", render_markdown(report))

    def test_repeated_json_stringify_is_reported_only_within_same_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text("[Script]\n", encoding="utf-8")
            (root / "stringify.js").write_text(
                "const first = JSON.stringify(payload); const second = JSON.stringify(payload);\n"
                "if (other) { const third = JSON.stringify(payload); }", encoding="utf-8"
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["local_js_json_stringify_calls"], 3)
            self.assertEqual(report["summary"]["repeated_json_stringify_expressions"], 1)
            item = report["local_js_json_parse"][0]
            self.assertEqual(item["repeated_stringify_expressions"][0]["count"], 2)
            self.assertIn("JSON.stringify", render_markdown(report))

    def test_commit_pinned_url_is_not_mutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "test.plugin"
            plugin.write_text(
                "[Script]\nhttp-response ^https://api.example.com/a script-path="
                "https://raw.githubusercontent.com/org/repo/0123456789abcdef0123456789abcdef01234567/a.js\n",
                encoding="utf-8",
            )
            report = audit_plugin(plugin, root)
            self.assertEqual(report["summary"]["mutable_branch_remote_urls"], 0)


    def test_goofish_home_sections_filters_are_combined_into_one_pass(self):
        plugin = Path(__file__).with_name("allAdRewrite.plugin").read_text(encoding="utf-8")
        line = next(
            (item for item in plugin.splitlines()
             if "idlehome" in item and "nextfresh" in item and ".data.sections" in item),
            None,
        )
        self.assertIsNotNone(line, "Goofish home-feed response rule must remain present")
        self.assertEqual(line.count(".data.sections |= map(select("), 1)
        self.assertIn("homeMultiBanner", line)
        self.assertIn("mamaAD", line)
        self.assertIn("idlefish_home_new_commodity_card", line)
        self.assertIn("fish_home_tags_item_card", line)
        self.assertIn(".data.homeTopList |= map(select(.sectionType", line)


    def test_xiaohongshu_hot_paths_use_linear_lookup_and_iterative_traversal(self):
        import shutil
        import subprocess

        source_path = Path(__file__).with_name("scripts").joinpath("xiaohongshu", "xiaohongshu-v4.js")
        source = source_path.read_text(encoding="utf-8")
        self.assertIn("const byFileId = new Map();", source)
        self.assertNotIn("collectionB.find", source)
        self.assertNotIn(".sort(sortStream)", source)
        self.assertNotIn("replaceRedIdWithFmz200(obj[key])", source)
        self.assertNotIn("value[i] = visit(value[i])", source)

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xiaohongshu hot-path integration test")
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const store = Object.create(null);
function run(url, body) {
  let result;
  const context = {
    $loon: {},
    $request: { url },
    $response: { body },
    $persistentStore: {
      read(key) { return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null; },
      write(value, key) { store[key] = value; return true; }
    },
    $done(value) { result = value; },
    console: { log() {} }
  };
  vm.runInNewContext(source, context);
  return result;
}

// H265 retains priority; within H265, resolution then average bitrate wins.
run("https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?test=1", JSON.stringify({
  data: [{
    id: "note-1",
    model_type: "note",
    video_info_v2: { media: { stream: {
      h265: [
        { master_url: "https://video.example/low.mp4", width: 720, height: 1280, avg_bitrate: 1000 },
        { master_url: "https://video.example/best.mp4", width: 2160, height: 3840, avg_bitrate: 9000 },
        { master_url: "https://video.example/best-numeric.mp4", width: 2160, height: 3840, avg_bitrate: "10000" },
        { width: 4320, height: 7680, avg_bitrate: 99999 }
      ],
      h264: [{ master_url: "https://video.example/h264.mp4", width: 4320, height: 7680, avg_bitrate: 99999 }]
    } } }
  }]
}));
const feedCache = JSON.parse(store.redBookVideoFeed);
if (feedCache.length !== 1 || feedCache[0].url !== "https://video.example/best-numeric.mp4") {
  throw new Error("linear stream selection changed H265 priority or ranking");
}

// Indexed replacement preserves Array.find()'s first-match behavior.
store["fmz200.xiaohongshu.feed.rsp"] = JSON.stringify([
  { live_photo_file_id: "file-1", video_id: "v1", url: "https://video.example/first.mp4?token=1" },
  { live_photo_file_id: "file-1", video_id: "v2", url: "https://video.example/second.mp4?token=2" }
]);
const saved = run("https://edith.xiaohongshu.com/api/sns/v1/note/live_photo/save", JSON.stringify({
  data: { datas: [{ file_id: "file-1", url: "" }] }
}));
if (JSON.parse(saved.body).data.datas[0].url !== "https://video.example/first.mp4?token=1") {
  throw new Error("indexed cache lookup no longer preserves first match");
}

// Deep comment payload must not depend on the JavaScript call stack.
const depth = 4000;
const nested = '{"data":' + '{"child":'.repeat(depth) + '{"red_id":"deep-id"}' + '}'.repeat(depth) + '}';
const deepResult = run("https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?test=1", nested);
if (!deepResult || !deepResult.body.includes('"fmz200":"deep-id"') || deepResult.body.includes('"red_id"')) {
  throw new Error("iterative red_id traversal failed on deeply nested data");
}

// Deep image metadata still receives URL enhancement through iterative traversal.
const deepImage = '{"data":[{"note_list":[{"images_list":[' +
  '{"child":'.repeat(depth) + '{"url":"https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"}' +
  '}'.repeat(depth) + ']}]}]}';
const imageResult = run("https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?test=1", deepImage);
if (!imageResult || !imageResult.body.includes("imageView2/2/w/2160/format")) {
  throw new Error("iterative image traversal failed on deeply nested data");
}
"""
        completed = subprocess.run([node, "-e", harness, str(source_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()


class BilibiliLocalJsonRuntimePerformanceTests(unittest.TestCase):
    def test_json_cleaner_uses_one_parse_stringify_and_in_place_array_compaction(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Bilibili runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("bilibili", "bilibili-json.js")
        source = source_path.read_text(encoding="utf-8")
        self.assertNotIn(".filter(", source)
        self.assertNotIn("newItems", source)
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)

        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const cases = [
  {
    url: "https://app.bilibili.com/x/v3/feed/index?test=1",
    data: { data: { items: [{ card_goto: "av", id: 1 }, { card_goto: "banner", id: 2 }, { card_goto: "av", id: 3 }], config: { toast: { has_toast: true } } } },
    check(body) {
      if (body.data.items.length !== 2 || body.data.items[0].id !== 1 || body.data.items[1].id !== 3 || body.data.config.toast.has_toast !== false) throw new Error("feed result mismatch");
    }
  },
  {
    url: "https://app.bilibili.com/x/v3/feed/index/story?test=1",
    data: { data: { items: [{ ad_info: null }, { card_goto: "vertical_live" }, { card_goto: "vertical_ad_av" }, { card_goto: "organic", creative_entrance: {}, story_cart_icon: {} }] } },
    check(body) {
      if (body.data.items.length !== 1 || body.data.items[0].card_goto !== "organic" || "creative_entrance" in body.data.items[0] || "story_cart_icon" in body.data.items[0]) throw new Error("story result mismatch");
    }
  },
  {
    url: "https://app.bilibili.com/x/v3/account/mine?test=1",
    data: { data: { sections_v2: [
      { style: 1, title: "创作中心", items: [] },
      { style: 2, title: "更多服务", items: [{ uri: "bilibili://user_center/feedback" }, { uri: "bilibili://user_center/setting" }, { uri: "bilibili://user_center/other" }] },
      { style: 1, title: "常规服务", button: {} },
      { style: 3, title: "其他" }
    ] } },
    check(body) {
      const sections = body.data.sections_v2;
      if (sections.length !== 2 || sections[0].items.length !== 2 || sections[0].title !== undefined || sections[1].title !== "常规服务" || "button" in sections[1]) throw new Error("account result mismatch");
    }
  },
  {
    url: "https://app.bilibili.com/x/resource/show/tab/v1?test=1",
    data: { data: { bottom: [{name:"我的"},{name:"其他"},{name:"首页"},{name:"首页"}], tab: [{name:"动画"},{name:"推荐"},{name:"未知"}], top: [{name:"动态"},{name:"消息",pos:9}] } },
    check(body) {
      if (body.data.bottom.map(x=>x.name).join(",") !== "首页,首页,我的" || body.data.tab.map(x=>x.name).join(",") !== "推荐,动画" || body.data.top.length !== 1 || body.data.top[0].pos !== 1) throw new Error("tab result mismatch");
    }
  },
  {
    url: "https://api.bilibili.com/pgc/page/bangumi?test=1",
    data: { result: { modules: [{ style:"banner", items:[{link:"https://play.example"},{link:"https://other.example"}] }, {style:"function",items:[{blink:"bilibili://x"},{blink:"https://x"}]}] } },
    check(body) {
      const modules = body.result.modules;
      if (modules[0].items.length !== 1 || modules[1].items.length !== 1) throw new Error("pgc result mismatch");
    }
  },
  {
    url: "https://api.live.bilibili.com/xlive/app-room/v2/index/getInfoByRoom?test=1",
    data: { data: { activity_banner_info:{}, new_tab_info:{outer_list:[{biz_id:33},{biz_id:1}]}, shopping_info:{is_show:1} } },
    check(body) {
      if (body.data.new_tab_info.outer_list.length !== 1 || body.data.new_tab_info.outer_list[0].biz_id !== 1 || body.data.shopping_info.is_show !== 0 || "activity_banner_info" in body.data) throw new Error("live result mismatch");
    }
  }
];
for (const item of cases) {
  let parseCalls = 0, stringifyCalls = 0, doneResult;
  const trackedJSON = {
    parse(...args) { parseCalls++; return JSON.parse(...args); },
    stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
  };
  const context = {
    JSON: trackedJSON,
    $request: { url: item.url },
    $response: { body: JSON.stringify(item.data) },
    $done(value) { doneResult = value; }
  };
  vm.runInNewContext(source, context);
  if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error(item.url + " parse/stringify count " + parseCalls + "/" + stringifyCalls);
  item.check(JSON.parse(doneResult.body));
}
let emptyDone;
vm.runInNewContext(source, {
  JSON,
  $request: { url: "https://app.bilibili.com/x/v3/feed/index?test=empty" },
  $response: { body: "" },
  $done(value) { emptyDone = value; }
});
if (!emptyDone || Object.keys(emptyDone).length !== 0) throw new Error("empty body fast path changed");
'''
        result = subprocess.run([node, "-e", harness, str(source_path)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


class DidiLocalJsonRuntimePerformanceTests(unittest.TestCase):
    def test_json_cleaner_uses_one_parse_stringify_and_in_place_array_compaction(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Didi runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("didi", "didi-ads.js")
        source = source_path.read_text(encoding="utf-8")
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".forEach(", source)
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)

        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const cases = [
  {
    url: "https://common.diditaxi.com.cn/other/pGetSceneList",
    data: { data: { scene_list: [{text:"优惠商城"},{text:"快车"}], show_data:[{scene_ids:["scene_coupon_mall","scene_ride"]},{scene_ids:["scene_ride"]}] } },
    check(body) {
      if (body.data.scene_list.length !== 1 || body.data.scene_list[0].text !== "快车" || body.data.show_data[0].scene_ids.length !== 1) throw new Error("scene list result mismatch");
    }
  },
  {
    url: "https://common.diditaxi.com.cn/homepage/v1/core",
    data: { data: { order_cards:{nav_list_card:{data:[{nav_id:"dache_anycar"},{nav_id:"other"}]}}, disorder_cards:{bottom_nav_list:{data:[{id:"home_page"},{id:"other"}]}} } },
    check(body) {
      if (body.data.order_cards.nav_list_card.data.length !== 1 || body.data.disorder_cards.bottom_nav_list.data.length !== 1) throw new Error("homepage result mismatch");
    }
  },
  {
    url: "https://api.diditaxi.com.cn/ota/na/yuantu/infoList",
    data: { data: { disorder_cards:{top_banner_card:{data:[{T:"yuentu_top_banner"},{T:"keep"}]}} } },
    check(body) {
      if (body.data.disorder_cards.top_banner_card.data.length !== 1 || body.data.disorder_cards.top_banner_card.data[0].T !== "keep") throw new Error("OTA result mismatch");
    }
  },
  {
    url: "https://api.udache.com/gulfstream/passenger-center/v2/other/pInTripLayout",
    data: { data: { order_components:[{name:"passenger_common_casper"},{name:"keep"},{name:"keep2"}] } },
    check(body) {
      if (body.data.order_components.length !== 2 || body.data.order_components[0].name !== "keep") throw new Error("trip layout result mismatch");
    }
  },
  {
    url: "https://common.diditaxi.com.cn/usercenter/me",
    data: { data: { cards:[
      {title:"金融服务"},
      {title:"保留卡片",tag:"normal"},
      {title:"钱包",tag:"wallet",items:[{title:"优惠券"},{title:"其他"}],card_type:4,bottom_items:[{title:"省钱套餐"},{title:"天天神券"},{title:"其他"}]}
    ] } },
    check(body) {
      const cards = body.data.cards;
      if (cards.length !== 2 || cards[0].title !== "保留卡片" || cards[1].items.length !== 1 || cards[1].bottom_items.length !== 2) throw new Error("usercenter result mismatch");
    }
  },
  {
    url: "https://common.diditaxi.com.cn/common/v5",
    data: { data: { sections:[{sectionId:"center_v2"},{sectionId:"other"},{sectionId:"core_function"}] } },
    check(body) {
      if (body.data.sections.length !== 2 || body.data.sections[0].sectionId !== "center_v2") throw new Error("mini program result mismatch");
    }
  }
];
for (const item of cases) {
  let parseCalls = 0, stringifyCalls = 0, doneResult;
  const trackedJSON = {
    parse(...args) { parseCalls++; return JSON.parse(...args); },
    stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
  };
  vm.runInNewContext(source, {
    JSON: trackedJSON,
    $request: { url: item.url },
    $response: { body: JSON.stringify(item.data) },
    $done(value) { doneResult = value; }
  });
  if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error(item.url + " parse/stringify count " + parseCalls + "/" + stringifyCalls);
  item.check(JSON.parse(doneResult.body));
}
let emptyDone;
vm.runInNewContext(source, {
  JSON,
  $request: { url: "https://common.diditaxi.com.cn/common/v5" },
  $response: { body: "" },
  $done(value) { emptyDone = value; }
});
if (!emptyDone || Object.keys(emptyDone).length !== 0) throw new Error("empty body fast path changed");
'''
        result = subprocess.run([node, "-e", harness, str(source_path)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


class BaiduMapZeroCopyProtobufRuntimeTests(unittest.TestCase):
    def test_binary_handler_preserves_result_bytes_and_updates_only_ad_dates(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Baidu Map protobuf runtime test")
        source_path = Path(__file__).with_name("scripts").joinpath("baidumap", "baidu-map-protobuf.js")
        source = source_path.read_text(encoding="utf-8")
        app = source[source.index("const isQuanX ="):]
        self.assertNotIn("binaryBody.slice(", app)
        self.assertNotIn("Uint8Array.from([...", app)
        self.assertNotIn("resultType.decode", app)
        self.assertNotIn("console.log(", app)
        self.assertEqual(app.count("binaryBody.subarray("), 2)

        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const appStart = source.indexOf("const isQuanX =");
const schemaContext = { console: { log() {} }, Uint8Array, ArrayBuffer, DataView };
vm.runInNewContext(source.slice(0, appStart) + "\nglobalThis.__testRoot = baiduMapRoot;", schemaContext);
const root = schemaContext.__testRoot;
const resultType = root.lookupType("Result");
const adsType = root.lookupType("Ads");
const repHeadType = root.lookupType("RepHead");
const resultBytes = resultType.encode({ type: 1, error: 0 }).finish();
const adsBytes = adsType.encode({
  content: [
    { type: "home_banner", start: 10, end: 20 },
    { type: "splash_screen1040", start: 30, end: 40 },
    { type: "normal_card", start: 50, end: 60 }
  ]
}).finish();
const repHeadBytes = repHeadType.encode({
  md5: "original",
  range: "",
  messageHead: [
    { offset: 0, length: resultBytes.length, name: "Result" },
    { offset: resultBytes.length, length: adsBytes.length, name: "Ads" }
  ]
}).finish();
const input = new Uint8Array(4 + repHeadBytes.length + resultBytes.length + adsBytes.length);
new DataView(input.buffer).setInt32(0, repHeadBytes.length);
input.set(repHeadBytes, 4);
input.set(resultBytes, 4 + repHeadBytes.length);
input.set(adsBytes, 4 + repHeadBytes.length + resultBytes.length);
let doneResult, logs = [];
const context = {
  console: { log(...args) { logs.push(args); } },
  Uint8Array,
  ArrayBuffer,
  DataView,
  $response: { body: input },
  $done(value) { doneResult = value; }
};
vm.runInNewContext(source + "\nglobalThis.__testRoot = baiduMapRoot; globalThis.__testMd5 = md5;", context);
if (!doneResult || !(doneResult.body instanceof Uint8Array)) throw new Error("Baidu handler did not return a binary body");
if (logs.length !== 0) throw new Error("Baidu handler emitted runtime debug logs");
const output = doneResult.body;
const headerLength = new DataView(output.buffer, output.byteOffset, 4).getInt32(0);
const outputRoot = context.__testRoot;
const header = outputRoot.lookupType("RepHead").decode(output.subarray(4, 4 + headerLength));
const resultMeta = header.messageHead.find(item => item.name === "Result");
const adsMeta = header.messageHead.find(item => item.name === "Ads");
const resultOffset = 4 + headerLength + resultMeta.offset;
const outputResult = output.subarray(resultOffset, resultOffset + resultMeta.length);
if (Buffer.compare(Buffer.from(outputResult), Buffer.from(resultBytes)) !== 0) throw new Error("untouched Result bytes were changed");
const adsOffset = 4 + headerLength + adsMeta.offset;
const outputAds = outputRoot.lookupType("Ads").decode(output.subarray(adsOffset, adsOffset + adsMeta.length));
if (outputAds.content[0].start !== 1648746061 || outputAds.content[0].end !== 1648832461) throw new Error("banner dates were not expired");
if (outputAds.content[1].start !== 1648746061 || outputAds.content[1].end !== 1648832461) throw new Error("splash dates were not expired");
if (outputAds.content[2].start !== 50 || outputAds.content[2].end !== 60) throw new Error("non-ad content was modified");
const merged = new Uint8Array(outputResult.length + adsMeta.length);
merged.set(outputResult, 0);
merged.set(output.subarray(adsOffset, adsOffset + adsMeta.length), outputResult.length);
if (header.md5 !== context.__testMd5(merged)) throw new Error("RepHead md5 does not match the rewritten payload");
'''
        result = subprocess.run([node, "-e", harness, str(source_path)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


class TaobaoLocalJsonRuntimePerformanceTests(unittest.TestCase):
    def test_taobao_handler_parses_and_serializes_once_per_response(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Taobao runtime integration test")
        source_path = Path(__file__).with_name("scripts").joinpath("taobao", "taobao.js")
        source = source_path.read_text(encoding="utf-8")
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)
        self.assertEqual(source.count('setIfDifferent(item, "waitTime", "0")'), 1)

        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const cases = [
  {
    url: "https://guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query",
    data: { data: { duration: "20", resources: [{url:"a"}], caches: [{url:"b"}], respTimeInMs: "1" } },
    check(body) {
      if (body.data.duration !== "0" || body.data.resources.length !== 0 || body.data.caches.length !== 0 || body.data.respTimeInMs !== "3818332800000") throw new Error("cloudvideo result mismatch");
    }
  },
  {
    url: "https://guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get",
    data: { data: { containers: { splash_home_base: { base: { sections: [
      { bizData: { "taobao-splash": { data: [{waitTime:"10",times:"3",hotStart:"true",haveVoice:"true",hideTBLogo:"true",enable4G:"true",coldStart:"true",imgUrl:"image",videoUrl:"video"}] } } }
    ] } } } } },
    check(body) {
      const item = body.data.containers.splash_home_base.base.sections[0].bizData["taobao-splash"].data[0];
      if (item.waitTime !== "0" || item.times !== "0" || item.hotStart !== "false" || item.imgUrl !== "" || item.videoUrl !== "" || item.startTime !== "3818332800000") throw new Error("splash result mismatch");
    }
  },
  {
    url: "https://poplayer.template.alibaba.com/test.json",
    data: { res: { images:[1], videos:[2] }, enable:true, mainRes:{images:[3]} },
    check(body) {
      if (body.res.images.length !== 0 || body.res.videos.length !== 0 || body.enable !== false || body.mainRes.images.length !== 0) throw new Error("poplayer result mismatch");
    }
  }
];
for (const item of cases) {
  let parseCalls = 0, stringifyCalls = 0, doneResult;
  const trackedJSON = {
    parse(...args) { parseCalls++; return JSON.parse(...args); },
    stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
  };
  vm.runInNewContext(source, {
    JSON: trackedJSON,
    $request: { url: item.url },
    $response: { body: JSON.stringify(item.data) },
    $done(value) { doneResult = value; }
  });
  if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error(item.url + " parse/stringify count " + parseCalls + "/" + stringifyCalls);
  item.check(JSON.parse(doneResult.body));
}
let emptyDone;
vm.runInNewContext(source, {
  JSON,
  $request: { url: "https://guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query" },
  $response: { body: "" },
  $done(value) { emptyDone = value; }
});
if (!emptyDone || Object.keys(emptyDone).length !== 0) throw new Error("empty body fast path changed");
'''
        result = subprocess.run([node, "-e", harness, str(source_path)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
