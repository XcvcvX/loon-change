import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_amap import ARRAY_MARKER, LOCAL, REMOTE, TRACKING_MARKER, SCALAR_MARKER, DYNAMIC_MATCHER_MARKER, COMPACTION_MARKER, hoist_static_arrays, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "amap" / "amap.js"
NODE = shutil.which("node")


class AmapRStoreOptimizerTests(unittest.TestCase):
    def test_hoister_repairs_a_partially_optimized_snapshot(self):
        partial = (
            ARRAY_MARKER + "\n"
            + 'const AMAP_STATIC_ITEMS_01 = ["existing"];\n'
            + '  const items = ["banner", "popup"];\n'
        )
        repaired = hoist_static_arrays(partial)
        self.assertNotIn("const items = [", repaired)
        self.assertIn('const AMAP_STATIC_ITEMS_02 = ["banner", "popup"];', repaired)
        self.assertEqual(repaired.count(ARRAY_MARKER), 1)
        self.assertEqual(hoist_static_arrays(repaired), repaired)

    def test_static_filter_arrays_are_hoisted_and_optimizer_is_idempotent(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(ARRAY_MARKER, source)
        self.assertGreater(source.count("const AMAP_STATIC_ITEMS_"), 0)
        self.assertNotRegex(source, r"^\s*const items = \[")
        self.assertNotRegex(source, r"\[(?:\s*(?:\"[^\"\n]*\"|'[^'\n]*')\s*,?)+\s*\]\?\.includes")
        self.assertEqual(hoist_static_arrays(source), source)
        self.assertEqual(optimize_source(source), source)

    def test_route_info_uses_one_shared_dynamic_ad_matcher_and_optimizer_repairs_it(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(DYNAMIC_MATCHER_MARKER, source)
        self.assertEqual(source.count(r"const AMAP_AD_DYNAMIC_ID = /ads-\d+/;"), 1)
        self.assertEqual(source.count("AMAP_AD_DYNAMIC_ID.test(item?.dynamic_id_s)"), 1)
        self.assertEqual(source.count(', "dynamicAds")'), 4)
        self.assertNotIn(r"/ads-\d+/.test(item?.dynamic_id_s)", source)
        self.assertEqual(optimize_source(source), source)

        declaration = DYNAMIC_MATCHER_MARKER + "\nconst AMAP_AD_DYNAMIC_ID = /ads-\\d+/;\n\n"
        damaged = source.replace(declaration, "", 1).replace(
            "AMAP_AD_DYNAMIC_ID.test(item?.dynamic_id_s)",
            r"/ads-\d+/.test(item?.dynamic_id_s)",
        )
        repaired = optimize_source(damaged)
        self.assertIn(DYNAMIC_MATCHER_MARKER, repaired)
        self.assertEqual(repaired.count("AMAP_AD_DYNAMIC_ID.test(item?.dynamic_id_s)"), 1)
        self.assertEqual(repaired.count(', "dynamicAds")'), 4)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_route_info_caches_nested_response_references_and_optimizer_repairs_upstream_form(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = '} else if (url.includes("/perception/drive/routeInfo")) {'
        end = '} else if (url.includes("/perception/drive/routePlan")) {'
        i = source.index(start)
        j = source.index(end, i + len(start))
        block = source[i:j]
        self.assertIn("// loon-change: Amap routeInfo cached nested references v1", block)
        for declaration in (
            "const routeInfoFrontEnd = routeInfoData?.front_end;",
            "const routeInfoEvents = routeInfoData?.tbt?.event;",
            "const routeInfoGuideTips = routeInfoFrontEnd?.guide_tips;",
            "const routeInfoDownloads = routeInfoFrontEnd?.download;",
        ):
            self.assertIn(declaration, block)
        self.assertNotIn("obj?.data?.front_end", block)
        self.assertNotIn("obj?.data?.tbt?.event", block)
        self.assertEqual(optimize_source(source), source)

        damaged = source.replace(
            "  // loon-change: Amap routeInfo cached nested references v1\n"
            "  const routeInfoData = obj?.data;\n"
            "  const routeInfoFrontEnd = routeInfoData?.front_end;\n"
            "  const routeInfoEvents = routeInfoData?.tbt?.event;\n"
            "  const routeInfoGuideTips = routeInfoFrontEnd?.guide_tips;\n"
            "  const routeInfoDownloads = routeInfoFrontEnd?.download;",
            "",
            1,
        )
        self.assertNotEqual(damaged, source)
        repaired = optimize_source(damaged)
        self.assertIn("// loon-change: Amap routeInfo cached nested references v1", repaired)
        self.assertIn("const routeInfoEvents = routeInfoData?.tbt?.event;", repaired)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_route_info_cached_references_preserve_filtering_and_lazy_serialization(self):
        body = {"data": {
            "tbt": {"event": [{"dynamic_id_s": "ads-123"}, {"dynamic_id_s": "road-event"}]},
            "front_end": {
                "assistant": {"skin": "ad"},
                "guide_tips": [{"biz_type": "music"}, {"biz_type": "traffic"}],
                "download": [{"dynamic_id_s": "ads-456"}, {"dynamic_id_s": "normal-voice"}],
            },
        }}
        result = self.run_script(
            "https://m1.amap.com/ws/perception/drive/routeInfo?x=1",
            json.dumps(body),
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["tbt"]["event"], [{"dynamic_id_s": "road-event"}])
        self.assertNotIn("assistant", output["data"]["front_end"])
        self.assertEqual(output["data"]["front_end"]["guide_tips"], [{"biz_type": "traffic"}])
        self.assertEqual(output["data"]["front_end"]["download"], [{"dynamic_id_s": "normal-voice"}])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_route_plan_caches_nested_references_and_optimizer_repairs_upstream_form(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = '} else if (url.includes("/perception/drive/routePlan")) {'
        end = '} else if (url.includes("/promotion-web/resource")) {'
        i = source.index(start)
        j = source.index(end, i + len(start))
        block = source[i:j]
        self.assertIn("// loon-change: Amap routePlan cached nested references v1", block)
        for declaration in (
            "const routePlanFrontEnd = routePlanData?.front_end;",
            "const routePlanEvents = routePlanData?.tbt?.event;",
            "const routePlanDownloads = routePlanFrontEnd?.download;",
        ):
            self.assertIn(declaration, block)
        self.assertNotIn("obj?.data?.front_end", block)
        self.assertNotIn("obj?.data?.tbt?.event", block)
        self.assertEqual(optimize_source(source), source)

        damaged = source.replace(
            "  // loon-change: Amap routePlan cached nested references v1\n"
            "  const routePlanData = obj?.data;\n"
            "  const routePlanFrontEnd = routePlanData?.front_end;\n"
            "  const routePlanEvents = routePlanData?.tbt?.event;\n"
            "  const routePlanDownloads = routePlanFrontEnd?.download;",
            "",
            1,
        )
        self.assertNotEqual(damaged, source)
        repaired = optimize_source(damaged)
        self.assertIn("// loon-change: Amap routePlan cached nested references v1", repaired)
        self.assertIn("const routePlanEvents = routePlanData?.tbt?.event;", repaired)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_route_plan_cached_references_preserve_filtering_and_lazy_serialization(self):
        body = {"data": {
            "front_end": {
                "assistant": {"skin": "ad"},
                "global_guide_data": {"promo": True},
                "route_search": {"promo": True},
                "start_button_tips": {"promo": True},
                "download": [{"dynamic_id_s": "ads-789"}, {"dynamic_id_s": "normal-route-voice"}],
            },
            "tbt": {"event": [{"dynamic_id_s": "ads-321"}, {"dynamic_id_s": "normal-route-event"}]},
        }}
        result = self.run_script(
            "https://m1.amap.com/ws/perception/drive/routePlan?x=1",
            json.dumps(body),
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["tbt"]["event"], [{"dynamic_id_s": "normal-route-event"}])
        self.assertEqual(output["data"]["front_end"]["download"], [{"dynamic_id_s": "normal-route-voice"}])
        self.assertNotIn("assistant", output["data"]["front_end"])
        self.assertNotIn("global_guide_data", output["data"]["front_end"])
        self.assertNotIn("route_search", output["data"]["front_end"])
        self.assertNotIn("start_button_tips", output["data"]["front_end"])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_local_script_has_guard_and_in_place_compaction(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Amap R-Store supported-route guard v1", source)
        self.assertIn(COMPACTION_MARKER, source)
        self.assertIn("function compactInPlace(items, mode)", source)
        self.assertNotIn(".filter(", source)
        self.assertLess(source.index("const shouldProcess ="), source.index("JSON.parse($response.body)"))
        self.assertIn("if (!$response.body) {", source)

    def test_all_fourteen_active_triggers_migrate_and_are_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://m%d.amap.com/api script-path=%s,tag=AMAP-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(14)
        ) + "\n[MITM]\nhostname = *.amap.com\n"
        result = rewrite_plugin(fixture)
        self.assertEqual(result.count(LOCAL), 14)
        self.assertNotIn(REMOTE, result)
        self.assertEqual(rewrite_plugin(result), result)
        partial = "\n".join(line for line in fixture.splitlines() if "tag=AMAP-3," not in line)
        with self.assertRaisesRegex(ValueError, "expected 14"):
            rewrite_plugin(partial)

    def test_route_guard_covers_all_fourteen_upstream_endpoint_families(self):
        source = SOURCE.read_text(encoding="utf-8")
        expected = [
            "/aos/perception/publicTravel/beforeNavi", "/bus/plan/integrate",
            "/c3frontend/af-hotel/page/main", "/c3frontend/af-launch/page/main",
            "/perception/drive/routeInfo", "/perception/drive/routePlan",
            "/shield/search/common/coupon/info", "/shield/search/poi/detail",
            "/shield/search_business/process/marketingOperationStructured",
            "/shield/search_poi/", "/faas/amap-navigation/card-service-plan-home",
            "/faas/amap-navigation/main-page", "/shield/frogserver/aocs/updatable/1",
            "/shield/dsp/profile/index/nodefaasv", "/shield/search/nearbyrec_smart",
            "/boss/car/order/content_info", "/boss/order_web/friendly_information",
            "/promotion-web/resource", "/sharedtrip/taxi/order_detail_car_tips",
            "/shield/search_bff/hotword", "/valueadded/alimama/splash_screen"
        ]
        for route in expected:
            self.assertIn('url.includes("' + route + '")', source)

    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeJSON = JSON;
let parseCount = 0, stringifyCount = 0, doneResult;
const trackedJSON = {
  parse(value) { parseCount++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCount++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: {url: payload.url},
  $response: {body: payload.body},
  $done(value) { doneResult = value; },
  console: {log(){}, warn(){}, error(){}}
};
vm.runInNewContext("Array.prototype.filter = function(){ throw new Error('Array.filter used'); };", context);
vm.runInNewContext(source, context, {timeout:5000});
process.stdout.write(nativeJSON.stringify({doneResult, parseCount, stringifyCount}));
"""
        result = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}),
            text=True, capture_output=True, check=True, timeout=10
        )
        return json.loads(result.stdout)

    def test_empty_body_and_unmatched_route_skip_json_parse(self):
        empty = self.run_script("https://m1.amap.com/ws/aos/perception/publicTravel/beforeNavi?", "")
        self.assertEqual(empty["doneResult"], {})
        self.assertEqual(empty["parseCount"], 0)
        unmatched = self.run_script("https://m1.amap.com/ws/shield/unused/large", '{"payload":1}')
        self.assertEqual(unmatched["doneResult"], {})
        self.assertEqual(unmatched["parseCount"], 0)
        self.assertEqual(unmatched["stringifyCount"], 0)

    def test_scalar_membership_hot_loops_use_direct_comparisons(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(SCALAR_MARKER, source)
        for stale in (
            "AMAP_STATIC_ITEMS_06", "AMAP_STATIC_ITEMS_09",
            "AMAP_STATIC_ITEMS_10", "AMAP_STATIC_ITEMS_11",
            "AMAP_STATIC_ITEMS_12", "AMAP_STATIC_ITEMS_13",
            ".includes(item?.tip?.", ".includes(i?.item_type)", "items?.includes(i)",
        ):
            self.assertNotIn(stale, source)
        nearby_start = source.index('} else if (url.includes("/shield/search/nearbyrec_smart"))')
        nearby_end = source.index('} else if (url.includes("/shield/search/poi/detail"))', nearby_start)
        nearby = source[nearby_start:nearby_end]
        self.assertIn("Array.isArray(obj?.data?.modules)", nearby)
        self.assertEqual(nearby.count("if (obj?.data?.modules?.length > 0)"), 0)
        self.assertIn('compactInPlace(obj.data.modules, "nearbyModules")', nearby)
        self.assertIn('item === "head" || item === "search_hot_words" || item === "feed_rec"', source)
        self.assertEqual(optimize_source(source), source)

    def test_nearby_module_scalar_filter_preserves_order_and_values(self):
        body = {"data": {"modules": [
            "head", "unused", "search_hot_words", "feed_rec", "banner"
        ]}}
        result = self.run_script(
            "https://m1.amap.com/ws/shield/search/nearbyrec_smart?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["modules"], ["head", "search_hot_words", "feed_rec"])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_mutation_tracking_is_complete_and_optimizer_is_idempotent(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(TRACKING_MARKER, source)
        self.assertIn("function sameValue(", source)
        self.assertIn("function setIfDifferent(", source)
        self.assertIn("function deleteIfPresent(", source)
        self.assertIn("$done(modified ? {body: JSON.stringify(obj)} : {});", source)
        self.assertIn("if (write !== length)", source)
        self.assertIn("items.length = write;", source)
        self.assertIn("modified = true;", source)
        handler = source[source.index("let obj = JSON.parse($response.body);"):source.index("$done(modified ? {body: JSON.stringify(obj)} : {});")]
        self.assertNotRegex(handler, r"^\s*delete\s+", msg="raw response delete remains")
        self.assertEqual(optimize_source(source), source)

    def test_supported_noop_response_skips_stringify(self):
        body = {"data": {"common_data": {
            "bus_plan_bottom_event": {"data": []},
            "bus_plan_segment_event": {"data": []}
        }, "front_end": {"assistant": []}}}
        result = self.run_script(
            "https://m1.amap.com/ws/aos/perception/publicTravel/beforeNavi?x=1",
            json.dumps(body)
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_noop_in_place_compaction_skips_stringify(self):
        body = {"data": {
            "cardList": [{"dataKey": "ContinueNavigationCard"}],
            "mapBizList": [{"dataKey": "FindCarVirtualCard"}]
        }}
        result = self.run_script(
            "https://m1.amap.com/ws/faas/amap-navigation/main-page?x=1",
            json.dumps(body)
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_real_compaction_serializes_once_and_preserves_kept_items(self):
        body = {"data": {
            "cardList": [
                {"dataKey": "AdvertisementCard"},
                {"dataKey": "ContinueNavigationCard"}
            ],
            "mapBizList": [{"dataKey": "FindCarVirtualCard"}]
        }}
        result = self.run_script(
            "https://m1.amap.com/ws/faas/amap-navigation/main-page?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["dataKey"] for x in output["data"]["cardList"]], ["ContinueNavigationCard"])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_repeated_splash_values_skip_stringify(self):
        body = {"data": {"ad": [{
            "set": {"setting": {"display_time": 0}},
            "creative": [{"start_time": 3818332800, "end_time": 3818419199}]
        }]}}
        result = self.run_script(
            "https://m1.amap.com/ws/valueadded/alimama/splash_screen?x=1",
            json.dumps(body)
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_delete_missing_promotion_fields_skips_stringify(self):
        result = self.run_script(
            "https://m1.amap.com/ws/promotion-web/resource?x=1",
            json.dumps({"data": {"unrelated": 1}})
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_actual_promotion_delete_serializes_once(self):
        result = self.run_script(
            "https://m1.amap.com/ws/promotion-web/resource?x=1",
            json.dumps({"data": {"alpha": {"id": 1}, "keep": 2}})
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"], {"keep": 2})
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_before_navi_keeps_existing_mutation(self):
        body = {"data": {"common_data": {
            "bus_plan_bottom_event": {"data": [{"id": 1}]},
            "bus_plan_segment_event": {"data": [{"id": 2}]}
        }, "front_end": {"assistant": [{"id": "promo"}]}}}
        result = self.run_script(
            "https://m1.amap.com/ws/aos/perception/publicTravel/beforeNavi?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["common_data"]["bus_plan_bottom_event"]["data"], [])
        self.assertEqual(output["data"]["common_data"]["bus_plan_segment_event"]["data"], [])
        self.assertEqual(output["data"]["front_end"]["assistant"], [])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_search_hotword_route_is_reachable_and_clears_header_hotwords(self):
        body = {"data": {"headerHotWord": [{"id": 1}, {"id": 2}]}}
        result = self.run_script(
            "https://m1.amap.com/ws/shield/search_bff/hotword?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["headerHotWord"], [])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_splash_route_is_reachable_and_disables_creative_display(self):
        body = {"data": {"ad": [{
            "set": {"setting": {"display_time": 10}},
            "creative": [{"start_time": 1, "end_time": 2}]
        }]}}
        result = self.run_script(
            "https://m1.amap.com/ws/valueadded/alimama/splash_screen?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        ad = output["data"]["ad"][0]
        self.assertEqual(ad["set"]["setting"]["display_time"], 0)
        self.assertEqual(ad["creative"][0]["start_time"], 3818332800)
        self.assertEqual(ad["creative"][0]["end_time"], 3818419199)
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_optimizer_repairs_missing_supported_routes_after_upstream_refresh(self):
        source = SOURCE.read_text(encoding="utf-8")
        damaged = source.replace('  url.includes("/shield/search_bff/hotword") ||\n', "", 1)
        self.assertNotEqual(damaged, source)
        repaired = optimize_source(damaged)
        self.assertIn('url.includes("/shield/search_bff/hotword")', repaired)
        self.assertIn('url.includes("/valueadded/alimama/splash_screen")', repaired)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_specialized_compaction_modes_remove_per_item_callbacks(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count(COMPACTION_MARKER), 1)
        self.assertEqual(source.count("compactInPlace("), 14)
        for mode, count in (
            ("withoutSchema", 1), ("homeCards", 1), ("findCar", 1),
            ("dynamicAds", 4), ("nonMusic", 1), ("myOrder", 1),
            ("nearbyModules", 1), ("searchContent", 1),
            ("suggestions", 1), ("citySuggestions", 1),
        ):
            self.assertEqual(source.count(', "' + mode + '")'), count)
        self.assertNotRegex(
            source,
            r'compactInPlace\([^,\n]+,\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>',
        )
        self.assertIn("const length = items.length;", source)
        self.assertEqual(optimize_source(source), source)

    def test_homepage_card_modes_keep_only_expected_items_and_order(self):
        body = {"data": {
            "cardList": [
                {"dataKey": "ContinueNavigationCard"},
                {"dataKey": "PromotionCard"},
                {"dataKey": "FrequentLocation"},
                {"dataKey": "LoginCard"},
            ],
            "mapBizList": [
                {"dataKey": "FindCarVirtualCard"},
                {"dataKey": "PromotionCard"},
            ],
        }}
        result = self.run_script(
            "https://m1.amap.com/ws/faas/amap-navigation/main-page?x=1",
            json.dumps(body),
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(
            [item["dataKey"] for item in output["data"]["cardList"]],
            ["ContinueNavigationCard", "FrequentLocation", "LoginCard"],
        )
        self.assertEqual(
            [item["dataKey"] for item in output["data"]["mapBizList"]],
            ["FindCarVirtualCard"],
        )
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_search_card_filter_uses_specialized_direct_loop_and_optimizer_repairs_upstream_form(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(COMPACTION_MARKER, source)
        self.assertIn('compactInPlace(list.content, "searchContent")', source)
        self.assertIn('const itemType = item?.item_type;', source)
        self.assertNotIn('compactInPlace(list.content, (', source)
        self.assertEqual(optimize_source(source), source)

        damaged = source.replace(
            'compactInPlace(list.content, "searchContent")',
            'compactInPlace(list.content, (item) => item?.item_type !== "brandAdCard" && item?.item_type !== "toplist_al");',
            1,
        )
        self.assertNotEqual(damaged, source)
        repaired = optimize_source(damaged)
        self.assertIn('compactInPlace(list.content, "searchContent")', repaired)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_search_suggestion_modes_cache_tip_reference_in_direct_loops(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = 'if (url.includes("/shield/search_poi/sug")) {'
        end = '} else if (url.includes("/shield/search_poi/tips_operation_location")) {'
        i = source.index(start)
        j = source.index(end, i + len(start))
        block = source[i:j]
        self.assertIn('compactInPlace(obj.tip_list, "suggestions")', block)
        self.assertIn('compactInPlace(city.tip_list, "citySuggestions")', block)
        self.assertEqual(source.count("const tip = item?.tip;"), 2)
        self.assertNotIn("item?.tip?.", source)
        self.assertEqual(source.count("// loon-change: Amap suggestion scalar property cache v1"), 2)
        self.assertEqual(source.count("const datatypeSpec = tip?.datatype_spec;"), 2)
        self.assertEqual(source.count("const resultType = tip?.result_type;"), 2)
        self.assertEqual(source.count("const taskTag = tip?.task_tag;"), 1)
        self.assertNotIn("tip?.result_type !==", source)
        self.assertNotIn("tip?.task_tag !==", source)
        self.assertEqual(optimize_source(source), source)

        upstream_block = """if (url.includes("/shield/search_poi/sug")) {
  if (Array.isArray(obj?.tip_list) && obj.tip_list.length > 0) {
    compactInPlace(obj.tip_list, item =>
      item?.tip?.datatype_spec !== "12" &&
      item?.tip?.result_type !== "ad" &&
      item?.tip?.result_type !== "poi_ad" &&
      item?.tip?.result_type !== "toplist" &&
      item?.tip?.task_tag !== "ad" &&
      item?.tip?.task_tag !== "exct_query_sug_merge_theme" &&
      item?.tip?.task_tag !== "query_sug_merge_theme" &&
      item?.tip?.task_tag !== "sp"
    );
  } else if (Array.isArray(obj?.city_list) && obj.city_list.length > 0) {
    for (const city of obj.city_list) {
      if (Array.isArray(city?.tip_list) && city.tip_list.length > 0) {
        compactInPlace(city.tip_list, item =>
          item?.tip?.datatype_spec !== "12" &&
          item?.tip?.result_type !== "ad" &&
          item?.tip?.result_type !== "poi_ad"
        );
      }
    }
  }
"""
        damaged = source[:i] + upstream_block + source[j:]
        repaired = optimize_source(damaged)
        self.assertIn(COMPACTION_MARKER, repaired)
        self.assertIn('compactInPlace(obj.tip_list, "suggestions")', repaired)
        self.assertIn('compactInPlace(city.tip_list, "citySuggestions")', repaired)
        self.assertEqual(optimize_source(repaired), repaired)

    def test_search_suggestion_filters_use_in_place_compaction(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index('if (url.includes("/shield/search_poi/sug")) {')
        end = source.index('} else if (url.includes("/shield/search_poi/tips_operation_location")) {', start)
        block = source[start:end]
        self.assertIn('compactInPlace(obj.tip_list, "suggestions")', block)
        self.assertIn('compactInPlace(city.tip_list, "citySuggestions")', block)
        self.assertNotIn("newLists", block)
        self.assertNotIn("newTips", block)
        self.assertEqual(optimize_source(source), source)

    def test_city_search_suggestion_filter_preserves_city_and_tip_order(self):
        body = {"city_list": [
            {"city": "A", "tip_list": [
                {"tip": {"datatype_spec": "1", "result_type": "poi"}, "id": 1},
                {"tip": {"datatype_spec": "12", "result_type": "poi"}, "id": 2},
                {"tip": {"datatype_spec": "1", "result_type": "ad"}, "id": 3},
                {"tip": {"datatype_spec": "1", "result_type": "poi"}, "id": 4}
            ]},
            {"city": "B", "tip_list": [
                {"tip": {"datatype_spec": "1", "result_type": "poi"}, "id": 5}
            ]}
        ]}
        result = self.run_script(
            "https://m1.amap.com/ws/shield/search_poi/sug?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([city["city"] for city in output["city_list"]], ["A", "B"])
        self.assertEqual([x["id"] for x in output["city_list"][0]["tip_list"]], [1, 4])
        self.assertEqual([x["id"] for x in output["city_list"][1]["tip_list"]], [5])

    def test_search_suggestion_filter_preserves_kept_item_order(self):
        body = {"tip_list": [
            {"tip": {"datatype_spec": "1", "result_type": "poi", "task_tag": "normal"}, "id": 1},
            {"tip": {"datatype_spec": "12", "result_type": "poi", "task_tag": "normal"}, "id": 2},
            {"tip": {"datatype_spec": "1", "result_type": "ad", "task_tag": "normal"}, "id": 3},
            {"tip": {"datatype_spec": "1", "result_type": "poi", "task_tag": "normal"}, "id": 4}
        ]}
        result = self.run_script(
            "https://m1.amap.com/ws/shield/search_poi/sug?x=1",
            json.dumps(body)
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([x["id"] for x in output["tip_list"]], [1, 4])


if __name__ == "__main__":
    unittest.main()
