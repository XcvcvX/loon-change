import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for the Xiaohongshu runtime regression tests")
class XiaohongshuV4SinglePassTests(unittest.TestCase):
    def run_script(self, url, body, disable_filter=False, initial_store=None):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("scripts/xiaohongshu/xiaohongshu-v4.js", "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const store = new Map(Object.entries(payload.store || {}));
let doneResult;
const context = {
  // Make the bundled Env helper select Loon storage rather than writing box.dat
  // into the GitHub Actions workspace.
  $loon: {},
  $persistentStore: {
    read(key) { return store.has(key) ? store.get(key) : null; },
    write(value, key) { store.set(key, value); return true; }
  },
  $request: { url: payload.url },
  $response: { body: JSON.stringify(payload.body) },
  $done: value => { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
if (payload.disableFilter) {
  vm.runInNewContext("Array.prototype.filter = function() { throw new Error('Array.filter allocation remains'); };", context);
}
vm.runInNewContext(source, context, { timeout: 5000 });
const result = {
  done: Boolean(doneResult),
  body: doneResult && typeof doneResult.body === "string" ? JSON.parse(doneResult.body) : null,
  store: Object.fromEntries(store)
};
process.stdout.write(JSON.stringify(result));
"""
        result = subprocess.run(
            [NODE, "-e", runner],
            input=json.dumps({"url": url, "body": body, "disableFilter": disable_filter, "store": initial_store or {}}),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        output_lines = [line for line in result.stdout.splitlines() if line.strip()]
        if not output_lines:
            self.fail(f"Node runtime produced no JSON output; stderr={result.stderr!r}")
        return json.loads(output_lines[-1])

    @staticmethod
    def video_item(item_id, url, include_download=False):
        return {
            "id": item_id,
            "model_type": "note",
            "media_save_config": {
                "disable_save": True,
                "disable_watermark": False,
                "disable_weibo_cover": False,
            },
            "function_switch": [
                {"type": "video_download", "enable": False, "reason": "restricted"}
            ],
            "share_info": {
                "function_entries": (
                    [{"type": "video_download"}]
                    if include_download else [{"type": "share"}]
                )
            },
            "video_info_v2": {
                "media": {
                    "stream": {
                        "h265": [{
                            "master_url": url,
                            "width": 1080,
                            "height": 1920,
                            "avg_bitrate": 3000000,
                        }],
                        "h264": [],
                    }
                }
            },
        }

    def test_v4_feed_filters_and_processes_retained_notes_in_one_pass(self):
        first = self.video_item("note-1", "https://video.example/note-1.mp4")
        second = self.video_item("note-2", "https://video.example/note-2.mp4", True)
        body = {
            "data": [
                first,
                {"id": "ad-1", "model_type": "note", "ad": {"ad_id": "1"}},
                {"id": "live-1", "model_type": "live_v2"},
                None,
                second,
            ]
        }

        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v4/note/videofeed",
            body,
        )

        self.assertTrue(result["done"])
        self.assertEqual(
            [item["id"] for item in result["body"]["data"]],
            ["note-1", "note-2"],
        )
        kept_first = result["body"]["data"][0]
        self.assertEqual(kept_first["media_save_config"]["disable_save"], False)
        self.assertEqual(kept_first["media_save_config"]["disable_watermark"], True)
        self.assertEqual(kept_first["media_save_config"]["disable_weibo_cover"], True)
        self.assertEqual(kept_first["function_switch"][0]["enable"], True)
        self.assertNotIn("reason", kept_first["function_switch"][0])
        self.assertEqual(
            [entry["type"] for entry in kept_first["share_info"]["function_entries"]],
            ["share", "video_download"],
        )
        self.assertEqual(
            [entry["type"] for entry in result["body"]["data"][1]["share_info"]["function_entries"]],
            ["video_download"],
        )
        self.assertEqual(
            json.loads(result["store"]["redBookVideoFeed"]),
            [
                {"id": "note-1", "url": "https://video.example/note-1.mp4"},
                {"id": "note-2", "url": "https://video.example/note-2.mp4"},
            ],
        )

    def test_empty_filtered_feed_clears_stale_video_cache(self):
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v4/note/videofeed",
            {
                "data": [
                    {"id": "ad-1", "model_type": "note", "ad": {"ad_id": "1"}},
                    {"id": "live-1", "model_type": "live_v2"},
                ]
            },
        )
        self.assertTrue(result["done"])
        self.assertEqual(result["body"]["data"], [])
        self.assertEqual(result["store"]["redBookVideoFeed"], "[]")

    def test_v4_feed_uses_in_place_compaction_not_filter_allocation(self):
        source = (ROOT / "scripts/xiaohongshu/xiaohongshu-v4.js").read_text(encoding="utf-8")
        start = source.index('// 信息流 视频\nif (url.includes("/v4/note/videofeed"))')
        end = source.index("// 视频保存请求", start)
        block = source[start:end]
        self.assertNotIn("obj.data = obj.data.filter", block)
        self.assertIn("items[write++] = item", block)
        self.assertIn("items.length = write", block)
        self.assertIn("processVideoFeedItem(item, videoData)", block)


    def test_search_follow_and_home_feeds_compact_in_place_without_filter(self):
        cases = [
            (
                "https://edith.xiaohongshu.com/api/sns/v1/search/notes?keyword=test",
                {"data": {"items": [
                    {"id": "note-1", "model_type": "note"},
                    {"id": "ad-1", "model_type": "ads"},
                    {"id": "note-2", "model_type": "note"},
                ]}},
                ["note-1", "note-2"],
            ),
            (
                "https://edith.xiaohongshu.com/api/sns/v1/user/followings/followfeed",
                {"data": {"items": [
                    {"id": "friend-1", "recommend_reason": "friend_post"},
                    {"id": "recommend-1", "recommend_reason": "recommend_user"},
                    {"id": "friend-2", "recommend_reason": "friend_post"},
                ]}},
                ["friend-1", "friend-2"],
            ),
            (
                "https://edith.xiaohongshu.com/api/sns/v4/followfeed",
                {"data": {"items": [
                    {"id": "friend-1", "recommend_reason": "friend_post"},
                    {"id": "recommend-1", "recommend_reason": "recommend_user"},
                    {"id": "friend-2", "recommend_reason": "friend_post"},
                ]}},
                ["friend-1", "friend-2"],
            ),
        ]
        for url, body, expected in cases:
            with self.subTest(url=url):
                result = self.run_script(url, body, disable_filter=True)
                self.assertTrue(result["done"])
                self.assertEqual(
                    [item["id"] for item in result["body"]["data"]["items"]],
                    expected,
                )

        home = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v6/homefeed",
            {"data": [
                {"id": "keep-1", "related_ques": {"id": 1}},
                {"id": "live", "model_type": "live_v2"},
                {"id": "ad", "ads_info": {}},
                {"id": "goods", "note_attributes": ["goods"]},
                None,
                {"id": "keep-2"},
            ]},
            disable_filter=True,
        )
        self.assertEqual(
            [item.get("id") if item else None for item in home["body"]["data"]],
            ["keep-1", None, "keep-2"],
        )
        self.assertNotIn("related_ques", home["body"]["data"][0])

    def test_imagefeed_hash_tags_compact_in_place_without_filter(self):
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=test",
            {"data": [{"note_list": [{
                "images_list": [],
                "hash_tag": [
                    {"type": "normal", "id": 1},
                    {"type": "interact_vote", "id": 2},
                    {"type": "normal", "id": 3},
                ],
            }]}]},
            disable_filter=True,
        )
        tags = result["body"]["data"][0]["note_list"][0]["hash_tag"]
        self.assertEqual([item["id"] for item in tags], [1, 3])

    def test_comment_cache_dedup_appends_and_compacts_in_place(self):
        cached = {
            "noteId": "note-1",
            "livePhotos": [{"videId": "old", "videoUrl": "old-url"}],
        }
        video_info = json.dumps({"stream": {"h265": [
            {"master_url": "old-new-url", "width": 1080, "height": 1920, "avg_bitrate": 1},
        ]}})
        new_info = json.dumps({"stream": {"h265": [
            {"master_url": "new-url", "width": 1080, "height": 1920, "avg_bitrate": 2},
        ]}})
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?note_id=note-1",
            {"data": {"comments": [{
                "id": "comment-1",
                "note_id": "note-1",
                "pictures": [
                    {"video_id": "old", "video_info": video_info},
                    {"video_id": "new", "video_info": new_info},
                ],
            }]}},
            disable_filter=True,
            initial_store={"fmz200.xiaohongshu.comments.rsp": json.dumps(cached)},
        )
        stored = json.loads(result["store"]["fmz200.xiaohongshu.comments.rsp"])
        self.assertEqual([item["videId"] for item in stored["livePhotos"]], ["old", "new"])
        self.assertEqual(stored["livePhotos"][0]["videoUrl"], "old-url")
        self.assertEqual(stored["livePhotos"][1]["videoUrl"], "new-url")


    def test_comment_red_id_walk_avoids_per_object_keys_arrays(self):
        source = (ROOT / "scripts/xiaohongshu/xiaohongshu-v4.js").read_text(encoding="utf-8")
        start = source.index("function replaceRedIdWithFmz200(obj) {")
        end = source.index("function deduplicateLivePhotos", start)
        block = source[start:end]
        self.assertNotIn("Object.keys(current)", block)
        self.assertIn("Object.prototype.hasOwnProperty.call(current, key)", block)
        self.assertIn("const childStart = stack.length", block)

        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?note_id=note-1",
            {"data": {
                "red_id": "root-id",
                "comments": [{
                    "id": "comment-1",
                    "note_id": "note-1",
                    "red_id": "comment-id",
                    "nested": {
                        "red_id": "nested-id",
                        "items": [{"red_id": "array-item-id"}],
                    },
                }],
            }},
        )
        data = result["body"]["data"]
        self.assertEqual(data["fmz200"], "root-id")
        self.assertNotIn("red_id", data)
        comment = data["comments"][0]
        self.assertEqual(comment["fmz200"], "comment-id")
        self.assertEqual(comment["nested"]["fmz200"], "nested-id")
        self.assertEqual(comment["nested"]["items"][0]["fmz200"], "array-item-id")


if __name__ == "__main__":
    unittest.main()
