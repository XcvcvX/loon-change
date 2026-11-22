import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for Jingdong runtime tests")
class JingdongLazySerializationTests(unittest.TestCase):
    def run_script(self, url, body, argument=None):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(process.argv[1], "utf8");
let doneResult, parseCalls = 0, stringifyCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
vm.runInNewContext(source, {
  JSON: trackedJSON,
  $request: { url: payload.url },
  $response: { body: nativeJSON.stringify(payload.body) },
  $argument: payload.argument,
  $done(value) { doneResult = value; }
}, { timeout: 5000 });
const output = doneResult && typeof doneResult.body === "string"
  ? nativeJSON.parse(doneResult.body) : null;
process.stdout.write(nativeJSON.stringify({
  done: doneResult || null, body: output, parseCalls, stringifyCalls
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(ROOT / "scripts/jingdong/jd.js")],
            input=json.dumps({"url": url, "body": body, "argument": argument}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_already_clean_responses_skip_serialization_for_every_route(self):
        cases = [
            ("functionId=start", {"images": [], "showTimesDaily": 0, "keep": 1}),
            ("functionId=welcomeHome", {"floorList": [{"type": "topTab"}], "webViewFloorList": [], "keep": 1}),
            ("functionId=readCustomSurfaceList", {"result": {"modeMap": {
                "dark": {"navigationAll": [{"functionId": "index"}]},
                "normal": {"navigationAll": [{"functionId": "home"}]}
            }}}),
            ("functionId=deliverLayer", {"floors": [{"mId": "normal"}]}),
            ("functionId=getTabHomeInfo", {"result": {"keep": 1}}),
            ("functionId=myOrderInfo", {"floors": [{"mId": "normal"}]}),
            ("functionId=personinfoBusiness", {"floors": [{"mId": "normal"}], "others": {"floors": [{"mId": "normal"}]}}),
        ]
        for marker, body in cases:
            with self.subTest(route=marker):
                result = self.run_script("https://api.m.jd.com/client.action?" + marker, body)
                self.assertEqual(result["done"], {})
                self.assertIsNone(result["body"])
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 0)

    def test_all_existing_cleanup_branches_still_mutate_and_serialize_once(self):
        cases = [
            ("functionId=start", {"images": ["splash"], "showTimesDaily": 3}, lambda b: b["images"] == [] and b["showTimesDaily"] == 0),
            ("functionId=welcomeHome", {"floorList": [{"type": "ad"}, {"type": "topTab"}], "webViewFloorList": [1], "promotionTabs": [1]}, lambda b: [x["type"] for x in b["floorList"]] == ["topTab"] and b["webViewFloorList"] == [] and "promotionTabs" not in b),
            ("functionId=readCustomSurfaceList", {"result": {"modeMap": {"dark": {"navigationAll": [{"functionId": "ad"}, {"functionId": "index"}]}}}}, lambda b: [x["functionId"] for x in b["result"]["modeMap"]["dark"]["navigationAll"]] == ["index"]),
            ("functionId=deliverLayer", {"bannerInfo": {"ad": 1}, "floors": [{"mId": "banner"}, {"mId": "normal"}]}, lambda b: "bannerInfo" not in b and [x["mId"] for x in b["floors"]] == ["normal"]),
            ("functionId=getTabHomeInfo", {"result": {"iconInfo": {}, "roofTop": {}, "keep": 1}}, lambda b: "iconInfo" not in b["result"] and "roofTop" not in b["result"]),
            ("functionId=myOrderInfo", {"floors": [{"mId": "bannerFloor"}, {"mId": "virtualServiceCenter", "data": {"virtualServiceCenters": [{"serviceList": [{"serviceTitle": "精选特惠"}, {"serviceTitle": "普通"}]}]}}, {"mId": "customerServiceFloor", "data": {"moreText": "更多", "moreIcon": "x"}}]}, lambda b: len(b["floors"]) == 2 and len(b["floors"][0]["data"]["virtualServiceCenters"][0]["serviceList"]) == 1 and b["floors"][1]["data"]["moreText"] == " "),
            ("functionId=personinfoBusiness", {"floors": [{"mId": "bigSaleFloor"}, {"mId": "basefloorinfo", "data": {"commonPopup": {}, "commonTips": [1]}}], "others": {"floors": [{"mId": "userinfo", "data": {"newPlusBlackCard": {}}}]}}, lambda b: len(b["floors"]) == 1 and "commonPopup" not in b["floors"][0]["data"] and b["floors"][0]["data"]["commonTips"] == [] and "newPlusBlackCard" not in b["others"]["floors"][0]["data"]),
        ]
        for marker, body, verify in cases:
            with self.subTest(route=marker):
                result = self.run_script("https://api.m.jd.com/client.action?" + marker, body)
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 1)
                self.assertIsNotNone(result["body"])
                self.assertTrue(verify(result["body"]))

    def test_optional_welcome_exclusions_remain_gated(self):
        body = {"floorList": [{"type": "topTab"}, {"type": "float"}]}
        result = self.run_script("https://api.m.jd.com/client.action?functionId=welcomeHome", body, {"jkds_enable": True})
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertEqual([x["type"] for x in result["body"]["floorList"]], ["topTab"])


if __name__ == "__main__":
    unittest.main()
