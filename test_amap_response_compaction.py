import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for the Amap runtime regression tests")
class AmapInPlaceCompactionTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("sources/amap/rucu6_amap.js", "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult;
const context = {
  $request: { url: payload.url },
  $response: { body: payload.body === null ? "" : JSON.stringify(payload.body) },
  $done: value => { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.runInNewContext(source, context, { timeout: 5000 });
if (!doneResult || typeof doneResult.body !== "string") {
  throw new Error("Amap script did not return a response body");
}
process.stdout.write(JSON.stringify(JSON.parse(doneResult.body)));
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
    def suggestion(item_id, datatype="1", result_type="poi", task_tag="normal"):
        return {
            "id": item_id,
            "tip": {
                "datatype_spec": datatype,
                "result_type": result_type,
                "task_tag": task_tag,
            },
        }

    def test_tip_list_removes_all_ad_categories_in_place_and_keeps_order(self):
        body = {
            "tip_list": [
                self.suggestion("keep-1"),
                self.suggestion("datatype-ad", datatype="12"),
                self.suggestion("result-ad", result_type="ad"),
                self.suggestion("result-poi-ad", result_type="poi_ad"),
                self.suggestion("toplist", result_type="toplist"),
                self.suggestion("task-ad", task_tag="ad"),
                self.suggestion("task-exct", task_tag="exct_query_sug_merge_theme"),
                self.suggestion("task-query", task_tag="query_sug_merge_theme"),
                self.suggestion("task-sp", task_tag="sp"),
                self.suggestion("keep-2"),
            ]
        }
        result = self.run_script(
            "https://m5.amap.com/shield/search_poi/sug",
            body,
        )
        self.assertEqual(
            [item["id"] for item in result["tip_list"]],
            ["keep-1", "keep-2"],
        )

    def test_city_list_is_not_reallocated_and_nested_tip_lists_are_compacted(self):
        body = {
            "city_list": [
                {
                    "city": "A",
                    "tip_list": [
                        self.suggestion("a-keep-1"),
                        self.suggestion("a-ad", result_type="ad"),
                        self.suggestion("a-keep-2"),
                    ],
                },
                {
                    "city": "B",
                    "tip_list": [
                        self.suggestion("b-ad", datatype="12"),
                    ],
                },
                {"city": "C", "tip_list": []},
            ]
        }
        result = self.run_script(
            "https://m5.amap.com/shield/search_poi/sug",
            body,
        )
        self.assertEqual([city["city"] for city in result["city_list"]], ["A", "B", "C"])
        self.assertEqual(
            [item["id"] for item in result["city_list"][0]["tip_list"]],
            ["a-keep-1", "a-keep-2"],
        )
        self.assertEqual(result["city_list"][1]["tip_list"], [])
        self.assertEqual(result["city_list"][2]["tip_list"], [])

    def test_main_page_card_lists_keep_only_existing_allowed_cards(self):
        body = {
            "data": {
                "cardList": [
                    {"dataKey": "ContinueNavigationCard"},
                    {"dataKey": "PromotionCard"},
                    {"dataKey": "FrequentLocation"},
                    {"dataKey": "LoginCard"},
                ],
                "mapBizList": [
                    {"dataKey": "FindCarVirtualCard"},
                    {"dataKey": "PromotionCard"},
                ],
            }
        }
        result = self.run_script(
            "https://m5.amap.com/faas/amap-navigation/main-page",
            body,
        )
        self.assertEqual(
            [item["dataKey"] for item in result["data"]["cardList"]],
            ["ContinueNavigationCard", "FrequentLocation", "LoginCard"],
        )
        self.assertEqual(
            [item["dataKey"] for item in result["data"]["mapBizList"]],
            ["FindCarVirtualCard"],
        )

    def test_route_info_filters_ads_and_music_without_changing_other_entries(self):
        body = {
            "data": {
                "tbt": {
                    "event": [
                        {"dynamic_id_s": "ads-123"},
                        {"dynamic_id_s": "road-event"},
                    ]
                },
                "front_end": {
                    "assistant": {"skin": "ad"},
                    "guide_tips": [
                        {"biz_type": "music"},
                        {"biz_type": "traffic"},
                    ],
                    "download": [
                        {"dynamic_id_s": "ads-456"},
                        {"dynamic_id_s": "normal-voice"},
                    ],
                },
            }
        }
        result = self.run_script(
            "https://m5.amap.com/perception/drive/routeInfo",
            body,
        )
        data = result["data"]
        self.assertEqual(data["tbt"]["event"], [{"dynamic_id_s": "road-event"}])
        self.assertNotIn("assistant", data["front_end"])
        self.assertEqual(data["front_end"]["guide_tips"], [{"biz_type": "traffic"}])
        self.assertEqual(
            data["front_end"]["download"],
            [{"dynamic_id_s": "normal-voice"}],
        )

    def test_empty_response_completes_without_attempting_json_parse(self):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("sources/amap/rucu6_amap.js", "utf8");
let doneResult, parseCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: "https://m5.amap.com/ws/perception/drive/routeInfo" },
  $response: { body: "" },
  $done(value) { doneResult = value; }
};
vm.runInNewContext(source, context, { timeout: 5000 });
if (!doneResult || Object.keys(doneResult).length !== 0) {
  throw new Error("empty Amap response was not passed through");
}
if (parseCalls !== 0) throw new Error("empty Amap response still attempted JSON.parse");
process.stdout.write(JSON.stringify({ parseCalls, doneResult }));
"""
        result = subprocess.run(
            [NODE, "-e", runner],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        self.assertEqual(json.loads(result.stdout)["parseCalls"], 0)

    def test_script_uses_in_place_compaction_instead_of_filter_allocations(self):
        source = (ROOT / "sources/amap/rucu6_amap.js").read_text(encoding="utf-8")
        self.assertNotIn(".filter(", source)
        self.assertNotIn("newLists", source)
        self.assertNotIn("newTips", source)
        self.assertIn("function compactInPlace", source)
        self.assertIn("tips[write++] = item", source)
        self.assertIn("tips.length = write", source)


if __name__ == "__main__":
    unittest.main()
