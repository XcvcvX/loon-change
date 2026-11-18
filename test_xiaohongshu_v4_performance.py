import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for the Xiaohongshu runtime regression tests")
class XiaohongshuV4SinglePassTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("scripts/xiaohongshu/xiaohongshu-v4.js", "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const store = new Map();
let doneResult;
class Env {
  getdata(key) { return store.has(key) ? store.get(key) : null; }
  setdata(value, key) { store.set(key, value); }
}
const context = {
  Env,
  $request: { url: payload.url },
  $response: { body: JSON.stringify(payload.body) },
  $done: value => { doneResult = value; },
  console
};
vm.runInNewContext(source, context, { timeout: 5000 });
if (!doneResult || typeof doneResult.body !== "string") {
  throw new Error("Xiaohongshu script did not return a response body");
}
process.stdout.write(JSON.stringify({
  body: JSON.parse(doneResult.body),
  store: Object.fromEntries(store)
}));
"""
        result = subprocess.run(
            [NODE, "-e", runner],
            input=json.dumps({"url": url, "body": body}),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(result.stdout)

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


if __name__ == "__main__":
    unittest.main()
