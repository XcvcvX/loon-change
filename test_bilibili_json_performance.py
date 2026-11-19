import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")
SOURCE = ROOT / "scripts" / "bilibili" / "bilibili-json.js"


@unittest.skipUnless(NODE, "Node.js is required for Bilibili response runtime tests")
class BilibiliResponseCompactionTests(unittest.TestCase):
    def run_body(self, url, body, guard_object_keys=False):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const NativeJSON = JSON;
let numericWrites = 0, parseCalls = 0, stringifyCalls = 0;
const instrumentedJSON = {
  parse(text) {
    parseCalls++;
    const value = NativeJSON.parse(text);
    const list = value && value.data && value.data.items;
    if (Array.isArray(list)) {
      value.data.items = new Proxy(list, {
        set(target, key, next) {
          if (/^(0|[1-9][0-9]*)$/.test(String(key))) numericWrites++;
          return Reflect.set(target, key, next);
        }
      });
    }
    return value;
  },
  stringify(value) {
    stringifyCalls++;
    return NativeJSON.stringify(value);
  }
};
let doneResult;
const context = {
  JSON: instrumentedJSON,
  $request: { url: payload.url },
  $response: { body: NativeJSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
if (payload.guardObjectKeys) {
  vm.runInContext("Object.keys = function() { throw new Error('Object.keys temporary allocation remains'); };", context);
}
vm.runInContext(source, context, { timeout: 5000 });
if (!doneResult) throw new Error("script did not call $done");
const hasBody = typeof doneResult.body === "string";
const output = hasBody ? NativeJSON.parse(doneResult.body) : payload.body;
process.stdout.write(NativeJSON.stringify({
  output, numericWrites, parseCalls, stringifyCalls, hasBody
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body, "guardObjectKeys": guard_object_keys}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def run_script(self, url, items):
        return self.run_body(url, {"data": {"items": items}})

    def test_feed_kept_items_are_not_written_back_to_the_same_indices(self):
        items = [{"id": "a", "card_goto": "av"}, {"id": "b", "card_goto": "av"}]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 0)
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 0)
        self.assertFalse(result["hasBody"])

    def test_feed_compaction_writes_only_when_items_shift(self):
        items = [
            {"id": "ad", "card_goto": "banner"},
            {"id": "a", "card_goto": "av"},
            {"id": "b", "card_goto": "av"},
        ]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 2)
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertTrue(result["hasBody"])

    def test_story_feed_preserves_kept_items_without_redundant_array_writes(self):
        items = [{"id": "a", "card_goto": "vertical_av"}, {"id": "b", "card_goto": "vertical_av"}]
        result = self.run_script("https://app.bilibili.com/x/v2/feed/index/story?pull=1", items)
        self.assertEqual([item["id"] for item in result["output"]["data"]["items"]], ["a", "b"])
        self.assertEqual(result["numericWrites"], 0)
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 0)
        self.assertFalse(result["hasBody"])

    def test_unchanged_tab_profile_splash_and_page_responses_skip_stringify(self):
        cases = [
            (
                "https://app.bilibili.com/x/resource/show/tab/v1?build=1",
                {"data": {
                    "bottom": [{"name": "首页"}, {"name": "动态"}, {"name": "关注"}, {"name": "我的"}],
                    "tab": [{"name": "推荐"}, {"name": "热门"}, {"name": "影视"}, {"name": "动画"}],
                    "top": [{"name": "消息", "pos": 1}]
                }},
            ),
            (
                "https://app.bilibili.com/x/v2/account/mine/ipad?build=1",
                {"data": {
                    "ipad_recommend_sections": [{"id": 789}, {"id": 790}],
                    "ipad_more_sections": [{"id": 797}, {"id": 798}]
                }},
            ),
            (
                "https://app.bilibili.com/x/v2/account/mine?build=1",
                {"data": {
                    "sections_v2": [{"style": 1, "title": "常规服务"}],
                    "vip": {"status": 1}
                }},
            ),
            (
                "https://app.bilibili.com/x/v2/account/myinfo?build=1",
                {"data": {"vip": {"status": 1}}},
            ),
            (
                "https://app.bilibili.com/x/v2/splash/list?build=1",
                {"data": {
                    "max_time": 0,
                    "min_interval": 31536000,
                    "pull_interval": 31536000,
                    "list": [{
                        "duration": 0, "enable_pre_download": False,
                        "begin_time": 3818332800, "end_time": 3818419199
                    }]
                }},
            ),
            (
                "https://app.bilibili.com/x/v2/search/square?build=1",
                {"data": {"type": "history", "title": "搜索历史", "search_hotword_revision": 2}},
            ),
            (
                "https://api.bilibili.com/pgc/page/bangumi?build=1",
                {"result": {"modules": [
                    {"style": "banner", "items": [{"link": "bilibili://play/1"}]},
                    {"style": "function", "items": [{"blink": "bilibili://home"}]},
                    {"module_id": 100, "items": [{"id": 1}]}
                ]}},
            ),
            (
                "https://api.live.bilibili.com/xlive/app-room/v1/index/getInfoByRoom?build=1",
                {"data": {
                    "shopping_info": {"is_show": 0},
                    "new_tab_info": {"outer_list": [{"biz_id": 1}]}
                }},
            ),
        ]
        for url, body in cases:
            with self.subTest(url=url):
                result = self.run_body(url, body)
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 0)
                self.assertFalse(result["hasBody"])

    def test_tab_filter_and_sort_mutations_still_serialize_once(self):
        result = self.run_body(
            "https://app.bilibili.com/x/resource/show/tab/v1?build=1",
            {"data": {
                "bottom": [{"name": "我的"}, {"name": "广告"}, {"name": "首页"}],
                "tab": [{"name": "热门"}, {"name": "推荐"}],
                "top": [{"name": "活动"}, {"name": "消息", "pos": 5}]
            }},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertTrue(result["hasBody"])
        self.assertEqual([x["name"] for x in result["output"]["data"]["bottom"]], ["首页", "我的"])
        self.assertEqual([x["name"] for x in result["output"]["data"]["tab"]], ["推荐", "热门"])
        self.assertEqual(result["output"]["data"]["top"], [{"name": "消息", "pos": 1}])

    def test_profile_vip_mutations_still_apply_once(self):
        result = self.run_body(
            "https://app.bilibili.com/x/v2/account/mine?build=1",
            {"data": {
                "rework_v1": {"ad": 1},
                "sections_v2": [
                    {"style": 1, "title": "更多服务", "button": {"text": "open"},
                     "items": [
                         {"uri": "user_center/setting"},
                         {"uri": "user_center/feedback"},
                         {"uri": "user_center/other"}
                     ]},
                    {"style": 4, "title": "隐藏区"}
                ],
                "vip": {"status": 0}
            }},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertTrue(result["hasBody"])
        data = result["output"]["data"]
        self.assertNotIn("rework_v1", data)
        self.assertEqual(len(data["sections_v2"]), 1)
        self.assertNotIn("button", data["sections_v2"][0])
        self.assertNotIn("title", data["sections_v2"][0])
        self.assertEqual([x["uri"] for x in data["sections_v2"][0]["items"]],
                         ["user_center/setting", "user_center/feedback"])
        self.assertEqual(data["vip"]["status"], 1)

    def test_search_square_and_live_room_key_checks_do_not_allocate_object_keys(self):
        search = self.run_body(
            "https://app.bilibili.com/x/v2/search/square?build=1",
            {"data": {"type": "history", "title": "搜索历史", "search_hotword_revision": 2}},
            guard_object_keys=True,
        )
        self.assertEqual(search["stringifyCalls"], 0)
        self.assertFalse(search["hasBody"])

        live = self.run_body(
            "https://api.live.bilibili.com/xlive/app-room/v1/index/getInfoByRoom?build=1",
            {"data": {"shopping_info": {"is_show": 0}}},
            guard_object_keys=True,
        )
        self.assertEqual(live["stringifyCalls"], 0)
        self.assertFalse(live["hasBody"])

    def test_live_room_cleanup_marks_only_real_changes(self):
        result = self.run_body(
            "https://api.live.bilibili.com/xlive/app-room/v1/index/getInfoByRoom?build=1",
            {"data": {
                "activity_banner_info": {"ad": 1},
                "shopping_info": {"is_show": 1, "extra": "remove"},
                "new_tab_info": {"outer_list": [{"biz_id": 33}, {"biz_id": 1}]}
            }},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        data = result["output"]["data"]
        self.assertNotIn("activity_banner_info", data)
        self.assertEqual(data["shopping_info"], {"is_show": 0})
        self.assertEqual(data["new_tab_info"]["outer_list"], [{"biz_id": 1}])

    def test_compaction_loops_cache_array_lengths_and_guard_same_index_writes(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("if (write !== read) items[write] = item;", source)
        self.assertIn("let read = 0, length = items.length", source)
        self.assertNotIn("items[write++]", source)
        self.assertNotIn("sections[sectionWrite++]", source)
        self.assertNotIn("items[itemWrite++]", source)
        self.assertNotIn("Object.keys(", source)
        self.assertIn("function countOwnEnumerableKeys(target, limit)", source)


if __name__ == "__main__":
    unittest.main()
