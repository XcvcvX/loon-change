#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from optimize_cross_app_triggers import AMAP_CANONICAL_RULE, AMAP_REQUIRED_PATHS


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "amap" / "amap.js").read_text(encoding="utf-8")


class AmapCanonicalScriptTests(unittest.TestCase):
    def test_canonical_script_covers_rucu6_nearby_route(self):
        self.assertIn('url.includes("/c3frontend/af-nearby/nearby")', SCRIPT)
        self.assertIn('setIfDifferent(obj.data.modules, "banner", {})', SCRIPT)
        self.assertIn('setIfDifferent(obj.data.modules, "contentPoster", {})', SCRIPT)
        self.assertIn('bus_plan_bottom_tips', SCRIPT)

    def test_canonical_matcher_covers_every_source_route(self):
        for route in AMAP_REQUIRED_PATHS:
            self.assertIn(route, AMAP_CANONICAL_RULE)

    def test_canonical_script_preserves_ishowshu_hotword_cleanup(self):
        self.assertIn('url.includes("/shield/search_bff/hotword")', SCRIPT)
        self.assertIn('setIfDifferent(obj.data, "headerHotWord", [])', SCRIPT)
        self.assertIn('setIfDifferent(obj.data, "hotWordWithIcon", [])', SCRIPT)


    def test_script_guard_covers_all_canonical_routes(self):
        for route in (
            "/aos/perception/publicTravel/beforeNavi",
            "/bus/plan/integrate",
            "/c3frontend/af-hotel/page/main",
            "/c3frontend/af-launch/page/main",
            "/c3frontend/af-nearby/nearby",
            "/perception/drive/routeInfo",
            "/perception/drive/routePlan",
            "/shield/search/common/coupon/info",
            "/shield/search/poi/detail",
            "/shield/search_business/process/marketingOperationStructured",
            "/shield/search_poi/",
            "/faas/amap-navigation/card-service-plan-home",
            "/faas/amap-navigation/main-page",
            "/shield/frogserver/aocs/updatable/1",
            "/shield/dsp/profile/index/nodefaasv",
            "/shield/search/nearbyrec_smart",
            "/boss/car/order/content_info",
            "/boss/order_web/friendly_information",
            "/promotion-web/resource",
            "/sharedtrip/taxi/order_detail_car_tips",
            "/shield/search_bff/hotword",
            "/valueadded/alimama/splash_screen",
        ):
            self.assertIn(route, SCRIPT)

    def test_profile_cleanup_merges_native_json_allowlists(self):
        for key in ("MyOrderCard", "MineNewFootprintCard", "MineNewBEntranceCardV4"):
            self.assertIn(key, SCRIPT)
        self.assertIn('mode === "myOrderEntrance1"', SCRIPT)
        self.assertIn('mode === "myOrderEntrance2"', SCRIPT)
        self.assertIn('deleteIfPresent(obj.data, "wallet")', SCRIPT)
        for allowed_id in ("id === 7", "id === 8", "id === 10", "id === 17",
                            "id === 1", "id === 32", "id === 9", "id === 14"):
            self.assertIn(allowed_id, SCRIPT)


if __name__ == "__main__":
    unittest.main()
