#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_xianyu import MARKER, optimize_source, validate_optimized_source

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "xianyu" / "goofish.js"
NODE = shutil.which("node")


class GoofishAllocationOptimizerTests(unittest.TestCase):
    def test_checked_in_runtime_is_optimized_and_idempotent(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(validate_optimized_source(source), source)
        self.assertEqual(source.count("new Set("), 1)
        self.assertNotIn("Object.keys(", source)
        self.assertNotIn("supportedPaths.some(", source)
        self.assertNotIn("const adTemplate =", source)

    def test_unreviewed_source_drift_fails_closed(self):
        source = SOURCE.read_text(encoding="utf-8").replace(
            "const isSupportedPath =", "const supportedPaths = [", 1
        )
        with self.assertRaisesRegex(ValueError, "optimized source drift"):
            optimize_source(source)


@unittest.skipUnless(NODE, "Node.js is required for Goofish runtime tests")
class GoofishAllocationRuntimeTests(unittest.TestCase):
    runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeJSON = JSON;
const nativeKeys = Object.keys.bind(Object);
let doneResult, parseCalls = 0, stringifyCalls = 0, objectKeysCalls = 0;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const trackedObject = {
  prototype: Object.prototype,
  keys(value) { objectKeysCalls++; return nativeKeys(value); }
};
const context = {
  JSON: trackedJSON, Object: trackedObject,
  $request: {url: payload.url},
  $response: {body: nativeJSON.stringify(payload.body)},
  $done(value) { doneResult = value; },
  console: {log() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
const output = doneResult && typeof doneResult.body === "string"
  ? nativeJSON.parse(doneResult.body)
  : null;
process.stdout.write(nativeJSON.stringify({
  done: doneResult || null, body: output, parseCalls, stringifyCalls, objectKeysCalls
}));
"""

    def run_script(self, url, body):
        completed = subprocess.run(
            [NODE, "-e", self.runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        return json.loads(completed.stdout)

    def test_empty_splash_fast_path_skips_parse_and_traversal(self):
        result = self.run_script(
            "https://acs.m.goofish.com/gw/mtop.taobao.idlecommerce.splash.ads/1.0/",
            {"data": {"ordinary": {"nested": [{"value": 1}]}}},
        )
        self.assertEqual(result["done"], {})
        self.assertEqual(result["parseCalls"], 0)
        self.assertEqual(result["stringifyCalls"], 0)
        self.assertEqual(result["objectKeysCalls"], 0)

    def test_splash_nested_cleanup_avoids_object_keys_allocations(self):
        body = {"data": {"keep": {"nested": [{"deeper": {"realTimeAd": {"id": 1}, "keep": 2}}]}}}
        result = self.run_script(
            "https://acs.m.goofish.com/gw/mtop.taobao.idlecommerce.splash.ads/1.0/", body
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertEqual(result["objectKeysCalls"], 0)
        self.assertNotIn("realTimeAd", result["body"]["data"]["keep"]["nested"][0]["deeper"])
        self.assertEqual(result["body"]["data"]["keep"]["nested"][0]["deeper"]["keep"], 2)

    def test_route_guard_and_nextfresh_filters_keep_existing_semantics(self):
        body = {"data": {
            "sections": [
                {"template": {"name": "fish_home_yunying_card_d3"}, "data": {"cardTypeValue": "Item"}},
                {"template": {"name": "fish_home_advertise_card_d3"}, "data": {"cardTypeValue": "Item"}},
                {"data": {"cardType": "mamaAD", "cardTypeValue": "Item"}},
                {"data": {"cardType": "homeMultiBanner", "cardTypeValue": "Item"}},
                {"data": {"cardTypeValue": "Item", "id": "organic"}}
            ],
            "homeTopList": [{"id": "removed"}]
        }}
        result = self.run_script(
            "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/", body
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertEqual([x["data"]["id"] for x in result["body"]["data"]["sections"]], ["organic"])
        self.assertEqual(result["body"]["data"]["homeTopList"], [])

    def test_profile_and_search_filters_keep_the_same_whitelists(self):
        profile = self.run_script(
            "https://acs.m.goofish.com/gw/mtop.idle.user.page.my.adapter/1.0/",
            {"data": {"container": {"sections": [{"index": 0}, {"index": 2}, {"index": 3}]},
                      "ability": [1]}},
        )
        self.assertEqual([x["index"] for x in profile["body"]["data"]["container"]["sections"]], [0, 3])
        self.assertEqual(profile["body"]["data"]["ability"], [])

        search = self.run_script(
            "https://g-acs.m.goofish.com/gw/mtop.taobao.idlemtopsearch.search/1.0/",
            {"data": {"resultList": [
                {"data": {"template": {"name": "idlefish_search_card_category_select"}}},
                {"data": {"template": {"name": "organic"}, "id": "keep"}}
            ]}},
        )
        self.assertEqual([x["data"]["id"] for x in search["body"]["data"]["resultList"]], ["keep"])

    def test_unsupported_route_exits_without_parse_or_stringify(self):
        result = self.run_script(
            "https://acs.m.goofish.com/gw/mtop.taobao.idle.unhandled.endpoint/1.0/",
            {"data": {"large": [1, 2, 3]}},
        )
        self.assertEqual(result["done"], {})
        self.assertEqual(result["parseCalls"], 0)
        self.assertEqual(result["stringifyCalls"], 0)
        self.assertEqual(result["objectKeysCalls"], 0)


if __name__ == "__main__":
    unittest.main()
