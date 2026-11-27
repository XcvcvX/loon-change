#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from optimize_cross_app_triggers import (
    MEITUAN_MARKER, PDD_MARKER, PDD_RULE, optimize,
    consolidate_meituan, consolidate_pinduoduo_mrk,
)

SCRIPT = "https://raw.githubusercontent.com/ifflagged/Romeo/1a724bb3c7ae08b3852a9ab94210d7f7fcb2e3a7/Modules/JavaScript/ZenmoFeiShi/MT/ZenmoFeiShi_MT.js"
def fixture():
    legacy = []
    for i in range(8):
        legacy.append('response if ${url} ~= /^https:\\/\\/api%d\\.meituan\\.com\\/path/i then script("%s") with tag="MT", timeout=60, requires_body=true' % (i, SCRIPT))
    return "[Rewrite]\n" + "\n".join([
        r'request if ${url} ~= /^https:\/\/t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_/i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/mrk\//i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/marketing_api\//i then reject(404)',
    ]) + "\n[Script]\n" + "\n".join(legacy) + "\n" + 'http-response ^https?:\\/\\/api.meituan.com/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/meituan/meituan.js,tag=MEITUAN-CONSOLIDATED,requires-body=true\n' + r'http-response ^https:\/\/m5\.amap\.com\/x script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js' + "\n" + r'http-response ^https:\/\/youtubei\.googleapis\.com\/x script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/youtube.js' + "\n"

class CrossAppTriggerTests(unittest.TestCase):
    def test_meituan_eight_triggers_removed_only_with_canonical_handler(self):
        source = fixture()
        result, _, _ = optimize(source)
        self.assertEqual(result.count(MEITUAN_MARKER), 1)
        self.assertEqual(result.count(SCRIPT), 0)
        self.assertEqual(result.count("MEITUAN-CONSOLIDATED"), 1)

    def test_pinduoduo_mrk_rules_merge_to_one_matcher(self):
        result, _, _ = optimize(fixture())
        self.assertEqual(result.count(PDD_MARKER), 1)
        self.assertEqual(result.count(PDD_RULE), 1)
        self.assertNotIn("dspcb", result.split("[Script]", 1)[0].replace(PDD_RULE, ""))

    def test_idempotence(self):
        result, _, _ = optimize(fixture())
        self.assertEqual(optimize(result)[0], result)

    def test_meituan_drift_fails_closed(self):
        source = fixture().replace('tag="MT"', 'tag="OTHER"', 1)
        with self.assertRaisesRegex(ValueError, "exactly 8"):
            optimize(source)

    def test_missing_canonical_meituan_handler_fails_closed(self):
        source = fixture().replace("MEITUAN-CONSOLIDATED", "OTHER")
        with self.assertRaisesRegex(ValueError, "canonical consolidated"):
            optimize(source)

    def test_amap_and_youtube_ambiguous_processor_is_rejected(self):
        source = fixture().replace("script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js",
                                   'script-path=https://example.com/a.js script("https://example.com/b.js")')
        with self.assertRaisesRegex(ValueError, "Amap processor ownership"):
            optimize(source)

if __name__ == "__main__":
    unittest.main()
