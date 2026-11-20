import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_smzdm import (
    EXPECTED_TRIGGERS,
    LOCAL,
    MARKER,
    REMOTE,
    optimize_source,
    rewrite_plugin,
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "smzdm" / "smzdm.js"
NODE = shutil.which("node")


class SMZDMOptimizerTests(unittest.TestCase):
    def test_checked_in_script_is_idempotent_and_has_no_allocating_array_filters(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)
        self.assertIn("function compactInPlace(items, keep)", source)
        self.assertIn("function deleteIfPresent(target, key)", source)
        self.assertIn("if (!$response.body) {", source)
        self.assertIn("if (modified) {", source)

    def test_all_nine_smzdm_triggers_are_migrated_and_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://smzdm%d.example/api script-path=%s,tag=SMZDM-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(EXPECTED_TRIGGERS)
        ) + "\n[MITM]\nhostname = smzdm.example\n"
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertNotIn(REMOTE, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)

    def test_partial_and_mixed_script_url_inventories_fail_closed(self):
        partial = "[Script]\n" + "\n".join(
            "http-response ^https://smzdm.example/%d script-path=%s" % (index, REMOTE)
            for index in range(EXPECTED_TRIGGERS - 1)
        )
        with self.assertRaisesRegex(ValueError, "expected 9"):
            rewrite_plugin(partial)
        mixed = partial + "\nhttp-response ^https://smzdm.example/local script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


@unittest.skipUnless(NODE, "Node.js is required for SMZDM response runtime tests")]
class SMZDMRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const nativeParse = JSON.parse.bind(JSON);
const nativeStringify = JSON.stringify.bind(JSON);
let doneResult;
let doneCount = 0;
const context = {
  $request: { url: payload.url },
  $response: { body: payload.body === null ? "" : nativeStringify(payload.body) },
  $done(value) { doneResult = value; doneCount++; },
  parseCount: 0,
  stringifyCount: 0,
  nativeParse,
  nativeStringify,
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(`
  JSON.parse = function(value) { parseCount++; return nativeParse(value); };
  JSON.stringify = function(value) { stringifyCount++; return nativeStringify(value); };
  Array.prototype.filter = function() { throw new Error("allocating Array.filter remains"); };
  Array.prototype.map = function() { throw new Error("allocating Array.map remains"); };
`, context);
vm.runInContext(source, context, { timeout: 5000 });
if (doneCount !== 1) throw new Error("script must call $done exactly once; got " + doneCount);
const output = doneResult && typeof doneResult.body === "string" ? nativeParse(doneResult.body) : null;
process.stdout.write(nativeStringify({
  done: doneResult,
  output,
  parseCount: context.parseCount,
  stringifyCount: context.stringifyCount,
  doneCount
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_empty_body_exits_before_json_parse(self):
        result = self.run_script("https://homepage-api.smzdm.com/v1/home", None)
        self.assertEqual(result["done"], {})
        self.assertEqual(result["parseCount"], 0)
        self.assertEqual(result["stringifyCount"], 0)
        self.assertEqual(result["doneCount"], 1)

    def test_homepage_compacts_nested_and_target_arrays_in_place(self):
        body = {
            "data": {
                "component": [
                    {"zz_type": "circular_banner", "pos": 8},
                    {"zz_type": "ad", "pos": 9},
                    {"zz_type": "list", "pos": 10},
                ],
                "functions": [{"type": "message", "pos": 8}, {"type": "ad", "pos": 9}],
                "services": [
                    {"type": "articel_manage", "pos": 8},
                    {"type": "advertisement", "pos": 9},
                    {"type": "199794", "pos": 10},
                ],
                "rows": [
                    {"id": "keep"},
                    {"id": "banner", "ad_banner_id": "ad-1"},
                    {"id": "campaign", "ad": "ad_campaign_name"},
                ],
                "nested": [
                    {"cell_type": "23008", "id": "drop-a"},
                    {"cell_type": "normal", "children": [
                        {"cell_type": "23005", "id": "drop-b"},
                        {"id": "keep-child"},
                    ]},
                    {"cell_type": "23024", "id": "drop-c"},
                ],
                "widget": {"ad": True},
                "operation_float_screen": {"ad": True},
            }
        }
        result = self.run_script("https://homepage-api.smzdm.com/v1/home", body)
        output = result["output"]
        data = output["data"]
        self.assertEqual([item["zz_type"] for item in data["component"]], ["circular_banner", "list"])
        self.assertEqual([item["pos"] for item in data["component"]], [1, 2])
        self.assertEqual([item["type"] for item in data["functions"]], ["message"])
        self.assertEqual([item["pos"] for item in data["functions"]], [1])
        self.assertEqual([item["type"] for item in data["services"]], ["articel_manage", "199794"])
        self.assertEqual([item["pos"] for item in data["services"]], [1, 2])
        self.assertEqual([item["id"] for item in data["rows"]], ["keep"])
        self.assertEqual(data["nested"], [{"cell_type": "normal", "children": [{"id": "keep-child"}]}])
        self.assertNotIn("widget", data)
        self.assertNotIn("operation_float_screen", data)
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_already_clean_homepage_skips_response_serialization(self):
        body = {
            "data": {
                "component": [{"zz_type": "list", "pos": 1}],
                "functions": [{"type": "message", "pos": 1}],
                "services": [{"type": "199794", "pos": 1}],
                "rows": [{"id": "normal"}],
                "nested": [{"cell_type": "normal", "children": [{"id": "ok"}]}],
            }
        }
        result = self.run_script("https://homepage-api.smzdm.com/v1/home", body)
        self.assertEqual(result["done"], {})
        self.assertEqual(result["output"], None)
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 0)

    def test_app_home_preserves_allowlist_and_repairs_position(self):
        body = {"data": [
            {"id": "40", "pos": 3}, {"id": "other", "pos": 4}, {"id": "20", "pos": 5}
        ]}
        result = self.run_script("https://qianbao.smzdm.com/v1/app/home", body)
        self.assertEqual([item["id"] for item in result["output"]["data"]], ["40", "20"])
        self.assertEqual([item["pos"] for item in result["output"]["data"]], [1, 2])
        self.assertEqual(result["parseCount"], 1)
        self.assertEqual(result["stringifyCount"], 1)

    def test_vip_route_deletes_ad_fields_but_clean_payload_passes_through(self):
        clean = self.run_script("https://haojia-api.smzdm.com/vip/creator_user_center", {"data": {}})
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)

        changed = self.run_script(
            "https://haojia-api.smzdm.com/vip/info",
            {"data": {"big_banner": {"id": 1}, "top_banner": {"id": 2}, "profile": "ok"}},
        )
        self.assertEqual(changed["output"], {"data": {"profile": "ok"}})
        self.assertEqual(changed["stringifyCount"], 1)

    def test_footer_pic_cleanup_and_util_loading_delete_only_when_present(self):
        footer = self.run_script(
            "https://post.m.smzdm.com/ajax_app/ajax_get_footer_list",
            {"data": {"activity_banner": {"hot_widget": [{"pic_url": "ad.jpg", "name": "x"}, {"name": "y"}]}}},
        )
        self.assertEqual(footer["output"]["data"]["activity_banner"]["hot_widget"], [{"name": "x"}, {"name": "y"}])
        self.assertEqual(footer["stringifyCount"], 1)

        clean = self.run_script("https://api.smzdm.com/util/loading", {"meta": {"ok": True}})
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)


if __name__ == "__main__":
    unittest.main()
