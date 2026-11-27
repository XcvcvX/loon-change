#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_amap_rucu6 import (
    HELPER,
    OLD_HELPER,
    REWRITES,
    ROUTE_MARKER,
    optimize_source,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sources" / "amap" / "rucu6_amap.js"
NODE = shutil.which("node")


class AmapRucu6OptimizerTests(unittest.TestCase):
    def test_optimizer_is_idempotent_and_all_callback_call_sites_are_gone(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(source.count("compactAmapRucu6("), 12)
        self.assertNotIn("compactInPlace(", source)
        self.assertIn("const length = items.length;", source)
        self.assertIn("if (write !== read) items[write] = item;", source)
        self.assertIn("if (write !== length) items.length = write;", source)

    def test_optimizer_regenerates_the_known_patched_upstream_form(self):
        optimized = SCRIPT.read_text(encoding="utf-8")
        legacy = optimized.replace(HELPER, OLD_HELPER, 1)
        legacy = legacy.replace("    " + ROUTE_MARKER + "\n", "", 1)
        for old, new, expected, _description in REWRITES:
            self.assertGreaterEqual(legacy.count(new), expected)
            legacy = legacy.replace(new, old, expected)
        self.assertNotIn("compactAmapRucu6(", legacy)
        self.assertEqual(optimize_source(legacy), optimized)

    def test_optimizer_fails_closed_when_one_specialized_route_drifts(self):
        source = SCRIPT.read_text(encoding="utf-8")
        damaged = source.replace(
            'compactAmapRucu6(obj.data.children, "withoutSchema");',
            'compactAmapRucu6(obj.data.children, "unknownMode");',
            1,
        )
        with self.assertRaisesRegex(ValueError, "withoutSchema"):
            optimize_source(damaged)


@unittest.skipUnless(NODE, "Node.js is required for Amap Rucu6 runtime regressions")
class AmapRucu6RuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync(process.argv[1], "utf8");
source = source.replace(
  "let obj = JSON.parse($response.body);",
  "let obj = JSON.parse($response.body); " +
    "Array.prototype.filter = function(){ throw new Error('filter called'); }; " +
    "Array.prototype.map = function(){ throw new Error('map called'); }; " +
    "Array.prototype.forEach = function(){ throw new Error('forEach called'); };"
);
let doneResult;
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const context = {
  $request: { url: payload.url },
  $response: { body: JSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.runInNewContext(source, context, { timeout: 5000 });
if (!doneResult || typeof doneResult.body !== "string") {
  throw new Error("Amap Rucu6 script did not return a response body");
}
process.stdout.write(doneResult.body);
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": url, "body": body}),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_all_eight_modes_preserve_filtering_order_and_output(self):
        # withoutSchema also deliberately preserves falsy values, matching the prior predicate.
        schema = self.run_script(
            "https://m5.amap.com/faas/amap-navigation/card-service-plan-home",
            {
                "data": {
                    "children": [
                        {"id": "keep"},
                        {"id": "drop", "schema": {}},
                        None,
                        False,
                        0,
                        "",
                        {"id": "drop-null-schema", "schema": None},
                    ]
                }
            },
        )
        self.assertEqual(
            schema["data"]["children"],
            [{"id": "keep"}, None, False, 0, ""],
        )

        home = self.run_script(
            "https://m5.amap.com/faas/amap-navigation/main-page",
            {
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
            },
        )
        self.assertEqual(
            [item["dataKey"] for item in home["data"]["cardList"]],
            ["ContinueNavigationCard", "FrequentLocation", "LoginCard"],
        )
        self.assertEqual(
            [item["dataKey"] for item in home["data"]["mapBizList"]],
            ["FindCarVirtualCard"],
        )

        route_info = self.run_script(
            "https://m5.amap.com/perception/drive/routeInfo",
            {
                "data": {
                    "tbt": {"event": [{"dynamic_id_s": "ads-123"}, {"dynamic_id_s": "road"}]},
                    "front_end": {
                        "assistant": {"skin": "ad"},
                        "guide_tips": [{"biz_type": "music"}, {"biz_type": "traffic"}],
                        "download": [{"dynamic_id_s": "ads-456"}, {"dynamic_id_s": "voice"}],
                    },
                }
            },
        )
        self.assertEqual(route_info["data"]["tbt"]["event"], [{"dynamic_id_s": "road"}])
        self.assertNotIn("assistant", route_info["data"]["front_end"])
        self.assertEqual(route_info["data"]["front_end"]["guide_tips"], [{"biz_type": "traffic"}])
        self.assertEqual(
            route_info["data"]["front_end"]["download"],
            [{"dynamic_id_s": "voice"}],
        )

        route_plan = self.run_script(
            "https://m5.amap.com/perception/drive/routePlan",
            {
                "data": {
                    "front_end": {
                        "assistant": {"ad": True},
                        "global_guide_data": {},
                        "route_search": {},
                        "start_button_tips": {},
                        "download": [{"dynamic_id_s": "ads-789"}, {"dynamic_id_s": "normal"}],
                    },
                    "tbt": {"event": [{"dynamic_id_s": "ads-555"}, {"dynamic_id_s": "turn"}]},
                }
            },
        )
        self.assertEqual(route_plan["data"]["tbt"]["event"], [{"dynamic_id_s": "turn"}])
        self.assertEqual(
            route_plan["data"]["front_end"]["download"],
            [{"dynamic_id_s": "normal"}],
        )
        for key in ("assistant", "global_guide_data", "route_search", "start_button_tips"):
            self.assertNotIn(key, route_plan["data"]["front_end"])

        profile = self.run_script(
            "https://m5.amap.com/shield/dsp/profile/index/nodefaasv3",
            {
                "data": {
                    "cardList": [
                        {"dataKey": "MyOrderCard"},
                        {"dataKey": "PromotionCard"},
                        {"dataKey": "MyOrderCard", "id": "second"},
                    ],
                    "tipData": {"ad": True},
                    "memberInfo": {"badge": True},
                    "topMixedCard": {"ad": True},
                }
            },
        )
        self.assertEqual(
            [item["dataKey"] for item in profile["data"]["cardList"]],
            ["MyOrderCard", "MyOrderCard"],
        )
        self.assertNotIn("tipData", profile["data"])
        self.assertNotIn("memberInfo", profile["data"])
        self.assertNotIn("topMixedCard", profile["data"])

        nearby = self.run_script(
            "https://m5.amap.com/shield/search/nearbyrec_smart",
            {"data": {"modules": ["head", "ad", "search_hot_words", "feed_rec", "promo"]}},
        )
        self.assertEqual(
            nearby["data"]["modules"],
            ["head", "search_hot_words", "feed_rec"],
        )

        search = self.run_script(
            "https://m5.amap.com/shield/search_poi/mps",
            {
                "data": {
                    "modules": {
                        "list_data": {
                            "data": {
                                "content": [
                                    {"item_type": "brandAdCard"},
                                    {"item_type": "poi"},
                                    {"item_type": "toplist_al"},
                                    {"item_type": "shop"},
                                ]
                            }
                        }
                    }
                }
            },
        )
        self.assertEqual(
            [item["item_type"] for item in search["data"]["modules"]["list_data"]["data"]["content"]],
            ["poi", "shop"],
        )

    def test_helper_reads_array_length_once_and_only_sets_length_when_compacted(self):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const context = {
  $request: { url: "https://m5.amap.com/perception/drive/routeInfo" },
  $response: { body: "" },
  $done() {}
};
vm.runInNewContext(source, context, { timeout: 5000 });
const target = [{dataKey:"PromotionCard"}, {dataKey:"LoginCard"}];
let lengthReads = 0, lengthWrites = 0;
const tracked = new Proxy(target, {
  get(object, key, receiver) {
    if (key === "length") lengthReads++;
    return Reflect.get(object, key, receiver);
  },
  set(object, key, value, receiver) {
    if (key === "length") lengthWrites++;
    return Reflect.set(object, key, value, receiver);
  }
});
context.tracked = tracked;
vm.runInNewContext('compactAmapRucu6(tracked, "homeCards")', context, { timeout: 5000 });
process.stdout.write(JSON.stringify({
  lengthReads,
  lengthWrites,
  retained: target.map(item => item.dataKey)
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["lengthReads"], 1)
        self.assertEqual(result["lengthWrites"], 1)
        self.assertEqual(result["retained"], ["LoginCard"])


if __name__ == "__main__":
    unittest.main()
