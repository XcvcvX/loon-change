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
from optimize_cntv import MARKER, MENUS_MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "cntv" / "cntv.js"
NODE = shutil.which("node")


class CNTVOptimizerTests(unittest.TestCase):
    def test_checked_in_snapshot_is_idempotent_and_all_filters_are_in_place(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertEqual(source.count("compactInPlace(") - 1, 13)
        self.assertNotIn(".filter(", source)
        self.assertIn("if (!$response.body) {", source)
        self.assertTrue(source.rstrip().endswith("}"))
        self.assertIn(MENUS_MARKER, source)
        menus_branch = source.split('url.includes("/getMyMenus?")', 1)[1].split('url.includes("/home_top_menu?")', 1)[0]
        self.assertNotIn("newMenus", menus_branch)
        self.assertNotIn("newLists", menus_branch)

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

    def test_empty_body_does_not_attempt_json_parse(self):
        result = self.run_script("https://iface2.iqiyi.com/views/3.0/bottom_theme?version=1", None)
        self.assertTrue(result["empty"])
        self.assertEqual(result["parseCount"], 0)


if __name__ == "__main__":
    unittest.main()
