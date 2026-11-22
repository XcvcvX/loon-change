import json
import shutil
import subprocess
import unittest
from pathlib import Path

from apply_local_overrides import (
    CNTV_LOCAL_SCRIPT_URL,
    CNTV_REMOTE_SCRIPT_URL,
    migrate_cntv_script_to_local,
)
from optimize_cntv import MARKER, MENUS_MARKER, YOUKU_HOME_FEED_MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "cntv" / "cntv.js"
NODE = shutil.which("node")


class CNTVOptimizerTests(unittest.TestCase):
    def test_checked_in_snapshot_is_idempotent_and_all_filters_are_in_place(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(source.count("compactInPlace(") - 1, 24)
        self.assertNotIn(".filter(", source)
        self.assertIn("if (!$response.body) {", source)
        self.assertTrue(source.rstrip().endswith("}"))
        self.assertIn(MENUS_MARKER, source)
        menus_branch = source.split('url.includes("/getMyMenus?")', 1)[1].split('url.includes("/home_top_menu?")', 1)[0]
        self.assertNotIn("newMenus", menus_branch)
        self.assertNotIn("newLists", menus_branch)

    def test_iqiyi_feed_branches_use_in_place_compaction_without_temporary_arrays(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("// loon-change: CNTV iQIYI feed array compaction v1", source)
        branches = [
            ('  } else if (url.includes("/views_category/")) {', '  } else if (url.includes("/views_comment/")) {'),
            ('  } else if (url.includes("/views_home/")) {', '  } else if (url.includes("/views_plt/")) {'),
            ('  } else if (url.includes("/views_search/")) {', '  } else if (url.includes("/waterfall/")) {'),
            ('  } else if (url.includes("/waterfall/")) {', '} else if (isMG) {'),
        ]
        for start, end in branches:
            block = source.split(start, 1)[1].split(end, 1)[0]
            self.assertIn("compactInPlace(", block)
            for allocation in ("newCards", "newItems", "newBlocks"):
                self.assertNotIn(allocation, block)
        self.assertEqual(optimize_source(source), source)

    def test_all_26_response_triggers_are_migrated_and_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://cntv%d.example/api script-path=%s,tag=CNTV-%d,requires-body=true"
            % (index, CNTV_REMOTE_SCRIPT_URL, index)
            for index in range(26)
        ) + "\n[MITM]\nhostname = cntv.example\n"
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(CNTV_LOCAL_SCRIPT_URL), 26)
        self.assertNotIn(CNTV_REMOTE_SCRIPT_URL, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)

        lines, changed = migrate_cntv_script_to_local(fixture.splitlines())
        self.assertEqual(changed, 26)
        self.assertEqual(sum(CNTV_LOCAL_SCRIPT_URL in line for line in lines), 26)
        lines_again, changed_again = migrate_cntv_script_to_local(lines)
        self.assertEqual(changed_again, 0)
        self.assertEqual(lines_again, lines)

    def test_partial_local_inventory_fails_closed(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://cntv%d.example/api script-path=%s,tag=CNTV-%d,requires-body=true"
            % (index, CNTV_LOCAL_SCRIPT_URL, index)
            for index in range(2)
        )
        with self.assertRaisesRegex(ValueError, "expected 26"):
            rewrite_plugin(fixture)

    def test_standalone_cntv_inventory_is_not_removed_as_cnftp_duplicate(self):
        from apply_local_overrides import (
            CNFTP_DUPLICATE_REMOVE_TRIGGERS,
            remove_duplicate_cnftp_scripts,
        )
        fixture = ["[Script]", *CNFTP_DUPLICATE_REMOVE_TRIGGERS, "[MITM]"]
        self.assertEqual(remove_duplicate_cnftp_scripts(fixture), (fixture, 0))

    def test_legacy_response_syntax_is_migrated_without_requiring_http_response_form(self):
        fixture = [
            "[Script]",
            'response if ${url} ~= /^https?:\\/\\/me\\.bz\\.mgtv\\.com\\/v3\\/module\\/list\\?/ then script("' + CNTV_REMOTE_SCRIPT_URL + '") with enable=mhgotv_enable, tag="芒果TV我的页面", timeout=60, requires_body=true',
            "[MITM]",
            "hostname = me.bz.mgtv.com",
        ]
        lines, changed = migrate_cntv_script_to_local(fixture)
        self.assertEqual(changed, 1)
        self.assertIn(CNTV_LOCAL_SCRIPT_URL, "\\n".join(lines))
        self.assertNotIn(CNTV_REMOTE_SCRIPT_URL, "\\n".join(lines))

    def test_partial_trigger_inventory_fails_closed(self):
        fixture = ["[Script]"] + [
            "http-response ^https://cntv.example/api script-path=%s,tag=CNTV,requires-body=true"
            % CNTV_REMOTE_SCRIPT_URL
        ] + ["[MITM]", "hostname = cntv.example"]
        with self.assertRaisesRegex(ValueError, "expected 26"):
            rewrite_plugin("\\n".join(fixture))


