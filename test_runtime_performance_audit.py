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

if __name__ == "__main__":
    unittest.main()
