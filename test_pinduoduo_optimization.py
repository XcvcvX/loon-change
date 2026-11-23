#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for single-pass Pinduoduo order response cleanup."""
import re
import unittest
from pathlib import Path

from optimize_pinduoduo import MARKER, ORDER_RULE, SHIPPING_RULE, optimize_plugin

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "allAdRewrite.plugin"


class PinduoduoOrderOptimizationTests(unittest.TestCase):
    def fixture(self):
        return "[Rewrite]\n" + SHIPPING_RULE + "\n" + ORDER_RULE + "\n[MITM]\nhostname = api.pinduoduo.com\n"

    def test_shipping_specific_jq_is_removed_and_generic_delete_is_retained(self):
        result = optimize_plugin(self.fixture())
        self.assertEqual(result.count(MARKER), 1)
        self.assertNotIn(SHIPPING_RULE, result)
        self.assertEqual(result.count(ORDER_RULE), 1)
        self.assertIn('["marketing_banner_vo", "shipping.banner_above_recommend"]', result)

    def test_shipping_response_matches_exactly_one_response_json_handler(self):
        result = optimize_plugin(self.fixture())
        shipping_url = "https://api.pinduoduo.com/order/12345-67890/shipping?source=app"
        handlers = []
        for line in result.splitlines():
            if not line.startswith("response if "):
                continue
            pattern = line.split("~= /", 1)[1].split("/i then", 1)[0]
            if re.search(pattern, shipping_url, re.I):
                handlers.append(line)
        self.assertEqual(handlers, [ORDER_RULE])

    def test_optimizer_is_idempotent(self):
        result = optimize_plugin(self.fixture())
        self.assertEqual(optimize_plugin(result), result)

    def test_checked_in_plugin_snapshot_has_single_pass_rule(self):
        result = optimize_plugin(PLUGIN.read_text(encoding="utf-8"))
        self.assertEqual(result.count(MARKER), 1)
        self.assertNotIn(SHIPPING_RULE, result)
        self.assertEqual(result.count(ORDER_RULE), 1)

    def test_unknown_or_partial_rule_inventory_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "rule inventory changed"):
            optimize_plugin("[Rewrite]\n" + ORDER_RULE + "\n")
        damaged = self.fixture().replace(SHIPPING_RULE, SHIPPING_RULE + "\n" + SHIPPING_RULE)
        with self.assertRaisesRegex(ValueError, "rule inventory changed"):
            optimize_plugin(damaged)


if __name__ == "__main__":
    unittest.main()
