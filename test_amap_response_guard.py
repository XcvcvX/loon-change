import shutil
import subprocess
import unittest
from pathlib import Path


class AmapResponseGuardTests(unittest.TestCase):
    def test_unrelated_response_skips_json_parse(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required")
        source = Path(__file__).with_name("sources").joinpath("amap", "rucu6_amap.js")
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(url, body) {
  let result;
  let parses = 0;
  const json = {
    parse(value) { parses++; return JSON.parse(value); },
    stringify(value) { return JSON.stringify(value); }
  };
  const context = {
    JSON: json,
    $request: { url },
    $response: { body: JSON.stringify(body) },
    $done(value) { result = value; }
  };
  vm.runInNewContext(source, context);
  return { result, parses };
}
const unrelated = run("https://m5.amap.com/ws/unmatched/large-feed", { data: { huge: "x".repeat(50000) } });
if (unrelated.parses !== 0) throw new Error("unrelated body was parsed");
if (!unrelated.result || Object.keys(unrelated.result).length !== 0) throw new Error("unrelated response was modified");
const matched = run("https://m5.amap.com/ws/shield/search_poi/sug?keywords=test", {
  tip_list: [{ id: 1, tip: { result_type: "ad" } }, { id: 2, tip: { result_type: "normal" } }]
});
if (matched.parses !== 1) throw new Error("matched response should be parsed exactly once");
if (!matched.result || typeof matched.result.body !== "string") throw new Error("matched response was not returned");
const output = JSON.parse(matched.result.body);
if (output.tip_list.length !== 1 || output.tip_list[0].id !== 2) throw new Error("matched filtering behavior changed");
const empty = run("https://m5.amap.com/ws/shield/search_poi/sug?keywords=test", "");
if (empty.parses !== 0 || !empty.result || Object.keys(empty.result).length !== 0) throw new Error("empty body guard regressed");
"""
        completed = subprocess.run([node, "-e", harness, str(source)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)

    def test_supported_path_inventory_matches_response_branches(self):
        source = Path(__file__).with_name("sources").joinpath("amap", "rucu6_amap.js").read_text(encoding="utf-8")
        expected = [
            "/aos/perception/publicTravel/beforeNavi", "/boss/car/order/content_info",
            "/boss/order_web/friendly_information", "/bus/plan/integrate",
            "/c3frontend/af-hotel/page/main", "/c3frontend/af-launch/page/main",
            "/c3frontend/af-nearby/nearby", "/faas/amap-navigation/card-service-plan-home",
            "/faas/amap-navigation/main-page", "/perception/drive/routeInfo",
            "/perception/drive/routePlan", "/promotion-web/resource",
            "/shield/dsp/profile/index/nodefaasv3", "/shield/frogserver/aocs/updatable/",
            "/shield/search/common/coupon/info", "/shield/search/nearbyrec_smart",
            "/shield/search/poi/detail", "/shield/search_bff/hotword",
            "/shield/search_poi/search/sp", "/shield/search_poi/mps",
            "/shield/search_poi/sug", "/shield/search_poi/tips_operation_location",
            "/valueadded/alimama/splash_screen",
        ]
        for path in expected:
            self.assertIn('"' + path + '"', source)
