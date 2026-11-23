import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")
SCRIPT = ROOT / "scripts" / "meituan" / "meituan.js"


@unittest.skipUnless(NODE, "Node.js is required for Meituan runtime tests")
class MeituanAllocationRuntimeTests(unittest.TestCase):
    runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult, parseCalls = 0, stringifyCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: input.url, headers: input.headers || {} },
  $response: { body: nativeJSON.stringify(input.body) },
  $done(value) { doneResult = value; }
};
vm.runInNewContext(source, context, { timeout: 5000 });
process.stdout.write(nativeJSON.stringify({
  done: doneResult || null, parseCalls, stringifyCalls
}));
"""

    def run_script(self, path, body):
        completed = subprocess.run(
            [NODE, "-e", self.runner, str(SCRIPT)],
            input=json.dumps({"url": "https://api.meituan.com" + path, "body": body}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_tab_area_compacts_in_place_and_preserves_allowlist_and_order(self):
        body = {"data": {"resource": {"tabArea": [
            {"tabName": "homepage"}, {"tabName": "video"}, {"tabName": "mine"},
            {"tabName": "xiaotuan"}, {"tabName": "other"}
        ]}}}
        result = self.run_script("/aggroup/indexTab", body)
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        tabs = json.loads(result["done"]["body"])["data"]["resource"]["tabArea"]
        self.assertEqual([x["tabName"] for x in tabs], ["homepage", "mine", "other"])

    def test_clean_mine_and_miniprogram_keep_exact_existing_items(self):
        mine = {"children": [{"name": "keep"}, {"name": "mine_cross_recommend"}, {"name": "also_keep"}]}
        result = self.run_script("/usercenter/display", mine)
        self.assertEqual(json.loads(result["done"]["body"])["children"], [{"name":"keep"},{"name":"also_keep"}])
        mini = {"data": [{"name":"首页"},{"name":"广告"},{"name":"神券"},{"name":"我的"}]}
        result = self.run_script("/api/miniprogram/tabbar/all/query", mini)
        self.assertEqual(json.loads(result["done"]["body"])["data"], [{"name":"首页"},{"name":"神券"},{"name":"我的"}])

    def test_hot_recommend_compacts_nested_segments_and_clears_bubble(self):
        body = {"data": {"segmentsV2": [
            {"id":"empty", "hotwordSegments":[{"pageName":"EntranceHotwordsV2Hotwords"}]},
            {"id":"kept", "hotwordSegments":[{"pageName":"ordinary"},{"pageName":"EntranceHotwordsV2ContentCard"}]},
        ], "aiSearchBubble":{"bubbleTexts":["ad"]}}}
        result = self.run_script("/searchpage/hotword/city/divide/hotrecommend/city", body)
        self.assertEqual(result["stringifyCalls"], 1)
        data = json.loads(result["done"]["body"])["data"]
        self.assertEqual([x["id"] for x in data["segmentsV2"]], ["kept"])
        self.assertEqual(data["segmentsV2"][0]["hotwordSegments"], [{"pageName":"ordinary"}])
        self.assertEqual(data["aiSearchBubble"]["bubbleTexts"], [])

    def test_default_word_and_area_cleanup_mutate_arrays_without_replacing_them(self):
        body = {"searchIntroduceResponse":{
            "defaultWordRes":{"defaultWordItems":[1]}, "HotWordInfos":[2]
        }}
        result = self.run_script("/searchpage/defaultword", body)
        output = json.loads(result["done"]["body"])
        self.assertEqual(output["searchIntroduceResponse"]["defaultWordRes"]["defaultWordItems"], [])
        self.assertEqual(output["searchIntroduceResponse"]["HotWordInfos"], [])
        area = {"data":{"resource":{"topBannerArea":[1]},"resourcesMap":{"topBannerArea":[2]}}}
        result = self.run_script("/mop/entry/shoppingCartEntry", area)
        output = json.loads(result["done"]["body"])
        self.assertEqual(output["data"]["resource"]["topBannerArea"], [])
        self.assertEqual(output["data"]["resourcesMap"]["topBannerArea"], [])

    def test_ai_skill_nested_json_is_cleaned_without_object_keys_array(self):
        body = {"data": json.dumps({"skills":{"a":1,"b":2},"other":True})}
        result = self.run_script("/assistant/getAppClientHornConfig", body)
        output = json.loads(result["done"]["body"])
        self.assertEqual(json.loads(output["data"]), {"skills":{},"other":True})

    def test_already_clean_responses_skip_serialization(self):
        cases = [
            ("/usercenter/display", {"children":[{"name":"ordinary"}]}),
            ("/aggroup/indexTab", {"data":{"resource":{"tabArea":[{"tabName":"homepage"},{"tabName":"mine"}]}}}),
            ("/searchpage/defaultword", {"searchIntroduceResponse":{"defaultWordRes":{"defaultWordItems":[]},"HotWordInfos":[]}}),
            ("/assistant/getAppClientHornConfig", {"data":json.dumps({"skills":{},"other":1})}),
        ]
        for path, body in cases:
            with self.subTest(path=path):
                result = self.run_script(path, body)
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 0)
                self.assertEqual(result["done"], {})


class MeituanSourceInvariantTests(unittest.TestCase):
    def test_hot_paths_avoid_replacement_arrays_and_callback_array_methods(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("// loon-change: Meituan allocation-light response cleanup v1", source)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)
        self.assertNotIn(".forEach(", source)
        self.assertNotIn("Object.keys(data.skills)", source)
        self.assertNotIn("const kept = []", source)
        self.assertIn("tabs.length = write;", source)
        self.assertIn("hotwords.length = hotwordWrite;", source)