@unittest.skipUnless(NODE, "Node.js is required for CNTV response runtime tests")
class CNTVRuntimeTests(unittest.TestCase):
    def run_script(self, url, body, disable_push=False):
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
if (payload.disablePush) vm.runInContext("Array.prototype.push = function() { throw new Error('temporary push allocation remains'); };", context);
vm.runInContext(source, context, { timeout: 5000 });
if (context.__parseCount > 1) throw new Error("response parsed more than once");
if (payload.body === null) {
  if (!doneResult || Object.keys(doneResult).length !== 0) throw new Error("empty response did not finish cleanly");
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, empty: true }));
} else {
  if (!doneResult || typeof doneResult.body !== "string") throw new Error("missing rewritten response");
  process.stdout.write(JSON.stringify({ parseCount: context.__parseCount, output: JSON.parse(doneResult.body) }));
}
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body, "disablePush": disable_push}),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_iqiyi_bottom_theme_compacts_in_place_and_repairs_order(self):
        body = {"cards": [{"items": [
            {"_id": "29"}, {"_id": "35"}, {"_id": "31"}, {"_id": "184"}, {"_id": "34"}
        ]}]}
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/bottom_theme?version=1", body)
        items = result["output"]["cards"][0]["items"]
        self.assertEqual([item["_id"] for item in items], ["29", "31", "34"])
        self.assertEqual([item["show_order"] for item in items], [1, 2, 3])
        self.assertEqual(result["parseCount"], 1)

    def test_mgtv_video_info_compacts_category_list_without_reordering(self):
        body = {"data": {"categoryList": [
            {"dataType": 1}, {"dataType": 2}, {"dataType": 3}, {"dataType": 8}, {"dataType": 20}
        ]}}
        result = self.run_script("https://mobile.api.mgtv.com/video/info?foo=1", body)
        self.assertEqual(
            [item["dataType"] for item in result["output"]["data"]["categoryList"]],
            [1, 3, 20],
        )
        self.assertEqual(result["parseCount"], 1)

    def test_youku_bottom_tabs_compact_and_keep_menu_indexes(self):
        body = {"data": {"model": {"configInfo": {"bottomNavigate": {"data": {
            "bottomTabList": [
                {"type": "HOME"}, {"type": "SEARCH"}, {"type": "NEW_UCENTER"},
                {"type": "DONGTAI"}, {"type": "VIP_MEMBER"}
            ]
        }}}}}}
        result = self.run_script(
            "https://acs.youku.com/gw/mtop.youku.haidai.lantern.appconfig.get/",
            body,
        )
        items = result["output"]["data"]["model"]["configInfo"]["bottomNavigate"]["data"]["bottomTabList"]
        self.assertEqual([item["type"] for item in items], ["HOME", "NEW_UCENTER", "VIP_MEMBER"])
        self.assertEqual([item["menuIndex"] for item in items], [1, 2, 3])
        self.assertEqual(result["parseCount"], 1)

    def test_iqiyi_comment_cards_keep_only_non_ad_resource_entries(self):
        body = {"cards": [
            {"alias_name": "normal_comment"},
            {"alias_name": "comment_resource_card"},
            {"alias_name": "comment_resource_convention_card"},
            {"title": "missing alias"}
        ]}
        result = self.run_script(
            "https://comment-card.iqiyi.com/views_comment/3.0/long_video_comments?foo=1",
            body,
        )
        self.assertEqual(
            [item["alias_name"] for item in result["output"]["cards"]],
            ["normal_comment"],
        )

    def test_iqiyi_my_menus_compacts_outer_and_inner_arrays_in_place(self):
        body = {"data": [
            {"statistic": {"block": "wd_liebiao_2"}, "menuList": [{"menuType": 1}]},
            {"statistic": {"block": "normal"}, "menuList": [
                {"menuType": 1, "id": "keep-1"},
                {"menuType": 121, "id": "survey"},
                {"menuType": 2, "id": "keep-2"}
            ]},
            {"statistic": {"block": "normal"}, "menuList": []},
            {"statistic": {"block": "wd_liebiao_4"}}
        ]}
        result = self.run_script(
            "https://iface2.iqiyi.com/aggregate/3.0/getMyMenus?foo=1",
            body,
            disable_push=True,
        )
        data = result["output"]["data"]
        self.assertEqual(len(data), 2)
        self.assertEqual([item["id"] for item in data[0]["menuList"]], ["keep-1", "keep-2"])
        self.assertEqual(data[1]["menuList"], [])
        self.assertEqual(result["parseCount"], 1)

    def test_iqiyi_feed_and_search_paths_compact_nested_arrays_in_place(self):
        category = {"base": {"statistics": {"ad_str": "ad"}}, "cards": [
            {"blocks": [{"block_name": "block_321"}, {"block_name": "normal"}, {"buttons": [{"id": "ad"}]}, {"block_name": "keep"}]},
            {"title": "card without blocks"}
        ]}
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/views_category/list", category, disable_push=True)
        self.assertEqual(len(result["output"]["cards"]), 2)
        self.assertEqual(len(result["output"]["cards"][0]["blocks"]), 2)
        self.assertNotIn("ad_str", result["output"]["base"]["statistics"])

        home = {"cards": [
            {"alias_name": "ad_mobile_flow"},
            {"alias_name": "normal", "top_banner": {"l_blocks": [{"buttons": [{"id": "x"}]}, {"title": "keep"}]}}
        ]}
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/views_home/list", home, disable_push=True)
        self.assertEqual(len(result["output"]["cards"]), 1)
        self.assertNotIn("buttons", result["output"]["cards"][0]["top_banner"]["l_blocks"][0])

        search = {"cards": [
            {"strategy_com_id": "search_vip_banner"},
            {"strategy_com_id": "normal", "blocks": [
                {"block_name": "keep"}, {"block_type": 959}, {"block_type": 10}, {"title": "drop"}
            ]}
        ]}
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/views_search/list", search, disable_push=True)
        blocks = result["output"]["cards"][0]["blocks"]
        self.assertEqual(len(result["output"]["cards"]), 1)
        self.assertEqual([item.get("block_type") for item in blocks], [None, 10])

        waterfall = {"cards": [
            {"block_class": "ad"},
            {"blocks": [{"block_class": "ad"}, {"id": "keep"}]},
            {"id": "keep-card"}
        ]}
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/waterfall/list", waterfall, disable_push=True)
        self.assertEqual(len(result["output"]["cards"]), 2)
        self.assertEqual(result["output"]["cards"][0]["blocks"], [{"id": "keep"}])

    def test_empty_body_does_not_attempt_json_parse(self):
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/bottom_theme?version=1", None)
        self.assertTrue(result["empty"])
        self.assertEqual(result["parseCount"], 0)


