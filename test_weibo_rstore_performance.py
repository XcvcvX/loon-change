import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_weibo_rstore import LOCAL, REMOTE, MARKER, LAZY_MARKER, GUARD_DECLARATION, HELPER, LEGACY_HELPER, optimize_source, rewrite_plugin, optimize_page_filter_cached_itemid, TOPIC_GROUP_MARKER, optimize_topic_group_in_place, COMMENT_DATA_CACHE_MARKER, optimize_comment_data_reference_cache

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
        self.assertEqual(len(re.findall(r"(?m)^\s*const __loonLength\d+ = __loonSource\d+\.length;$", source)), 32)
        self.assertNotRegex(source, r"for \(let __loonRead\d+ = 0, __loonLength\d+")
        self.assertNotRegex(source, r"\[[^\]\n]+\]\??\.includes\(")
        remaining = re.findall(r"\b(new[A-Za-z0-9_]*)\s*=\s*\[\s*\]", source)
        self.assertEqual(sorted(remaining), ["newActions"])
        self.assertIn("compactInPlace(obj.elements", source)
        self.assertIn("compactInPlace(obj.user_list", source)
        self.assertIn("compactInPlace(obj.cards", source)
        self.assertNotIn("obj.elements = obj.elements.filter(", source)
        self.assertNotIn("obj.user_list = obj.user_list.filter(", source)
        self.assertNotIn("obj.channelInfo.channel_list = obj.channelInfo.channel_list.filter(", source)

    def test_hot_loop_membership_uses_scalar_comparisons(self):
        source = SCRIPT.read_text(encoding="utf-8")
        marker = "// loon-change: Weibo hot-loop scalar membership v1"
        self.assertEqual(source.count(marker), 1)
        self.assertEqual(optimize_source(source), source)
        self.assertNotRegex(source, r"\[[^\]\n]+\]\??\.includes\(")
        self.assertIn("cardType === 120 || cardType === 145 || cardType === 192", source)
        self.assertIn("item?.data?.card_type === 19 || item?.data?.card_type === 118", source)
        self.assertIn("!(item?.data?.card_type === 4 || item?.data?.card_type === 197", source)


    def test_page_filter_caches_repeated_itemid_property_reads(self):
        source = SCRIPT.read_text(encoding="utf-8")
        marker = "// loon-change: Weibo /2/page cached itemid reads v1"
        self.assertEqual(source.count(marker), 1)
        self.assertEqual(optimize_page_filter_cached_itemid(source), source)
        self.assertIn("const itemId = c?.itemid;", source)
        self.assertIn("const itemId = i.itemid;", source)
        self.assertEqual(source.count("i.itemid?.includes("), 0)
        self.assertEqual(source.count("c?.itemid?.includes("), 0)
        damaged = source.replace("const itemId = i.itemid;", "const cachedItemId = i.itemid;", 1)
        with self.assertRaisesRegex(ValueError, "transformed block missing"):
            optimize_page_filter_cached_itemid(damaged)

    def test_topic_group_compaction_is_in_place_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_topic_group_in_place(source), source)
        self.assertEqual(source.count(TOPIC_GROUP_MARKER), 1)
        self.assertIn("const groupItems = item.items;", source)
        self.assertIn("const groupLength = groupItems.length;", source)
        self.assertIn("groupItems.length = groupWrite;", source)
        self.assertNotIn("let newII = [];", source)
        self.assertNotIn("item.items = newII;", source)
        damaged = source.replace("const groupItems = item.items;", "const groupItems = undefined;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_topic_group_in_place(damaged)

    def test_comment_loop_caches_data_reference_once_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(COMMENT_DATA_CACHE_MARKER), 1)
        self.assertEqual(optimize_comment_data_reference_cache(source), source)
        self.assertIn("const commentData = item?.data;", source)
        self.assertIn("if (!isAd(commentData))", source)
        self.assertIn("removeAvatar(commentData);", source)
        self.assertNotIn("isAd(item?.data)", source)
        self.assertNotIn("removeAvatar(item?.data)", source)
        self.assertNotIn("delete item.data.comment_bubble", source)
        damaged = source.replace("const commentData = item?.data;", "const cachedCommentData = item?.data;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_comment_data_reference_cache(damaged)

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
            capture_output=True, text=True, check=False, timeout=10
        )
        if completed.returncode:
            raise AssertionError(
                "Node VM failed (exit %s):\\n%s\\nstdout:\\n%s"
                % (completed.returncode, completed.stderr, completed.stdout)
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


    def test_search_page_filters_preserve_order_and_ads_semantics(self):
        body = {"cards": [
            {"itemid": "keep-group", "card_group": [
                {"itemid": "normal"},
                {"itemid": "t:51:banner"},
                {"actionlog": {"ext": "ads_word"}, "itemid": "normal-2"},
                {"itemid": "ads_word"}
            ]},
            {"itemid": "feed_-_invite:1"},
            {"itemid": "infeed_friends_recommend:1"},
            {"itemid": "infeed_may_interest_in:1"},
            {"itemid": "infeed_pagemanual3:1"},
            {"itemid": "infeed_weibo_mall:1"},
            {"itemid": "normal-card", "mblog": {"mblogtypename": "广告"}},
            {"itemid": "keep-1"},
            {"itemid": "keep-2"}
        ]}
        result = self.run_script("https://api.weibo.cn/2/page?containerid=fixture", body)
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([item["itemid"] for item in output["cards"]], ["keep-group", "keep-1", "keep-2"])
        self.assertEqual([item["itemid"] for item in output["cards"][0]["card_group"]], ["normal"])

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

    def test_topic_group_top_items_compact_in_place_preserving_order_and_hotwords(self):
        body = {"items": [{
            "category": "group",
            "itemId": None,
            "items": [
                {"data": {"itemid": "mine_topics_1", "buttons": [{"type": "follow"}]}},
                {"data": {"itemid": "tab_search_input", "hotwords": [{"word": "old"}], "icons": [{"type": "x"}]}},
                {"data": {"itemid": "poiRankList"}},
                {"data": {"itemid": "unwanted_recommend"}},
                {"data": {"title": "no itemid", "buttons": [{"type": "follow"}]}},
                {"title": "missing data"}
            ]
        }]}
        result = self.run_script("https://api.weibo.cn/2/statuses/container_timeline_topic?fixture=1", body)
        output = json.loads(result["doneResult"]["body"])
        kept = output["items"][0]["items"]
        self.assertEqual(len(kept), 5)
        self.assertEqual([x.get("data", {}).get("itemid") for x in kept[:3]],
                         ["mine_topics_1", "tab_search_input", "poiRankList"])
        self.assertEqual(kept[1]["data"]["hotwords"], [{"word": "搜索超话"}])
        self.assertNotIn("buttons", kept[0]["data"])
        self.assertNotIn("icons", kept[1]["data"])
        self.assertEqual(kept[3]["data"]["title"], "no itemid")
        self.assertEqual(kept[4]["title"], "missing data")

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
