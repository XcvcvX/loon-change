import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_didi import (
    EXPECTED_FILTERS,
    DIDI_MODE_MARKER,
    DIDI_WALLET_PROPERTY_CACHE_MARKER,
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
        lines.extend([
            'obj.data.scene_list = obj.data.scene_list.filter(item => item.text !== "优惠商城");',
            'block.scene_ids = block.scene_ids.filter(id => id !== "scene_coupon_mall");',
            "    const keepNavIds = ['dache_anycar', 'driverservice', 'bike'];",
            "obj.data.order_cards.nav_list_card.data = obj.data.order_cards.nav_list_card.data.filter(item => keepNavIds.includes(item.nav_id));",
            "    const keepBottomNavIds = ['v6x_home', 'user_center'];",
            "obj.data.disorder_cards.bottom_nav_list.data = obj.data.disorder_cards.bottom_nav_list.data.filter(item => keepBottomNavIds.includes(item.id));",
            "  const excludedTitles = ['天天领福利', '金融服务', '更多服务', '企业服务', '安全中心'];",
            "",
        ])
        lines.extend([
            "if (obj.data && obj.data.cards) {",
            "    obj.data.cards = obj.data.cards.filter(card => !excludedTitles.includes(card.title));",
            "",
            "    obj.data.cards.forEach(card => {",
            "      if (card.tag === \"wallet\") {",
            "        if (card.items) {",
            "          card.items = card.items.filter(item => item.title === \"优惠券\");",
            "        }",
            "        if (card.card_type === 4 && card.bottom_items) {",
            "          card.bottom_items = card.bottom_items.filter(item =>",
            "              item.title === \"省钱套餐\" || item.title === \"天天神券\"",
            "          );",
            "        }",
            "      }",
            "    });",
            "}",
        ])
        lines.append("$done({body: JSON.stringify(obj)});")
        return "\n".join(lines) + "\n"

    def test_optimizer_converts_all_seven_filters_and_is_idempotent(self):
        original = self.fixture_source()
        result = optimize_source(original, "0123456789abcdef0123456789abcdef01234567")
        self.assertIn(MARKER, result)
        self.assertEqual(result.count("compactDidiByField(") - 1, EXPECTED_FILTERS)
        self.assertIsNone(re.search(r"\.filter\s*\(", result))
        self.assertNotIn("new Set(", result)
        self.assertNotIn("keepNavIds", result)
        self.assertNotIn("keepBottomNavIds", result)
        self.assertNotIn("excludedTitles", result)
        self.assertIn("if (!$response.body) {", result)
        self.assertIn("$done(modified ? {body: JSON.stringify(obj)} : {});", result)
        self.assertIn("if (write !== length) {", result)
        self.assertIn("modified = true;", result)
        self.assertIn("Didi pre-parse supported-route guard v1", result)
        self.assertLess(result.index("const shouldProcess"), result.index("JSON.parse($response.body)"))
        self.assertTrue(result.rstrip().endswith("}"))
        self.assertEqual(optimize_source(result), result)
        self.assertIn(DIDI_MODE_MARKER, result)
        self.assertEqual(result.count("for (let read = 0; read < length; read++)"), 7)
        self.assertIn(DIDI_WALLET_PROPERTY_CACHE_MARKER, result)
        self.assertIn("const walletItems = item.items;", result)
        self.assertIn("const walletBottomItems = item.bottom_items;", result)
        self.assertNotIn("Array.isArray(item.items)", result)
        self.assertNotIn("Array.isArray(item.bottom_items)", result)

    def test_optimizer_fails_closed_when_upstream_filter_inventory_drifts(self):
        source = self.fixture_source().replace(
            'block.scene_ids = block.scene_ids.filter(id => id !== "scene_coupon_mall");',
            "block.scene_ids = block.scene_ids;",
        )
        with self.assertRaisesRegex(ValueError, "expected 7, got 6"):
            optimize_source(source)

    def test_wallet_property_cache_fails_closed_when_cached_reference_drifts(self):
        result = optimize_source(self.fixture_source(), "0123456789abcdef0123456789abcdef01234567")
        broken = result.replace("const walletItems = item.items;", "const walletItems = item.other_items;", 1)
        with self.assertRaisesRegex(ValueError, "wallet property-cache structure is incomplete"):
            optimize_source(broken)

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
    def run_script(self, url, body, disable_for_each=False, track_wallet_properties=False):
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
  __stringifyCount: 0,
  __walletPropertyReads: { tag: 0, items: 0, card_type: 0, bottom_items: 0 },
  __trackWalletPropertyReads: true,
  __captureWalletPropertyReads: payload.trackWalletProperties,
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(
  "const nativeParse = JSON.parse.bind(JSON); JSON.parse = function(value) { __parseCount++; const parsed = nativeParse(value); if (__captureWalletPropertyReads) { const wallet = parsed?.data?.cards?.[0]; if (wallet && wallet.tag === 'wallet') { for (const key of ['tag', 'items', 'card_type', 'bottom_items']) { let current = wallet[key]; Object.defineProperty(wallet, key, { enumerable: true, configurable: true, get() { if (__trackWalletPropertyReads) __walletPropertyReads[key]++; return current; }, set(value) { current = value; } }); } } } return parsed; }; const nativeStringify = JSON.stringify.bind(JSON); JSON.stringify = function(value) { __stringifyCount++; const tracking = __trackWalletPropertyReads; __trackWalletPropertyReads = false; try { return nativeStringify(value); } finally { __trackWalletPropertyReads = tracking; } }; Array.prototype.filter = function() { throw new Error('allocating Array.filter remains'); };",
  context
);
if (payload.disableForEach) {
  vm.runInContext("Array.prototype.forEach = function() { throw new Error('second user-center traversal remains'); };", context);
}
vm.runInContext(source, context, { timeout: 5000 });
if (payload.body === null) {
  if (!doneResult || Object.keys(doneResult).length !== 0) throw new Error("empty body did not complete cleanly");
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, stringifyCount: context.__stringifyCount, empty: true }));
} else if (!doneResult || typeof doneResult.body !== "string") {
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, stringifyCount: context.__stringifyCount, passThrough: true }));
} else {
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, stringifyCount: context.__stringifyCount, walletPropertyReads: context.__walletPropertyReads, output: JSON.parse(doneResult.body) }));
}
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body, "trackWalletProperties": track_wallet_properties}),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_usercenter_wallet_fields_are_compacted_during_the_card_pass(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("obj.data.cards.forEach", source)
        self.assertIn('compactDidiByField(obj.data.cards, "title", "card");', source)
        self.assertIn('compactDidiByField(walletItems, "title", "walletItem")', source)
        self.assertIn('compactDidiByField(walletBottomItems, "title", "walletBottom")', source)
        self.assertNotIn('compactDidiByField(item.items, "title", "walletItem")', source)
        self.assertNotIn('compactDidiByField(item.bottom_items, "title", "walletBottom")', source)
        self.assertNotIn("new Set(", source)
        self.assertNotIn("=>", source)
        self.assertNotIn("excludedTitles", source)

    def test_mode_dispatch_is_hoisted_outside_each_compaction_loop(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index(DIDI_MODE_MARKER)
        end = source.index("if (!$response.body)", start)
        helper = source[start:end].rstrip()
        modes = ("scene", "sceneId", "nav", "bottomNav", "walletItem", "walletBottom", "card")
        self.assertEqual(helper.count('mode === "'), len(modes))
        self.assertEqual(helper.count("for (let read = 0; read < length; read++)"), len(modes))
        for index, mode in enumerate(modes):
            selector = ('if (mode === "' if index == 0 else 'else if (mode === "') + mode + '") {'
            branch_start = helper.index(selector)
            next_candidates = [
                helper.find('  } else if (mode === "', branch_start + len(selector)),
                helper.find("  } else {", branch_start + len(selector)),
            ]
            next_candidates = [value for value in next_candidates if value >= 0]
            branch_end = min(next_candidates) if next_candidates else len(helper)
            branch = helper[branch_start:branch_end]
            loop_start = branch.index("for (let read = 0; read < length; read++)")
            self.assertNotIn("mode ===", branch[loop_start:])
        self.assertNotIn(".filter(", helper)
        self.assertNotIn(".forEach(", helper)

    def test_generated_snapshot_has_no_allocating_filter_and_seven_compaction_calls(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertIn(DIDI_MODE_MARKER, source)
        self.assertEqual(source.count("for (let read = 0; read < length; read++)"), 7)
        self.assertEqual(source.count("compactDidiByField(") - 1, EXPECTED_FILTERS)
        self.assertIsNone(re.search(r"\.filter\s*\(", source))
        self.assertNotIn("new Set(", source)
        self.assertNotIn("=>", source)

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
        result = self.run_script("https://common.diditaxi.com.cn/common/v1/usercenter/me", profile, disable_for_each=True)
        cards = result["output"]["data"]["cards"]
        self.assertEqual([item["title"] for item in cards], ["普通卡片", "钱包"])
        self.assertEqual([item["title"] for item in cards[1]["items"]], ["优惠券"])
        self.assertEqual(
            [item["title"] for item in cards[1]["bottom_items"]],
            ["省钱套餐", "天天神券"],
        )

    def test_wallet_nested_array_properties_are_read_once_per_wallet_card(self):
        body = {"data": {"cards": [
            {"title": "钱包", "tag": "wallet", "items": [
                {"title": "余额"}, {"title": "优惠券"}
            ], "card_type": 4, "bottom_items": [
                {"title": "其他"}, {"title": "天天神券"}
            ]},
            {"title": "普通卡片", "tag": "normal"}
        ]}}
        result = self.run_script(
            "https://common.diditaxi.com.cn/common/v1/usercenter/me",
            body,
            track_wallet_properties=True,
        )
        self.assertEqual(result["walletPropertyReads"], {
            "tag": 1, "items": 1, "card_type": 1, "bottom_items": 1,
        })
        wallet = result["output"]["data"]["cards"][0]
        self.assertEqual([item["title"] for item in wallet["items"]], ["优惠券"])
        self.assertEqual([item["title"] for item in wallet["bottom_items"]], ["天天神券"])

    def test_wallet_nested_non_array_fields_are_left_untouched(self):
        body = {"data": {"cards": [
            {"title": "钱包", "tag": "wallet", "items": "unexpected",
             "card_type": 4, "bottom_items": {"unexpected": True}},
            {"title": "金融服务", "tag": "remove"},
            {"title": "普通卡片", "tag": "normal"}
        ]}}
        result = self.run_script("https://common.diditaxi.com.cn/common/v1/usercenter/me", body)
        cards = result["output"]["data"]["cards"]
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["items"], "unexpected")
        self.assertEqual(cards[0]["bottom_items"], {"unexpected": True})
        self.assertEqual(result["stringifyCount"], 1)

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

    def test_unchanged_homepage_skips_json_serialization(self):
        body = {
            "data": {
                "order_cards": {"nav_list_card": {"data": [
                    {"nav_id": "dache_anycar"}, {"nav_id": "driverservice"}, {"nav_id": "bike"}
                ]}},
                "disorder_cards": {"bottom_nav_list": {"data": [
                    {"id": "v6x_home"}, {"id": "user_center"}
                ]}},
            }
        }
        result = self.run_script("https://conf.diditaxi.com.cn/homepage/v1/core", body)
        self.assertTrue(result["passThrough"])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_unrelated_response_skips_json_parse_before_body_decode(self):
        result = self.run_script("https://api.diditaxi.com.cn/unrelated/large-response", {"large": [1, 2, 3]})
        self.assertTrue(result["passThrough"])
        self.assertEqual(result["parseCount"], 0)
        self.assertEqual(result["stringifyCount"], 0)
    def test_empty_body_skips_json_parse(self):
        result = self.run_script(
            "https://api.udache.com/gulfstream/pre-sale/v1/other/pGetSceneList",
            None,
        )
        self.assertTrue(result["empty"])
        self.assertEqual(result["parseCount"], 0)


    def test_sync_workflow_tracks_the_generated_local_didi_runtime(self):
        workflow = (ROOT / ".github" / "workflows" / "sync.yml").read_text(encoding="utf-8")
        diff_line = next(
            line for line in workflow.splitlines()
            if "git diff --quiet -- allAdRewrite.plugin" in line
        )
        add_line = next(
            line for line in workflow.splitlines()
            if line.strip().startswith("git add -A -- allAdRewrite.plugin")
        )
        self.assertIn("scripts/", diff_line)
        self.assertIn("scripts/", add_line)


if __name__ == "__main__":
    unittest.main()