if __name__ == "__main__":
    unittest.main()


class CNTVPreParseRouteGuardTests(unittest.TestCase):
    def test_route_guard_is_idempotent_and_precedes_json_parse(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("// loon-change: CNTV pre-parse supported-route guard v1", source)
        self.assertEqual(source.count("const shouldProcess ="), 1)
        self.assertLess(source.index("const shouldProcess ="), source.index("let obj = JSON.parse"))
        self.assertEqual(optimize_source(source), source)


    def test_supported_route_inventory_is_explicit(self):
        source = SOURCE.read_text(encoding="utf-8")
        expected = [
            "/bottom_theme?", "/common_switch?", "/control/", "/getMyMenus?",
            "/home_top_menu?", "/mixer?", "/search.video.iqiyi.com/",
            "/views_category/", "/views_comment/", "/views_home/", "/views_plt/",
            "/views_search/", "/waterfall/", "/channel/vrsList/", "/mobile/config?",
            "/mobile/recommend/v", "/vod/info?", "/module/list?", "/video/info?",
            "columbus.gateway.new.execute", "columbus.home.feed/",
            "columbus.home.query/", "columbus.uc.query/", "columbus.ycp.query/",
            "haidai.lantern.appconfig.get/", "huluwa.dispatcher.youthmode.config2/",
            "play.ups.appinfo.get/", "soku.yksearch/"
        ]
        for route in expected:
            self.assertIn('url.includes("' + route + '")', source)
        self.assertIn('(url.includes("/dynamic/v") && url.includes("/channel/index/"))', source)
        self.assertIn('(url.includes("/channel/index?") && url.includes("/odin/c"))', source)


@unittest.skipUnless(NODE, "Node.js is required for CNTV route-guard runtime tests")
class CNTVPreParseRouteGuardRuntimeTests(unittest.TestCase):
    def run_script(self, url, body, disable_push=False):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeJSON = JSON;
let parseCount = 0, stringifyCount = 0;
const trackedJSON = {
  parse(value) { parseCount++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCount++; return nativeJSON.stringify(value); }
};
let doneResult;
const context = {
  JSON: trackedJSON,
  $request: { url: payload.url },
  $response: { body: nativeJSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
if (payload.disablePush) {
  vm.runInNewContext("Array.prototype.push = function() { throw new Error('temporary push allocation remains'); }; Array.prototype.filter = function() { throw new Error('allocating Array.filter remains'); };", context);
}
vm.runInNewContext(source, context, { timeout: 5000 });
process.stdout.write(nativeJSON.stringify({
  doneResult,
  parseCount,
  stringifyCount
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body, "disablePush": disable_push}),
            capture_output=True, text=True, check=True, timeout=10
        )
        return json.loads(completed.stdout)

    def test_unknown_routes_on_all_three_apps_skip_parse_and_stringify(self):
        urls = [
            "https://iface2.iqiyi.com/unrelated/large-feed",
            "https://mobile.api.mgtv.com/unrelated/large-feed",
            "https://acs.youku.com/unrelated/large-feed",
            "https://unrelated.example/views_home/large-feed"
        ]
        body = {"data": [{"payload": "x" * 50000}]}
        for url in urls:
            with self.subTest(url=url):
                result = self.run_script(url, body)
                self.assertEqual(result["doneResult"], {})
                self.assertEqual(result["parseCount"], 0)
                self.assertEqual(result["stringifyCount"], 0)

    def test_supported_routes_keep_existing_processing(self):
        cases = [
            ("https://iface2.iqiyi.com/views/3.0/bottom_theme?version=1", {"cards": [{"items": [{"_id": "29"}, {"_id": "35"}]}]}),
            ("https://mobile.api.mgtv.com/vod/info?foo=1", {"data": {"tabs": [{"type": "1"}, {"type": "3"}]}}),
            ("https://acs.youku.com/gw/mtop.youku.haidai.lantern.appconfig.get/", {"data": {"model": {"configInfo": {"bottomNavigate": {"data": {"bottomTabList": [{"type": "HOME"}, {"type": "SEARCH"}, {"type": "NEW_UCENTER"}]}}}}}})
        ]
        for url, body in cases:
            with self.subTest(url=url):
                result = self.run_script(url, body)
                self.assertEqual(result["parseCount"], 1)
                self.assertEqual(result["stringifyCount"], 1)
                self.assertIsInstance(result["doneResult"].get("body"), str)


    def test_youku_home_feed_compacts_nested_cards_in_place_without_temporary_arrays(self):
        source = SOURCE.read_text(encoding="utf-8")
        branch = source.split('  } else if (url.includes("columbus.home.feed/")) {', 1)[1].split('  } else if (url.includes("columbus.home.query/")) {', 1)[0]
        self.assertIn(YOUKU_HOME_FEED_MARKER, source)
        self.assertNotIn("newNodes", branch)
        self.assertNotIn("newItems", branch)
        self.assertNotIn(".push(", branch)
        body = {"data": {"2019061000": {"data": {"nodes": [
            {"typeName": "NORMAL", "id": "keep-before"},
            {"typeName": "PHONE_FEED_CARD_GROUP", "nodes": [
                {"typeName": "PHONE_FEED_CARD_S_AD", "id": "small-ad"},
                {"typeName": "NORMAL", "id": "keep-1"},
                {"typeName": "PHONE_H_UC_AD", "id": "wide-ad"},
                {"typeName": "NORMAL", "id": "keep-2"}
            ]},
            {"typeName": "PHONE_FEED_CARD_GROUP", "nodes": []},
            {"typeName": "NORMAL", "id": "keep-after"}
        ]}}}}
        result = self.run_script(
            "https://acs.youku.com/gw/mtop.youku.columbus.home.feed/",
            body,
            disable_push=True,
        )
        output = json.loads(result["doneResult"]["body"])
        nodes = output["data"]["2019061000"]["data"]["nodes"]
        self.assertEqual([item.get("id") for item in nodes if item.get("id")], ["keep-before", "keep-after"])
        self.assertEqual([item["id"] for item in nodes[1]["nodes"]], ["keep-1", "keep-2"])
        self.assertEqual(nodes[2]["nodes"], [])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(optimize_source(source), source)

    def test_youku_home_query_compacts_nested_arrays_without_reordering(self):
        source = SOURCE.read_text(encoding="utf-8")
        branch = source.split('  } else if (url.includes("columbus.home.query/")) {', 1)[1].split('  } else if (url.includes("columbus.uc.query/")) {', 1)[0]
        self.assertIn("CNTV Youku home.query nested in-place compaction v1", branch)
        for temporary in ("let newNodes = []", "let newItems = []", "let newII = []", "let newIII = []"):
            self.assertNotIn(temporary, branch)
        body = {"data": {"2019061000": {"data": {"nodes": [
            {"data": {"nodeKey": "CHILD"}, "nodes": []},
            {"data": {"nodeKey": "NORMAL"}, "nodes": [
                {"id": 31476, "data": {"keywords": ["remove"]}},
                {"id": 35505, "data": {}},
                {"id": 7, "typeName": "UC广告抽屉", "data": {}},
                {"id": 8, "data": {"crmSale": {}}, "nodes": [
                    {"typeName": "NORMAL", "nodes": [
                        {"typeName": "KEEP", "data": {"title": "ok"}},
                        {"typeName": "PHONE_FEED_CARD_S_AD", "data": {}},
                        {"typeName": "KEEP_AD", "data": {"ad": {}}}
                    ]}
                ]}
            ]}
        ]}}}}
        result = self.run_script("https://acs.youku.com/gw/mtop.youku.columbus.home.query/", body)
        output = json.loads(result["doneResult"]["body"])
        nodes = output["data"]["2019061000"]["data"]["nodes"]
        self.assertEqual(len(nodes), 1)
        level2 = nodes[0]["nodes"]
        self.assertEqual([item["id"] for item in level2], [31476, 8])
        self.assertNotIn("keywords", level2[0]["data"])
        self.assertNotIn("crmSale", level2[1]["data"])
        level3 = level2[1]["nodes"]
        self.assertEqual(len(level3), 1)
        self.assertEqual(level3[0]["nodes"], [{"typeName": "KEEP", "data": {"title": "ok"}}])
        self.assertEqual(result["parseCount"], 1)

