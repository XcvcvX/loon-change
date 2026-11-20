import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_amap import LOCAL, REMOTE, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "amap" / "amap.js"
NODE = shutil.which("node")


class AmapRStoreOptimizerTests(unittest.TestCase):
    def test_local_script_has_guard_and_in_place_compaction(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Amap R-Store supported-route guard v1", source)
        self.assertIn("function compactInPlace(items, keep)", source)
        self.assertNotIn(".filter(", source)
        self.assertLess(source.index("const shouldProcess ="), source.index("JSON.parse($response.body)"))
        self.assertIn("if (!$response.body) {", source)

    def test_all_fourteen_active_triggers_migrate_and_are_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://m%d.amap.com/api script-path=%s,tag=AMAP-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(14)
        ) + "\n[MITM]\nhostname = *.amap.com\n"
        result = rewrite_plugin(fixture)
        self.assertEqual(result.count(LOCAL), 14)
        self.assertNotIn(REMOTE, result)
        self.assertEqual(rewrite_plugin(result), result)
        partial = "\n".join(line for line in fixture.splitlines() if "tag=AMAP-3," not in line)
        with self.assertRaisesRegex(ValueError, "expected 14"):
            rewrite_plugin(partial)

    def test_route_guard_covers_all_fourteen_upstream_endpoint_families(self):
        source = SOURCE.read_text(encoding="utf-8")
        expected = [
            "/aos/perception/publicTravel/beforeNavi", "/bus/plan/integrate",
            "/c3frontend/af-hotel/page/main", "/c3frontend/af-launch/page/main",
            "/perception/drive/routeInfo", "/perception/drive/routePlan",
            "/shield/search/common/coupon/info", "/shield/search/poi/detail",
            "/shield/search_business/process/marketingOperationStructured",
            "/shield/search_poi/", "/faas/amap-navigation/card-service-plan-home",
            "/faas/amap-navigation/main-page", "/shield/frogserver/aocs/updatable/1",
            "/shield/dsp/profile/index/nodefaasv", "/shield/search/nearbyrec_smart",
            "/boss/car/order/content_info", "/boss/order_web/friendly_information",
            "/promotion-web/resource", "/sharedtrip/taxi/order_detail_car_tips"
        ]
        for route in expected:
            self.assertIn('url.includes("' + route + '")', source)

    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeJSON = JSON;
let parseCount = 0, stringifyCount = 0, doneResult;
const trackedJSON = {
  parse(value) { parseCount++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCount++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: {url: payload.url},
  $response: {body: payload.body},
  $done(value) { doneResult = value; },
  console: {log(){}, warn(){}, error(){}}
};
vm.runInNewContext("Array.prototype.filter = function(){ throw new Error('Array.filter used'); };", context);
vm.runInNewContext(source, context, {timeout:5000});
process.stdout.write(nativeJSON.stringify({doneResult, parseCount, stringifyCount}));
"""
        result = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}),
            text=True, capture_output=True, check=True, timeout=10
        )
        return json.loads(result.stdout)

    def test_empty_body_and_unmatched_route_skip_json_parse(self):
        empty = self.run_script("https://m1.amap.com/ws/aos/perception/publicTravel/beforeNavi?", "")
        self.assertEqual(empty["doneResult"], {})
        self.assertEqual(empty["parseCount"], 0)
        unmatched = self.run_script("https://m1.amap.com/ws/shield/unused/large", '{"payload":1}')
        self.assertEqual(unmatched["doneResult"], {})
        self.assertEqual(unmatched["parseCount"], 0)
        self.assertEqual(unmatched["stringifyCount"], 0)

    def test_before_navi_keeps_existing_mutation(self):
        body = {"data": {"common_data": {
            "bus_plan_bottom_event": {"data": [{"id": 1}]},
            "bus_plan_segment_event": {"data": [{"id": 2}]}
        }, "front_end": {"assistant": [{"id": "promo"}]}}}
        result = self.run_script(
            "https://m1.amap.com/ws/aos/perception/publicTravel/beforeNavi?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["common_data"]["bus_plan_bottom_event"]["data"], [])
        self.assertEqual(output["data"]["common_data"]["bus_plan_segment_event"]["data"], [])
        self.assertEqual(output["data"]["front_end"]["assistant"], [])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_search_suggestion_filter_preserves_kept_item_order(self):
        body = {"tip_list": [
            {"tip": {"datatype_spec": "1", "result_type": "poi", "task_tag": "normal"}, "id": 1},
            {"tip": {"datatype_spec": "12", "result_type": "poi", "task_tag": "normal"}, "id": 2},
            {"tip": {"datatype_spec": "1", "result_type": "ad", "task_tag": "normal"}, "id": 3},
            {"tip": {"datatype_spec": "1", "result_type": "poi", "task_tag": "normal"}, "id": 4}
        ]}
        result = self.run_script(
            "https://m1.amap.com/ws/shield/search_poi/sug?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["id"] for x in output["tip_list"]], [1, 4])


if __name__ == "__main__":
    unittest.main()
