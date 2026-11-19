import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_weibo_rstore import LOCAL, REMOTE, MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/weibo/weibo-rstore.js"
NODE = shutil.which("node")


class RStoreWeiboOptimizerTests(unittest.TestCase):
    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(len(re.findall(r"const __loonSource\d+ =", source)), 32)
        remaining = re.findall(r"\b(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]", source)
        self.assertEqual(sorted(remaining), ["newActions", "newII"])
        self.assertIn("compactInPlace(obj.elements", source)
        self.assertIn("compactInPlace(obj.user_list", source)
        self.assertIn("compactInPlace(obj.cards", source)
        self.assertNotIn("obj.elements = obj.elements.filter(", source)
        self.assertNotIn("obj.user_list = obj.user_list.filter(", source)
        self.assertNotIn("obj.channelInfo.channel_list = obj.channelInfo.channel_list.filter(", source)

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


@unittest.skipUnless(NODE, "Node.js is required for Weibo runtime regression tests")
class RStoreWeiboRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult;
const context = {
  $request: {url: payload.url},
  $response: {body: JSON.stringify(payload.body)},
  $done(value) { doneResult = value; },
  console: {log() {}, warn() {}, error() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
process.stdout.write(JSON.stringify({doneResult}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True, text=True, check=True, timeout=10
        )
        return json.loads(completed.stdout)

    def test_cardlist_nested_arrays_compact_in_place_without_changing_order(self):
        body = {"cards": [
            {"card_group": [
                {"card_type": 120},
                {"card_type": 1, "mblog": {"buttons": [{"type": "follow"}]}}
            ]},
            {"card_type": 17},
            {"card_type": 2, "mblog": {"buttons": [{"type": "follow"}]}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/cardlist?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["cards"]), 2)
        self.assertEqual([g["card_type"] for g in output["cards"][0]["card_group"]], [1])
        self.assertNotIn("buttons", output["cards"][0]["card_group"][0]["mblog"])
        self.assertNotIn("buttons", output["cards"][1]["mblog"])

    def test_comments_cleanup_keeps_only_allowed_items(self):
        body = {"datas": [
            {"data": {"mblogtypename": "广告"}},
            {"type": 1, "data": {
                "user": {"name": "普通用户", "icons": [{"type": "vip"}]},
                "comment_bubble": {"text": "x"},
                "comment_bullet_screens_message": {"text": "x"},
                "hot_icon": {"type": "hot"},
                "vip_button": {"text": "x"}
            }},
            {"type": 1, "data": {"user": {"name": "超话社区"}}},
            {"type": 6, "data": {"user": {"name": "普通用户"}}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/comments/build_comments?flow=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(len(output["datas"]), 1)
        kept = output["datas"][0]["data"]
        self.assertNotIn("icons", kept["user"])
        for key in ("comment_bubble", "comment_bullet_screens_message", "hot_icon", "vip_button"):
            self.assertNotIn(key, kept)

    def test_hot_timeline_compaction_preserves_feed_order(self):
        body = {
            "items": [
                {"category": "feed", "data": {"id": "keep-1"}},
                {"category": "feed", "data": {"mblogtypename": "广告"}},
                {"category": "card", "data": {"id": "drop-card"}},
                {"category": "feed", "data": {"id": "keep-2"}}
            ],
            "statuses": [
                {"id": "drop-ad", "mblogtypename": "广告"},
                {"id": "keep-status"}
            ],
            "ad": {"x": 1},
            "trends": [{"x": 1}]
        }
        result = self.run_script("https://api.weibo.cn/2/statuses/container_timeline_hot?refresh=1", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["data"].get("id") for x in output["items"]], ["keep-1", "keep-2"])
        self.assertEqual([x["id"] for x in output["statuses"]], ["keep-status"])
        self.assertNotIn("ad", output)
        self.assertNotIn("trends", output)

    def test_search_page_filters_ads_in_place(self):
        body = {"cards": [
            {"itemid": "normal", "card_group": [
                {"itemid": "normal-group"},
                {"itemid": "t:51-sponsored"},
                {"actionlog": {"ext": "ads_word"}}
            ]},
            {"itemid": "infeed_friends_recommend"},
            {"itemid": "feed_-_invite"},
            {"itemid": "keep-2"}
        ]}
        result = self.run_script("https://api.weibo.cn/2/page?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["itemid"] for x in output["cards"]], ["normal", "keep-2"])
        self.assertEqual([x["itemid"] for x in output["cards"][0]["card_group"]], ["normal-group"])


if __name__ == "__main__":
    unittest.main()
