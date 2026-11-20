import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_xmly import EXPECTED_TRIGGERS, LOCAL, MARKER, REMOTE, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "xmly" / "xmly.js"
NODE = shutil.which("node")


class XimalayaOptimizerTests(unittest.TestCase):
    def test_checked_in_snapshot_is_idempotent_and_uses_no_filter_or_map(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)
        self.assertIn("function compactInPlace(items, keep)", source)
        self.assertEqual(source.count("JSON.parse(body)"), 1)
        self.assertIn("if (modified)", source)

    def test_five_triggers_migrate_exactly_and_fail_closed_on_partial_or_mixed_sets(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://xmly%d.example/api script-path=%s,tag=XMLY-%d,requires-body=true"
            % (index, REMOTE, index)
            for index in range(EXPECTED_TRIGGERS)
        ) + "\n[MITM]\nhostname = xmly.example\n"
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertNotIn(REMOTE, migrated)
        self.assertEqual(rewrite_plugin(migrated), migrated)
        partial = chr(10).join(line for line in fixture.splitlines() if "tag=XMLY-4," not in line)
        with self.assertRaisesRegex(ValueError, "expected 5"):
            rewrite_plugin(partial)
        mixed = fixture + "http-response ^https://xmly.local/api script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


@unittest.skipUnless(NODE, "Node.js is required for Ximalaya response runtime tests")
class XimalayaRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult, doneCount = 0;
const c = {
  $request: {url: input.url},
  $response: {body: input.body === null ? "" : (typeof input.body === "string" ? input.body : JSON.stringify(input.body))},
  $done(value) { doneResult = value; doneCount++; },
  console: {log() {}, warn() {}, error() {}}
};
vm.createContext(c);
vm.runInContext(
  "const nativeParse=JSON.parse, nativeStringify=JSON.stringify;" +
  "globalThis.__nativeStringify=nativeStringify;" +
  "globalThis.__counts={parse:0,stringify:0};" +
  "JSON.parse=function(v){__counts.parse++;return nativeParse(v)};" +
  "JSON.stringify=function(v){__counts.stringify++;return nativeStringify(v)};" +
  "Array.prototype.filter=function(){throw new Error('Array.filter must not be used')};" +
  "Array.prototype.map=function(){throw new Error('Array.map must not be used')};",
  c
);
vm.runInContext(source, c, {timeout:5000});
if (doneCount !== 1) throw new Error("expected exactly one $done call, got " + doneCount);
const output = doneResult && typeof doneResult.body === "string" ? JSON.parse(doneResult.body) : null;
process.stdout.write(c.__nativeStringify({
  done: doneResult, output, parseCount: c.__counts.parse,
  stringifyCount: c.__counts.stringify, doneCount
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}, ensure_ascii=False),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_custom_category_lists_are_compacted_and_clean_response_skips_stringify(self):
        body = {
            "customCategoryList": [
                {"itemType": "recommend", "categoryId": 1000},
                {"itemType": "other", "categoryId": 1001},
                {"itemType": "single_category", "categoryId": 1005},
                {"itemType": "template_category", "categoryId": 1002}
            ],
            "defaultTabList": [
                {"itemType": "recommend", "categoryId": 1005},
                {"itemType": "template_category", "categoryId": 2}
            ]
        }
        changed = self.run_script("https://www.ximalaya.com/discovery-category/customCategories", body)
        self.assertEqual([x["categoryId"] for x in changed["output"]["customCategoryList"]], [1000, 1002])
        self.assertEqual([x["categoryId"] for x in changed["output"]["defaultTabList"]], [2])
        self.assertEqual((changed["parseCount"], changed["stringifyCount"]), (1, 1))

        clean = self.run_script(
            "https://www.ximalaya.com/discovery-category/customCategories",
            {"customCategoryList": [{"itemType": "recommend", "categoryId": 1}]}
        )
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)

    def test_category_focus_images_keep_only_open_non_ads(self):
        body = {"focusImages": {"data": [
            {"realLink": "app://open/topic", "isAd": False},
            {"realLink": "app://open/ad", "isAd": True},
            {"realLink": "app://web/topic", "isAd": False}
        ]}}
        result = self.run_script("https://www.ximalaya.com/discovery-category/v3/category", body)
        self.assertEqual(result["output"]["focusImages"]["data"], [{"realLink": "app://open/topic", "isAd": False}])
        self.assertEqual(result["stringifyCount"], 1)

    def test_focus_pic_header_array_is_compacted(self):
        body = {"header": [{"item": {"list": [{"data": [
            {"realLink": "app://open/album", "isAd": False},
            {"realLink": "app://ad", "isAd": True}
        ]}]}}]}
        result = self.run_script("https://www.ximalaya.com/focus-mobile/focusPic", body)
        self.assertEqual(result["output"]["header"][0]["item"]["list"][0]["data"], [{"realLink": "app://open/album", "isAd": False}])
        self.assertEqual(result["stringifyCount"], 1)

    def test_discovery_feed_deletes_top_header_and_compacts_ads(self):
        body = {
            "header": [{"name": "campaign"}, {"name": "recommendations"}],
            "body": [
                {"item": {"title": "normal"}, "displayClass": "normal"},
                {"item": {"adInfo": {"id": 1}}},
                {"item": {"moduleType": "mix_ad"}},
                {"displayClass": "bigCard"},
                {"item": {"title": "keep"}}
            ]
        }
        result = self.run_script("https://www.ximalaya.com/discovery-feed/v1/mix", body)
        self.assertEqual(result["output"]["header"], [None, {"name": "recommendations"}])
        self.assertEqual(result["output"]["body"], [
            {"item": {"title": "normal"}, "displayClass": "normal"},
            {"item": {"title": "keep"}}
        ])
        self.assertEqual(result["stringifyCount"], 1)

    def test_home_page_entrances_are_compacted_and_clean_payload_skips_stringify(self):
        body = {"data": {"serviceModule": {"entrances": [
            {"id": 210}, {"id": 211}, {"id": 213}, {"id": 215}
        ]}}}
        result = self.run_script("https://www.ximalaya.com/mobile-user/v1/homePage", body)
        self.assertEqual([x["id"] for x in result["output"]["data"]["serviceModule"]["entrances"]], [210, 213, 215])
        self.assertEqual(result["stringifyCount"], 1)
        clean = self.run_script(
            "https://www.ximalaya.com/mobile-user/v1/homePage",
            {"data": {"serviceModule": {"entrances": [{"id": 210}, {"id": 213}]}}}
        )
        self.assertEqual(clean["done"], {})
        self.assertEqual(clean["stringifyCount"], 0)

    def test_empty_unknown_and_invalid_responses_skip_unnecessary_work(self):
        empty = self.run_script("https://www.ximalaya.com/discovery-category/customCategories", None)
        self.assertEqual(empty["done"], {})
        self.assertEqual((empty["parseCount"], empty["stringifyCount"]), (0, 0))

        unknown = self.run_script("https://www.ximalaya.com/unrelated/large-feed", {"data": [{"unused": "x"}]})
        self.assertEqual(unknown["done"], {})
        self.assertEqual((unknown["parseCount"], unknown["stringifyCount"]), (0, 0))

        invalid = self.run_script("https://www.ximalaya.com/discovery-category/customCategories", "{bad json")
        self.assertEqual(invalid["done"], {})
        self.assertEqual(invalid["parseCount"], 1)
        self.assertEqual(invalid["stringifyCount"], 0)


if __name__ == "__main__":
    unittest.main()
