import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_weibo_rstore import LOCAL, REMOTE, MARKER, LAZY_MARKER, GUARD_DECLARATION, HELPER, LEGACY_HELPER, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/weibo/weibo-rstore.js"
NODE = shutil.which("node")


class RStoreWeiboOptimizerTests(unittest.TestCase):
    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertIn(LAZY_MARKER, source)
        self.assertIn('let modified = !url.includes("/2/cardlist") && !url.includes("/2/comments/build_comments");', source)
        self.assertIn('$done(modified ? {body: JSON.stringify(obj)} : {});', source)
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

    def test_old_optimized_snapshot_regains_lazy_serialization_guard(self):
        source = SCRIPT.read_text(encoding="utf-8")
        legacy = source.replace(LAZY_MARKER + "\n", "", 1)
        legacy = legacy.replace(GUARD_DECLARATION + "\n", "", 1)
        legacy = legacy.replace(HELPER, LEGACY_HELPER, 1)
        legacy = re.sub(r"(?m)^([ \t]*)if \(__loonWrite\d+ !== __loonLength\d+\) modified = true;\n", "", legacy)
        legacy = re.sub(r"(?m)^([ \t]*)modified = true;\n([ \t]*delete .+;)$", r"\2", legacy)
        legacy = legacy.replace("$done(modified ? {body: JSON.stringify(obj)} : {});", "$done({body: JSON.stringify(obj)});", 1)
        self.assertEqual(optimize_source(legacy), source)

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
let parseCount = 0, stringifyCount = 0;
const nativeParse = JSON.parse.bind(JSON);
const nativeStringify = JSON.stringify.bind(JSON);
const trackedJSON = {
  parse(value) { parseCount++; return nativeParse(value); },
  stringify(value) { stringifyCount++; return nativeStringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: {url: payload.url},
  $response: {body: JSON.stringify(payload.body)},
  $done(value) { doneResult = value; },
  console: {log() {}, warn() {}, error() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
process.stdout.write(JSON.stringify({doneResult, parseCount, stringifyCount}));
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
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

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
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_clean_cardlist_and_comments_skip_response_serialization(self):
        cardlist = {"cards": [
            {"card_group": [{"card_type": 1, "mblog": {"id": "keep-1"}}]},
            {"card_type": 2, "mblog": {"id": "keep-2"}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/cardlist?containerid=clean", cardlist)
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

        comments = {"datas": [
            {"type": 1, "data": {"user": {"name": "普通用户"}, "text": "keep"}}
        ]}
        result = self.run_script("https://api.weibo.cn/2/comments/build_comments?flow=clean", comments)
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_other_response_routes_keep_legacy_serialization(self):
        result = self.run_script("https://api.weibo.cn/2/checkin/show", {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)
        self.assertIn("body", result["doneResult"])

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
