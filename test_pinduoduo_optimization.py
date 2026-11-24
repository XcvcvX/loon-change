#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for Pinduoduo order and request matcher optimization."""
import re
import unittest
from pathlib import Path

from optimize_pinduoduo import MARKER, ORDER_RULE, QUERY_MATCHER_MARKER, SHIPPING_RULE, optimize_plugin

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "allAdRewrite.plugin"
PDD_PATHS = (
    "/search_hotquery",
    "/api/zaire_biz/chat/resource/get_list_data",
    "/api/caterham/v3/query/new_chat_group",
    "/api/alexa/goods/back_up",
    "/api/caterham/v3/query/personal",
    "/api/caterham/v3/query/my_order_group",
    "/api/caterham/v3/query/likes",
)


def request_rules(path):
    escaped = path.replace("/", r"\\/")
    broad = r"request if ${url} ~= /^https:\/\/api\.pinduoduo\.com" + escaped + r"/i then reject_dict(200)"
    narrow = broad.replace("/i then", r"\?/i then")
    return broad, narrow


class PinduoduoOrderOptimizationTests(unittest.TestCase):
    def fixture(self):
        rules = []
        for path in PDD_PATHS:
            broad, narrow = request_rules(path)
            rules.extend((broad, narrow))
        return ("[Rewrite]\n" + SHIPPING_RULE + "\n" + ORDER_RULE + "\n"
                + "\n".join(rules) + "\n[MITM]\nhostname = api.pinduoduo.com\n")

    def test_order_response_cleanup(self):
        result = optimize_plugin(self.fixture())
        self.assertEqual(result.count(MARKER), 1)
        self.assertNotIn(SHIPPING_RULE, result)
        self.assertEqual(result.count(ORDER_RULE), 1)

    def test_shipping_response_matches_one_json_handler(self):
        result = optimize_plugin(self.fixture())
        url = "https://api.pinduoduo.com/order/12345-67890/shipping?source=app"
        handlers = []
        for line in result.splitlines():
            if line.startswith("response if "):
                pattern = line.split("~= /", 1)[1].split("/i then", 1)[0]
                if re.search(pattern, url, re.I):
                    handlers.append(line)
        self.assertEqual(handlers, [ORDER_RULE])

    def test_query_rules_preserve_query_url_coverage(self):
        result = optimize_plugin(self.fixture())
        self.assertEqual(result.count(QUERY_MATCHER_MARKER), 1)
        for path in PDD_PATHS:
            broad, narrow = request_rules(path)
            self.assertEqual(result.count(broad), 1)
            self.assertNotIn(narrow, result)
            pattern = broad.split("~= /", 1)[1].split("/i then", 1)[0]
            self.assertTrue(re.search(pattern, "https://api.pinduoduo.com" + path + "?x=1", re.I))

    def test_unrelated_app_rules_are_untouched(self):
        unrelated = r"request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/info_bff\/rankingCard\?/i then reject_dict(200)"
        result = optimize_plugin(self.fixture() + unrelated + "\n")
        self.assertIn(unrelated, result)

    def test_idempotence(self):
        result = optimize_plugin(self.fixture())
        self.assertEqual(optimize_plugin(result), result)

    def test_checked_in_plugin_snapshot(self):
        result = optimize_plugin(PLUGIN.read_text(encoding="utf-8"))
        self.assertEqual(result.count(MARKER), 1)
        self.assertEqual(result.count(QUERY_MATCHER_MARKER), 1)
        self.assertNotIn(SHIPPING_RULE, result)
        self.assertEqual(result.count(ORDER_RULE), 1)
        for path in PDD_PATHS:
            broad, narrow = request_rules(path)
            self.assertEqual(result.count(broad), 1)
            self.assertNotIn(narrow, result)

    def test_unknown_inventory_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "rule inventory changed"):
            optimize_plugin("[Rewrite]\n" + ORDER_RULE + "\n")
        damaged = self.fixture().replace(SHIPPING_RULE, SHIPPING_RULE + "\n" + SHIPPING_RULE)
        with self.assertRaisesRegex(ValueError, "rule inventory changed"):
            optimize_plugin(damaged)
        missing = self.fixture().replace(request_rules(PDD_PATHS[0])[1] + "\n", "")
        with self.assertRaisesRegex(ValueError, "query matcher inventory changed"):
            optimize_plugin(missing)


if __name__ == "__main__":
    unittest.main()
