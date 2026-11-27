#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from optimize_cross_app_triggers import (
    AMAP_CANONICAL_RULE, AMAP_NATIVE_JQ_PATHS, AMAP_YOUTUBE_MARKER,
    MEITUAN_MARKER, PDD_MARKER, PDD_RULE, optimize, validate_amap_ownership,
)

SCRIPT = "https://raw.githubusercontent.com/ifflagged/Romeo/1a724bb3c7ae08b3852a9ab94210d7f7fcb2e3a7/Modules/JavaScript/ZenmoFeiShi/MT/ZenmoFeiShi_MT.js"
ISHOWSHU = "https://raw.githubusercontent.com/ifflagged/Romeo/1a724bb3c7ae08b3852a9ab94210d7f7fcb2e3a7/Modules/JavaScript/ishowshu/amap/ishowshu_amap.js"
RUCU6 = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/amap/rucu6_amap.js"
AMAP_LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js"
YOUTUBE_RSTORE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/youtube.js"
YOUTUBE_ENHANCED = "https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/YouTube/response.min.js"

def fixture():
    legacy = []
    for i in range(8):
        legacy.append('response if ${url} ~= /^https:\\/\\/api%d\\.meituan\\.com\\/path/i then script("%s") with tag="MT", timeout=60, requires_body=true' % (i, SCRIPT))
    amap_local = [
        r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\? script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/bus\/plan\/integrate\? script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/shield\/search_poi\/homepage script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/shield\/dsp\/profile\/index\/nodefaasv\d\? script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d\.amap\.com\/ws\/shield\/search\/nearbyrec_smart\? script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d-zb\.amap\.com\/ws\/promotion-web\/resource script-path=' + AMAP_LOCAL,
        r'http-response ^https?:\/\/m\d-zb\.amap\.com\/ws\/sharedtrip\/taxi\/order_detail_car_tips\? script-path=' + AMAP_LOCAL,
    ]
    ishowshu_paths = ["search_bff/hotword", "search_poi/homepage", "nodefaasv3",
                      "car/order/content_info", "order_web/friendly_information"]
    ishowshu = [
        'response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/%s/i then script("%s") with tag="amap", requires_body=true' % (p, ISHOWSHU)
        for p in ishowshu_paths
    ]
    rucu6_paths = [
        "c3frontend/(?:af-hotel|af-launch|af-nearby)",
        "perception/drive/(?:routeInfo|routePlan)",
        "shield/search_poi/(?:mps|search/sp|sug|tips_operation_location)",
        "faas/amap-navigation/(?:card-service-plan-home|main-page)",
        "shield/frogserver/aocs/updatable/1",
        "shield/search/nearbyrec_smart",
        "valueadded/alimama/splash_screen",
        "boss/(?:car/order/content_info|order_web/friendly_information)",
        "promotion-web/resource",
        "shield/search/(?:common/coupon/info|poi/detail)",
    ]
    rucu6 = [
        'response if ${url} ~= /^https:\\/\\/m5(?:-zb)?\\.amap\\.com\\/ws\\/%s/i then script("%s") with tag="rucu6", requires_body=true' % (p, RUCU6)
        for p in rucu6_paths
    ]
    rewrite = [
        r'request if ${url} ~= /^https:\/\/t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_/i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/mrk\//i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/marketing_api\//i then reject(404)',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\?/i then response.json.jq("clean")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/bus\/plan\/integrate\?/i then response.json.jq("clean")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search_poi\/homepage\?/i then response.json.delete("history_tags")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/dsp\/profile\/index\/nodefaasv3\?/i then response.json.jq("profile cleanup")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search_bff\/hotword\?/i then response.json.jq("hotword cleanup")',
        r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search_business\/process\/marketingOperationStructured\?/i then response.json.delete("data.tipsOperationLocation")',
        r'response if ${url} ~= /^https:\/\/m5-zb\.amap\.com\/ws\/sharedtrip\/taxi\/order_detail_car_tips\?/i then response.json.delete("data.carTips.data.popupInfo")',
    ]
    scripts = legacy + [
        'http-response ^https?:\\/\\/api.meituan.com/ script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/meituan/meituan.js,tag=MEITUAN-CONSOLIDATED,requires-body=true'
    ] + amap_local + ishowshu + rucu6 + [
        r'http-response ^https?:\/\/youtubei\.googleapis\.com\/(youtubei\/v\d\/(browse|next|player|search|reel\/reel_watch_sequence|get_watch))(\?(.*))?$ script-path=' + YOUTUBE_RSTORE + ',tag=YOUTUBE,requires-body=true,binary-body-mode=true',
        r'http-response ^https:\/\/youtubei\.googleapis\.com\/youtubei\/v1\/(browse|next|search)(\?[^#]*)?$ script-path=' + YOUTUBE_ENHANCED,
        r'http-response ^https:\/\/youtubei\.googleapis\.com\/youtubei\/v1\/(player|get_watch)(\?[^#]*)?$ script-path=' + YOUTUBE_ENHANCED,
    ]
    return "[Rewrite]\n" + "\n".join(rewrite) + "\n[Script]\n" + "\n".join(scripts) + "\n"


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



    def test_amap_three_sources_consolidate_to_one_canonical_handler(self):
        result, _, _ = optimize(fixture())
        self.assertEqual(result.count(AMAP_YOUTUBE_MARKER), 1)
        self.assertEqual(result.count(AMAP_CANONICAL_RULE), 1)
        self.assertNotIn("ishowshu_amap.js", result)
        self.assertNotIn("rucu6_amap.js", result)
        self.assertEqual(result.count("scripts/amap/amap.js"), 1)
        for path in AMAP_NATIVE_JQ_PATHS:
            self.assertNotIn(path, result)
        self.assertIn("beforeNavi", result)
        self.assertIn("bus\\\\/plan\\\\/integrate", result)
        self.assertEqual(optimize(result)[0], result)

    def test_amap_source_inventory_drift_fails_closed(self):
        source = fixture().replace("rucu6_amap.js", "changed_amap.js", 1)
        with self.assertRaisesRegex(ValueError, "three-source script inventory changed"):
            optimize(source)

    def test_amap_native_rule_inventory_required(self):
        source = fixture().replace('response.json.delete("history_tags")\\n', "", 1)
        with self.assertRaisesRegex(ValueError, "native JSON owner inventory changed"):
            optimize(source)

    def test_youtube_enhanced_owners_required(self):
        source = fixture().replace("Scripts/YouTube/response.min.js", "Scripts/YouTube/other.js", 1)
        with self.assertRaisesRegex(ValueError, "YouTube v1 enhanced"):
            optimize(source)

    def test_amap_canonical_handler_must_be_single_processor(self):
        result, _, _ = optimize(fixture())
        bad = result.replace(AMAP_CANONICAL_RULE, AMAP_CANONICAL_RULE + ' script("https://example.com/second.js")')
        with self.assertRaisesRegex(ValueError, "single canonical processor"):
            validate_amap_ownership(bad)


    def test_youtube_enhanced_owners_required(self):
        source = fixture().replace("Scripts/YouTube/response.min.js", "Scripts/YouTube/other.js", 1)
        with self.assertRaisesRegex(ValueError, "YouTube v1 enhanced"):
            optimize(source)

    def test_amap_and_youtube_ambiguous_processor_is_rejected(self):
        source = fixture().replace("script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js",
                                   'script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js script("https://example.com/b.js")')
        with self.assertRaisesRegex(ValueError, "Amap processor ownership"):
            optimize(source)

if __name__ == "__main__":
    unittest.main()
