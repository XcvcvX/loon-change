import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class TargetedUpstreamAppRuleTests(unittest.TestCase):
    def test_merge_pipeline_keeps_only_targeted_local_xianyu_and_jd_additions(self):
        base_text = r"""#!name=fixture
[Rewrite]
^https?:\/\/m.360buyimg\.com\/mobilecms\/s1125x2436_jfs\/ reject-200
request if ${url} ~= /^https?:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads\// then reject_dict(200)
[Script]
[Rule]
[MITM]
hostname = m.360buyimg.com, img*.360buyimg.com, acs.m.goofish.com, g-acs.m.goofish.com
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.plugin"
            output = root / "merged.plugin"
            provenance = root / "provenance.json"
            base.write_text(base_text, encoding="utf-8")
            command = [
                sys.executable, str(ROOT / "merge_plugins.py"),
                "--base", str(base),
                "--extra", "none",
                "--filter", "none",
                "--myblockads", "none",
                "--alipayadblock", "none",
                "--out", str(output),
                "--provenance-out", str(provenance),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + "\n" + completed.stderr)
            merged = output.read_text(encoding="utf-8")
            self.assertIn("GOOFISH-SPLASH", merged)
            self.assertIn("realTimeAd", (ROOT / "scripts/xianyu/goofish.js").read_text(encoding="utf-8"))
            self.assertIn(r"s1\d{3}x2\d{3}_jfs", merged)
            self.assertIn("material-video", merged)
            self.assertFalse(any(r"idlecommerce\.splash" in line and "reject_dict" in line for line in merged.splitlines()))
            self.assertNotIn("s1125x2436_jfs", merged)
            self.assertIn("xianyu_jd_targeted", provenance.read_text(encoding="utf-8"))

    def test_xianyu_script_removes_real_time_splash_node_without_parsing_empty_splash(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xianyu runtime test")
        source_path = ROOT / "scripts" / "xianyu" / "goofish.js"
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(url, body) {
  let result, parseCalls = 0, stringifyCalls = 0;
  const trackedJSON = {
    parse(...args) { parseCalls++; return JSON.parse(...args); },
    stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
  };
  vm.runInNewContext(source, {
    JSON: trackedJSON,
    $request: { url },
    $response: { body },
    $done(value) { result = value; },
    console: { log() {} }
  });
  return { result, parseCalls, stringifyCalls };
}
const splashUrl = "https://acs.m.goofish.com/gw/mtop.taobao.idlecommerce.splash.ads/1.0/";
const noAd = run(splashUrl, '{"data":{"other":1}}');
if (noAd.parseCalls !== 0 || noAd.stringifyCalls !== 0) throw new Error("empty splash fast path parsed JSON");
const ad = run(splashUrl, JSON.stringify({
  data: { realTimeAd: { mamaAd: { imageMaterial: { showNow: "true" } } }, keep: 1 }
}));
if (ad.parseCalls !== 1 || ad.stringifyCalls !== 1) throw new Error("splash should parse/stringify once");
const parsed = JSON.parse(ad.result.body);
if ("realTimeAd" in parsed.data || parsed.data.keep !== 1) throw new Error("realTimeAd removal changed unrelated data");
const feedUrl = "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/";
const feed = run(feedUrl, JSON.stringify({ data: { sections: [
  { template: { name: "fish_home_advertise_card_d3" }, data: { cardTypeValue: "Item" } },
  { data: { cardType: "mamaAD", cardTypeValue: "Item" } },
  { data: { cardType: "homeMultiBanner", cardTypeValue: "Item" } },
  { data: { cardTypeValue: "Item", id: "organic" } }
] } }));
const sections = JSON.parse(feed.result.body).data.sections;
if (sections.length !== 1 || sections[0].data.id !== "organic") throw new Error("new Xianyu ad-card markers were not filtered");
if (feed.parseCalls !== 1 || feed.stringifyCalls !== 1) throw new Error("feed handler must retain one JSON round trip");
'''
        completed = subprocess.run(
            [node, "-e", harness, str(source_path)],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)




class XianyuLazySerializationRuntimeTests(unittest.TestCase):
    runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult, parseCalls = 0, stringifyCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: payload.url },
  $response: { body: nativeJSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {} }
};
vm.runInNewContext(source, context, { timeout: 5000 });
const output = doneResult && typeof doneResult.body === "string"
  ? nativeJSON.parse(doneResult.body)
  : null;
process.stdout.write(nativeJSON.stringify({
  done: doneResult || null,
  body: output,
  parseCalls,
  stringifyCalls
}));
"""

    def run_script(self, url, body):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xianyu runtime test")
        completed = subprocess.run(
            [node, "-e", self.runner, str(ROOT / "scripts" / "xianyu" / "goofish.js")],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_unchanged_responses_skip_stringify_across_all_regular_routes(self):
        cases = [
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/",
                {"data": {
                    "sections": [{"data": {"cardTypeValue": "Item", "id": "organic"}}],
                    "homeTopList": []
                }},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.home/1.0/",
                {"data": {"sections": [{
                    "data": {"bizType": "normal", "cardType": "normal", "cardTypeValue": "Item"}
                }]}},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.home.whale.modulet/1.0/",
                {"data": {"container": {"keep": True}}},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.idle.user.page.my.adapter/1.0/",
                {"data": {"container": {"sections": [
                    {"index": 0}, {"index": 1}, {"index": 3}
                ]}, "ability": []}},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.circle.list/1.0/",
                {"data": {
                    "circleList": [{"circleId": "1"}],
                    "next": {"headList": [
                        {"bizCode": "main"},
                        {"bizCode": "recycle", "showInfo": {"rightTagImage": {}}}
                    ]},
                    "headList": []
                }},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.nearby.itemdetail.enter/1.0/",
                {"data": {
                    "targetUrl": "", "trackParams": {"itemIds": ""},
                    "nearbyItemInfoList": [], "name": "", "desc": "", "poiName": ""
                }},
            ),
            (
                "https://g-acs.m.goofish.com/gw/mtop.taobao.idlemtopsearch.search/1.0/",
                {"data": {
                    "resultList": [{"data": {"cardType": "normal", "template": {"name": "organic"}}}],
                    "topList": []
                }},
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.flow.plat.section/1.0/",
                {"data": {"data": {"components": [{"key": "ordinary"}]}}},
            ),
        ]
        for url, body in cases:
            with self.subTest(url=url):
                result = self.run_script(url, body)
                self.assertEqual(result["done"], {})
                self.assertIsNone(result["body"])
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 0)

    def test_existing_cleanup_mutations_still_serialize_once(self):
        cases = [
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/",
                {"data": {
                    "widgetReturnDO": {"ad": 1},
                    "bannerReturnDO": {"ad": 1},
                    "homeTopList": [{"ad": 1}],
                    "sections": [
                        {"template": {"name": "fish_home_advertise_card_d3"},
                         "data": {"cardTypeValue": "Item"}},
                        {"data": {"cardTypeValue": "Item", "id": "organic"}}
                    ]
                }},
                lambda body: (
                    "widgetReturnDO" not in body["data"] and
                    "bannerReturnDO" not in body["data"] and
                    body["data"]["homeTopList"] == [] and
                    [item["data"]["id"] for item in body["data"]["sections"]] == ["organic"]
                ),
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.home/1.0/",
                {"data": {"sections": [
                    {"data": {"bizType": "AD"}},
                    {"data": {"bizType": "normal", "cardType": "normal", "cardTypeValue": "Item"}}
                ]}},
                lambda body: len(body["data"]["sections"]) == 1 and
                    body["data"]["sections"][0]["data"]["bizType"] == "normal",
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.home.whale.modulet/1.0/",
                {"data": {"container": {"sections": [1], "keep": True}}},
                lambda body: "sections" not in body["data"]["container"] and
                    body["data"]["container"]["keep"] is True,
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.idle.user.page.my.adapter/1.0/",
                {"data": {"container": {"sections": [
                    {"index": 0}, {"index": 2}, {"index": 3}
                ]}, "ability": [1]}},
                lambda body: [x["index"] for x in body["data"]["container"]["sections"]] == [0, 3]
                    and body["data"]["ability"] == [],
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.circle.list/1.0/",
                {"data": {
                    "circleList": [{"circleId": "9"}, {"circleId": "1"}],
                    "next": {"headList": [
                        {"bizCode": "other"},
                        {"bizCode": "recycle", "showInfo": {"rightTagImage": {"url": "ad"}}}
                    ]},
                    "headList": [{"bizCode": "other"}]
                }},
                lambda body: [x["circleId"] for x in body["data"]["circleList"]] == ["1"]
                    and len(body["data"]["next"]["headList"]) == 1
                    and body["data"]["next"]["headList"][0]["showInfo"]["rightTagImage"] == {}
                    and body["data"]["headList"] == [],
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.nearby.itemdetail.enter/1.0/",
                {"data": {
                    "targetUrl": "https://example.com", "trackParams": {"itemIds": "123"},
                    "nearbyItemInfoList": [1], "name": "name", "desc": "desc", "poiName": "poi"
                }},
                lambda body: body["data"]["targetUrl"] == "" and
                    body["data"]["trackParams"]["itemIds"] == "" and
                    body["data"]["nearbyItemInfoList"] == [] and
                    body["data"]["name"] == "" and body["data"]["desc"] == "" and
                    body["data"]["poiName"] == "",
            ),
            (
                "https://g-acs.m.goofish.com/gw/mtop.taobao.idlemtopsearch.search/1.0/",
                {"data": {
                    "resultList": [
                        {"data": {"cardType": "mamaAD"}},
                        {"data": {"cardType": "normal", "template": {"name": "organic"}}}
                    ],
                    "resultPrefixBar": {"ad": 1},
                    "topList": [1]
                }},
                lambda body: len(body["data"]["resultList"]) == 1 and
                    body["data"]["resultList"][0]["data"]["cardType"] == "normal" and
                    "resultPrefixBar" not in body["data"] and body["data"]["topList"] == [],
            ),
            (
                "https://acs.m.goofish.com/gw/mtop.taobao.idle.local.flow.plat.section/1.0/",
                {"data": {"data": {"components": [
                    {"key": "fish_home_activity_enter_cardV1"}, {"key": "ordinary"}
                ]}}},
                lambda body: body["data"]["data"]["components"] == [{"key": "ordinary"}],
            ),
        ]
        for url, body, verify in cases:
            with self.subTest(url=url):
                result = self.run_script(url, body)
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 1)
                self.assertIsNotNone(result["body"])
                self.assertTrue(verify(result["body"]))



if __name__ == "__main__":
    unittest.main()
