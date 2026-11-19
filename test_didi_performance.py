import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_didi import (
    EXPECTED_FILTERS,
    LOCAL,
    MARKER,
    REMOTE,
    optimize_source,
    rewrite_plugin,
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "didi" / "didi.js"
NODE = shutil.which("node")


class DidiOptimizerTests(unittest.TestCase):
    def fixture_source(self):
        lines = [
            "const url = $request.url;",
            "if (!$response.body) $done({});",
            "let obj = JSON.parse($response.body);",
        ]
        for index in range(EXPECTED_FILTERS):
            path = "obj.data.items%d" % index
            lines.append("%s = %s.filter(item => item.keep);" % (path, path))
        lines.append("$done({body: JSON.stringify(obj)});")
        return "\n".join(lines) + "\n"

    def test_optimizer_converts_all_seven_filters_and_is_idempotent(self):
        original = self.fixture_source()
        result = optimize_source(original, "0123456789abcdef0123456789abcdef01234567")
        self.assertIn(MARKER, result)
        self.assertEqual(result.count("compactInPlace("), EXPECTED_FILTERS + 1)
        self.assertIsNone(re.search(r"\.filter\s*\(", result))
        self.assertIn("if (!$response.body) {", result)
        self.assertTrue(result.rstrip().endswith("}"))
        self.assertEqual(optimize_source(result), result)

    def test_optimizer_fails_closed_when_upstream_filter_inventory_drifts(self):
        source = self.fixture_source().replace(
            "obj.data.items6 = obj.data.items6.filter(item => item.keep);",
            "obj.data.items6 = obj.data.items6;",
        )
        with self.assertRaisesRegex(ValueError, "expected 7, got 6"):
            optimize_source(source)

    def test_plugin_migration_accepts_the_reviewed_two_or_four_trigger_inventory(self):
        for count in (2, 4):
            fixture = "[Script]\n" + "\n".join(
                "http-response ^https://didi%d.example/api script-path=%s,tag=DIDI-%d,requires-body=true"
                % (index, REMOTE, index)
                for index in range(count)
            ) + "\n[MITM]\nhostname = didi.example\n"
            migrated = rewrite_plugin(fixture)
            self.assertEqual(migrated.count(LOCAL), count)
            self.assertNotIn(REMOTE, migrated)
            self.assertEqual(rewrite_plugin(migrated), migrated)

    def test_plugin_migration_rejects_unreviewed_trigger_counts(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://didi%d.example/api script-path=%s,tag=DIDI-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(3)
        )
        with self.assertRaisesRegex(ValueError, "expected 2 retained or 4 full triggers"):
            rewrite_plugin(fixture)


@unittest.skipUnless(NODE, "Node.js is required for Didi response runtime tests")
class DidiRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult;
const context = {
  $request: { url: payload.url },
  $response: { body: payload.body === null ? "" : JSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  __parseCount: 0,
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(
  "const nativeParse = JSON.parse.bind(JSON); JSON.parse = function(value) { __parseCount++; return nativeParse(value); }; Array.prototype.filter = function() { throw new Error('allocating Array.filter remains'); };",
  context
);
vm.runInContext(source, context, { timeout: 5000 });
if (payload.body === null) {
  if (!doneResult || Object.keys(doneResult).length !== 0) throw new Error("empty body did not complete cleanly");
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, empty: true }));
} else {
  if (!doneResult || typeof doneResult.body !== "string") throw new Error("missing rewritten response");
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, output: JSON.parse(doneResult.body) }));
}
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_generated_snapshot_has_no_allocating_filter_and_seven_compaction_calls(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(source.count("compactInPlace(") - 1, EXPECTED_FILTERS)
        self.assertIsNone(re.search(r"\.filter\s*\(", source))

    def test_presale_scene_lists_compact_in_place_and_preserve_order(self):
        body = {
            "data": {
                "scene_list": [
                    {"text": "优惠商城"}, {"text": "打车"}, {"text": "公交"}
                ],
                "show_data": [
                    {"scene_ids": ["scene_coupon_mall", "ride", "bus"]},
                    {"scene_ids": ["taxi", "scene_coupon_mall", "bike"]},
                ],
            }
        }
        result = self.run_script(
            "https://api.udache.com/gulfstream/pre-sale/v1/other/pGetSceneList",
            body,
        )
        self.assertEqual(result["parseCount"], 1)
        output = result["output"]["data"]
        self.assertEqual([item["text"] for item in output["scene_list"]], ["打车", "公交"])
        self.assertEqual(output["show_data"][0]["scene_ids"], ["ride", "bus"])
        self.assertEqual(output["show_data"][1]["scene_ids"], ["taxi", "bike"])

    def test_homepage_core_and_usercenter_keep_the_existing_allowlists(self):
        core = {
            "data": {
                "order_cards": {"nav_list_card": {"data": [
                    {"nav_id": "dache_anycar"}, {"nav_id": "promo"},
                    {"nav_id": "driverservice"}, {"nav_id": "bike"},
                ]}},
                "disorder_cards": {"bottom_nav_list": {"data": [
                    {"id": "v6x_home"}, {"id": "promo"}, {"id": "user_center"},
                ]}},
            }
        }
        result = self.run_script("https://conf.diditaxi.com.cn/homepage/v1/core", core)
        self.assertEqual(
            [item["nav_id"] for item in result["output"]["data"]["order_cards"]["nav_list_card"]["data"]],
            ["dache_anycar", "driverservice", "bike"],
        )
        self.assertEqual(
            [item["id"] for item in result["output"]["data"]["disorder_cards"]["bottom_nav_list"]["data"]],
            ["v6x_home", "user_center"],
        )

        profile = {"data": {"cards": [
            {"title": "金融服务"},
            {"title": "普通卡片", "tag": "normal"},
            {"title": "钱包", "tag": "wallet", "items": [
                {"title": "优惠券"}, {"title": "余额"}
            ], "card_type": 4, "bottom_items": [
                {"title": "省钱套餐"}, {"title": "其他"}, {"title": "天天神券"}
            ]},
        ]}}
        result = self.run_script("https://common.diditaxi.com.cn/common/v1/usercenter/me", profile)
        cards = result["output"]["data"]["cards"]
        self.assertEqual([item["title"] for item in cards], ["普通卡片", "钱包"])
        self.assertEqual([item["title"] for item in cards[1]["items"]], ["优惠券"])
        self.assertEqual(
            [item["title"] for item in cards[1]["bottom_items"]],
            ["省钱套餐", "天天神券"],
        )

    def test_ota_top_banner_removal_is_unchanged(self):
        body = {"data": {"disorder_cards": {"top_banner_card": {"data": [
            {"T": "yuentu_top_banner"}, {"T": "keep"}
        ]}}}}
        result = self.run_script(
            "https://conf.diditaxi.com.cn/ota/na/yuantu/infoList",
            body,
        )
        self.assertEqual(result["output"]["data"]["disorder_cards"]["top_banner_card"]["data"],
                         [{"T": "keep"}])

    def test_empty_body_skips_json_parse(self):
        result = self.run_script(
            "https://api.udache.com/gulfstream/pre-sale/v1/other/pGetSceneList",
            None,
        )
        self.assertTrue(result["empty"])
        self.assertEqual(result["parseCount"], 0)


if __name__ == "__main__":
    unittest.main()
