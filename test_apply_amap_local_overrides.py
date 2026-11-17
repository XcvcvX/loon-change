#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from apply_amap_local_overrides import (
    CANONICAL_GROUPED_RULE,
    DUPLICATE_HOTWORD_RULE,
    MARKETING_OPERATION_OLD_RULE,
    MARKETING_OPERATION_NEW_RULE,
    NATIVE_RESPONSE_SCRIPT_RULES,
    apply,
)


BASE = """#!name = 高德地图

[Rewrite]
__DUPLICATE__
__GROUPED__
__MARKETING__
request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/tips_adv\?/i then reject_dict(200)

[Script]
response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search_bff\/hotword\?/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js") with tag="[高德地图]移除搜索栏推广", requires_body=true
response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\?/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js") with tag="[高德地图]移除路线规划推广", requires_body=true
response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/bus\/plan\/integrate\?/i then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js") with tag="[高德地图]移除路线规划、导航结束页推广", requires_body=true

[MitM]
hostname = *.amap.com
""".replace("__DUPLICATE__", DUPLICATE_HOTWORD_RULE).replace(
    "__GROUPED__", CANONICAL_GROUPED_RULE
).replace("__MARKETING__", MARKETING_OPERATION_OLD_RULE)


class AmapLocalOverrideTests(unittest.TestCase):
    def test_vendored_plugin_has_deduplicated_hotword_and_correct_marketing_field_path(self):
        plugin = Path(__file__).parent / "sources" / "amap" / "Amap.lpx"
        original = plugin.read_text(encoding="utf-8-sig")
        result, removed = apply(original)
        self.assertEqual(removed, 0)
        self.assertIn(MARKETING_OPERATION_NEW_RULE, result)
        self.assertNotIn(MARKETING_OPERATION_OLD_RULE, result)
        for _marker, old_rule, native_rule in NATIVE_RESPONSE_SCRIPT_RULES:
            self.assertNotIn(old_rule, result)
            self.assertIn(native_rule, result)
        self.assertEqual(original.count(CANONICAL_GROUPED_RULE), 1)
        self.assertNotIn(DUPLICATE_HOTWORD_RULE, original)



    def test_converts_before_navi_and_bus_plan_scripts_to_native_json(self):
        result, _ = apply(BASE)
        for marker, old_rule, native_rule in NATIVE_RESPONSE_SCRIPT_RULES:
            self.assertIn(native_rule, result)
            self.assertNotIn(old_rule, result)
        bus_rule = next(rule for marker, _old, rule in NATIVE_RESPONSE_SCRIPT_RULES if marker == "bus/plan/integrate")
        self.assertIn("hkfRecommendPlans", bus_rule)
        self.assertEqual(apply(result)[0], result)

    def test_fails_closed_when_route_response_script_drifts(self):
        _marker, old_rule, _native_rule = NATIVE_RESPONSE_SCRIPT_RULES[0]
        fixture = BASE.replace(old_rule, old_rule.replace("requires_body=true", "requires_body=false"))
        with self.assertRaisesRegex(ValueError, "route response script changed"):
            apply(fixture)

    def test_fails_closed_when_native_route_rule_inventory_is_missing(self):
        _marker, old_rule, _native_rule = NATIVE_RESPONSE_SCRIPT_RULES[0]
        fixture = BASE.replace(old_rule + "\n", "")
        with self.assertRaisesRegex(ValueError, "route response rule inventory changed"):
            apply(fixture)

    def test_fails_closed_on_duplicate_route_response_scripts(self):
        _marker, old_rule, _native_rule = NATIVE_RESPONSE_SCRIPT_RULES[0]
        fixture = BASE.replace(old_rule + "\n", old_rule + "\n" + old_rule + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate Amap route response rules"):
            apply(fixture)

    def test_corrects_marketing_operation_resource_placement_json_path(self):
        result, removed = apply(BASE)
        self.assertIn(MARKETING_OPERATION_NEW_RULE, result)
        self.assertNotIn(MARKETING_OPERATION_OLD_RULE, result)
        self.assertEqual(removed, 1)

    def test_fails_closed_when_marketing_operation_rule_drifts(self):
        fixture = BASE.replace(
            MARKETING_OPERATION_OLD_RULE,
            MARKETING_OPERATION_OLD_RULE.replace("obj.data.resourcePlacement", "data.unreviewedField"),
        )
        with self.assertRaisesRegex(ValueError, "marketingOperationStructured rule changed"):
            apply(fixture)

    def test_fails_closed_when_marketing_operation_rule_is_missing(self):
        fixture = BASE.replace(MARKETING_OPERATION_OLD_RULE + "\n", "")
        with self.assertRaisesRegex(ValueError, "marketingOperationStructured rule inventory"):
            apply(fixture)

    def test_fails_closed_on_duplicate_marketing_operation_rule(self):
        fixture = BASE.replace(
            MARKETING_OPERATION_OLD_RULE + "\n",
            MARKETING_OPERATION_OLD_RULE + "\n" + MARKETING_OPERATION_OLD_RULE + "\n",
        )
        with self.assertRaisesRegex(ValueError, "duplicate Amap marketingOperationStructured"):
            apply(fixture)

    def test_removes_only_duplicate_hotword_rule(self):
        result, removed = apply(BASE)
        self.assertEqual(removed, 1)
        self.assertNotIn(DUPLICATE_HOTWORD_RULE, result)
        self.assertIn(CANONICAL_GROUPED_RULE, result)
        self.assertIn(MARKETING_OPERATION_NEW_RULE, result)
        self.assertNotIn(MARKETING_OPERATION_OLD_RULE, result)
        self.assertIn("search_poi", result)
        self.assertEqual(apply(result)[0], result)

    def test_is_idempotent_when_upstream_duplicate_is_already_absent(self):
        fixture = BASE.replace(DUPLICATE_HOTWORD_RULE + "\n", "")
        result, removed = apply(fixture)
        self.assertEqual(removed, 0)
        self.assertIn(MARKETING_OPERATION_NEW_RULE, result)
        self.assertEqual(apply(result)[0], result)

    def test_fails_closed_when_grouped_rule_is_missing(self):
        fixture = BASE.replace(CANONICAL_GROUPED_RULE + "\n", "")
        with self.assertRaisesRegex(ValueError, "grouped hotword rule inventory"):
            apply(fixture)

    def test_fails_closed_when_target_rule_drifts(self):
        fixture = BASE.replace(
            DUPLICATE_HOTWORD_RULE,
            DUPLICATE_HOTWORD_RULE.replace("reject_dict(200)", "reject(404)"),
        )
        with self.assertRaisesRegex(ValueError, "hotword rule changed"):
            apply(fixture)

    def test_fails_closed_on_duplicate_standalone_rule(self):
        fixture = BASE.replace(
            DUPLICATE_HOTWORD_RULE + "\n",
            DUPLICATE_HOTWORD_RULE + "\n" + DUPLICATE_HOTWORD_RULE + "\n",
        )
        with self.assertRaisesRegex(ValueError, "duplicate standalone"):
            apply(fixture)


if __name__ == "__main__":
    unittest.main()
