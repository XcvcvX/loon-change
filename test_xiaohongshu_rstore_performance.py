import json
import shutil
import subprocess
import sys
import unittest

sys.setrecursionlimit(10000)
from pathlib import Path

from optimize_xiaohongshu_rstore import LOCAL, REMOTE, MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/xiaohongshu/xiaohongshu-rstore.js"
NODE = shutil.which("node")


class RStoreXiaohongshuOptimizerTests(unittest.TestCase):
    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertIn("imageEnhance(images_list)", source)
        self.assertIn("if (!$response.body) { $done({}); } else {", source)
        self.assertNotIn("imageEnhance(JSON.stringify(images_list))", source)
        self.assertIn("appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)", source)
        self.assertIn("const byFileId = new Map()", source)
        self.assertIn("const stack = [obj]", source)
        self.assertNotIn(".filter(v => !!v.master_url && !!v.height).sort(", source)
        self.assertNotIn("let newItems = []", source)

    def test_exactly_ten_live_rstore_triggers_are_routed_to_local_script(self):
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        self.assertEqual(plugin.count(REMOTE), 0)
        self.assertEqual(plugin.count(LOCAL), 10)
        routed = rewrite_plugin(plugin)
        self.assertEqual(routed.count(LOCAL), 10)
        self.assertNotIn(REMOTE, routed)
        self.assertEqual(rewrite_plugin(routed), routed)

    def test_trigger_count_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected 10"):
            rewrite_plugin("[Script]\nhttp-response ^https://example.invalid script-path=" + REMOTE + "\n")

    def test_array_filters_and_video_sort_are_removed_from_hot_paths(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("compactInPlace(obj.data.items", source)
        self.assertIn("compactInPlace(item.hash_tag", source)
        self.assertIn("for (const stream of h265List)", source)
        self.assertNotIn("h265List.filter(", source)
        self.assertNotIn("obj.data = newItems", source)


@unittest.skipUnless(NODE, "Node.js is required for R-Store Xiaohongshu runtime tests")
class RStoreXiaohongshuRuntimeTests(unittest.TestCase):
    def run_script(self, url, body, store=None, raw_body=None):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const store = new Map(Object.entries(payload.store || {}));
let doneResult;
const context = {
  $loon: {},
  $persistentStore: {
    read(key) { return store.has(key) ? store.get(key) : null; },
    write(value, key) { store.set(key, value); return true; }
  },
  $request: {url: payload.url},
  $response: {body: payload.rawBody === undefined ? JSON.stringify(payload.body) : payload.rawBody},
  $done(value) { doneResult = value; },
  parseCount: 0,
  JSON: {
    parse(value) { this.parseCount++; return JSON.parse(value); },
    stringify(value) { return JSON.stringify(value); }
  },
  console: {log() {}, warn() {}, error() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
process.stdout.write(JSON.stringify({
  doneResult,
  parseCount: context.JSON.parseCount,
  store: Object.fromEntries(store)
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({
                "url": url, "body": body, "store": store or {},
                **({"rawBody": raw_body} if raw_body is not None else {})
            }),
            capture_output=True, text=True, check=True, timeout=10
        )
        return json.loads(completed.stdout)

    def test_empty_body_finishes_before_json_parse(self):
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture",
            None, raw_body=""
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 0)

    def test_imagefeed_mutates_parsed_object_without_json_round_trip(self):
        original = "https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"
        body = {"data": [{"note_list": [{
            "images_list": [{"url": original, "nested": {"url": original}}],
            "media_save_config": {"disable_save": True},
            "share_info": {"function_entries": [{"type": "share"}]},
            "hash_tag": [{"type": "normal"}, {"type": "interact_vote"}]
        }]}]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=fixture", body
        )
        response = json.loads(result["doneResult"]["body"])
        item = response["data"][0]["note_list"][0]
        self.assertIn("w/2160/format", item["images_list"][0]["url"])
        self.assertIn("w/2160/format", item["images_list"][0]["nested"]["url"])
        self.assertEqual([tag["type"] for tag in item["hash_tag"]], ["normal"])
        cached = json.loads(result["store"]["redBookLivePhoto"])
        self.assertEqual(cached[0]["url"], original)
        self.assertEqual(cached[0]["nested"]["url"], original)

    def test_homefeed_compaction_is_stable_and_keeps_null_items(self):
        body = {"data": [
            {"id": "keep1", "related_ques": {}},
            None,
            {"id": "ad", "ads_info": {}},
            {"id": "live", "model_type": "live_v2"},
            {"id": "shop", "note_attributes": ["goods"]},
            {"id": "card", "card_icon": None},
            {"id": "keep2"}
        ]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v6/homefeed?cursor=fixture", body
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([item["id"] for item in output["data"] if item], ["keep1", "keep2"])
        self.assertIsNone(output["data"][1])
        self.assertNotIn("related_ques", output["data"][0])

    def test_v4_video_stream_selection_uses_single_pass_highest_height(self):
        body = {"data": [{
            "id": "note-1",
            "video_info_v2": {"media": {"stream": {"h265": [
                {"master_url": "https://video.example/720.mp4", "height": 720},
                {"master_url": "https://video.example/2160.mp4", "height": 2160},
                {"master_url": "https://video.example/1080.mp4", "height": 1080}
            ]}}}
        }]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?cursor=fixture", body
        )
        cache = json.loads(result["store"]["redBookVideoFeed"])
        self.assertEqual(cache[0]["url"], "https://video.example/2160.mp4")

    def test_comment_tree_cleanup_is_iterative_for_deep_objects(self):
        nested = {"red_id": "deep"}
        for index in range(400):
            nested = {"child": nested, "red_id": str(index)}
        body = {"data": {"red_id": "root", "nested": nested}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture", body
        )
        output = json.loads(result["doneResult"]["body"])
        current = output["data"]
        while "nested" in current:
            self.assertNotIn("red_id", current)
            current = current["nested"]
        self.assertNotIn("red_id", current)


if __name__ == "__main__":
    unittest.main()
