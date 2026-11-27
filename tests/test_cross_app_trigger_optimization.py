#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from optimize_cross_app_triggers import (
    AMAP_YOUTUBE_MARKER, MEITUAN_MARKER, PDD_MARKER, PDD_RULE, optimize,
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
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\?/i then response.json.jq("clean")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/bus\/plan\/integrate\?/i then response.json.jq("clean")',
    ]) + "\n[Script]\n" + "\n".join(legacy) + "\n" + 'http-response ^https?:\\/\\/api.meituan.com/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/meituan/meituan.js,tag=MEITUAN-CONSOLIDATED,requires-body=true\n' + r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\? script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js' + "\n" + r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/bus\/plan\/integrate\? script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js' + "\n" + r'http-response ^https?:\/\/youtubei\.googleapis\.com\/(youtubei\/v\d\/(browse|next|player|search|reel\/reel_watch_sequence|get_watch))(\?(.*))?$ script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/youtube.js,tag=YOUTUBE,requires-body=true,binary-body-mode=true' + "\n" + r'http-response ^https:\/\/youtubei\.googleapis\.com\/youtubei\/v1\/(browse|next|search)(\?[^#]*)?$ script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/YouTube/response.min.js' + "\n" + r'http-response ^https:\/\/youtubei\.googleapis\.com\/youtubei\/v1\/(player|get_watch)(\?[^#]*)?$ script-path=https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/YouTube/response.min.js' + "\n"

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


    def test_amap_and_youtube_cross_processor_overlap_is_partitioned(self):
        result, _, _ = optimize(fixture())
        self.assertEqual(result.count(AMAP_YOUTUBE_MARKER), 1)
        self.assertIn(r"m[0-46-9]\.amap\.com", result)
        self.assertNotIn(r"m\d\.amap\.com", result)
        self.assertIn(r"youtubei\/v[2-9]\/", result)
        self.assertIn(r"youtubei\/v1\/(browse|next|search)", result)
        self.assertIn(r"youtubei\/v1\/(player|get_watch)", result)
        self.assertEqual(optimize(result)[0], result)

    def test_amap_native_json_owner_required(self):
        source = fixture().replace('response.json.jq("clean")', 'response.json.delete("clean")', 1)
        with self.assertRaisesRegex(ValueError, "Amap native JSON owner"):
            optimize(source)

    def test_youtube_enhanced_owners_required(self):
        source = fixture().replace("Scripts/YouTube/response.min.js", "Scripts/YouTube/other.js", 1)
        with self.assertRaisesRegex(ValueError, "YouTube v1 enhanced"):
            optimize(source)

    def test_amap_and_youtube_ambiguous_processor_is_rejected(self):
        source = fixture().replace("script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js",
                                   'script-path=https://example.com/a.js script("https://example.com/b.js")')
        with self.assertRaisesRegex(ValueError, "Amap processor ownership"):
            optimize(source)

if __name__ == "__main__":
    unittest.main()
