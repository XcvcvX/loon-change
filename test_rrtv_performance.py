import json
import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_rrtv import EXPECTED_TRIGGERS, LOCAL, MARKER, REMOTE, optimize_source, rewrite_plugin

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "scripts" / "rrtv" / "rrtv.js"
NODE = shutil.which("node")


class RRTVOptimizerTests(unittest.TestCase):
    def test_snapshot_is_idempotent_and_framework_is_removed(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        self.assertEqual(optimize_source(source), source)
        self.assertNotIn("function MagicJS(", source)
        self.assertNotIn("$persistentStore", source)
        self.assertNotIn("$httpClient", source)
        self.assertIn("function createLoonRuntime(name)", source)
        self.assertLess(len(source), 18000)

    def test_nine_triggers_migrate_and_fail_closed(self):
        fixture = "[Script]\n" + "\n".join(
            "http-response ^https://api.rr.tv/%d script-path=%s" % (i, REMOTE)
            for i in range(EXPECTED_TRIGGERS)
        )
        migrated = rewrite_plugin(fixture)
        self.assertEqual(migrated.count(LOCAL), EXPECTED_TRIGGERS)
        self.assertEqual(rewrite_plugin(migrated), migrated)
        with self.assertRaisesRegex(ValueError, "expected 9"):
            rewrite_plugin(fixture.rsplit("\n", 1)[0])
        mixed = fixture + "\nhttp-response ^https://api.rr.tv/local script-path=" + LOCAL
        with self.assertRaisesRegex(ValueError, "mixed local and remote"):
            rewrite_plugin(mixed)


@unittest.skipUnless(NODE, "Node.js is required for RRTV runtime tests")
class RRTVRuntimeTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const parse = JSON.parse.bind(JSON), stringify = JSON.stringify.bind(JSON);
const replace = String.prototype.replace;
let doneValue, doneCount = 0;
const c = {
  $request: {url: input.url},
  $response: {body: input.body === null ? "" : input.body},
  $done(v) {doneValue = v === undefined ? null : v; doneCount++;},
  parseCount: 0, stringifyCount: 0, replaceCount: 0,
  parse, stringify, replace,
  console: {log() {}, warn() {}, error() {}}
};
vm.createContext(c);
vm.runInContext(
  "JSON.parse=function(v){parseCount++;return parse(v)};" +
  "JSON.stringify=function(v){stringifyCount++;return stringify(v)};" +
  "String.prototype.replace=function(...a){replaceCount++;return replace.apply(this,a)};",
  c
);
vm.runInContext(source, c, {timeout:5000});
if (doneCount !== 1) throw new Error("expected one $done, got " + doneCount);
const output = doneValue && typeof doneValue.body === "string" ? parse(doneValue.body) : null;
process.stdout.write(stringify({done:doneValue,output,parseCount:c.parseCount,stringifyCount:c.stringifyCount,replaceCount:c.replaceCount}));
"""
        result = subprocess.run(
            [NODE, "-e", runner, str(SOURCE)],
            input=json.dumps({"url": url, "body": body}, ensure_ascii=False),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(result.stdout)

    def test_empty_body_stops_before_json_parse(self):
        r = self.run_script("https://api.rr.tv/level/info", None)
        self.assertEqual(r["done"], {})
        self.assertEqual(r["parseCount"], 0)
        self.assertEqual(r["stringifyCount"], 0)

    def test_homepage_ads_are_compacted_and_clean_homepage_skips_stringify(self):
        payload = {"data":{"sections":[
            {"sectionType":"NORMAL","id":1},{"sectionType":"AD","id":2},
            {"sectionType":"SINGLE_IMAGE","id":3},{"sectionType":"SHORT_VIDEO","id":4},
            {"sectionType":"NORMAL","id":5}]}}
        url = "https://api.rr.tv/v3plus/index/channel?pageNum=1&position=CHANNEL_INDEX"
        changed = self.run_script(url, json.dumps(payload))
        self.assertEqual([x["id"] for x in changed["output"]["data"]["sections"]], [1,5])
        self.assertEqual(changed["stringifyCount"], 1)
        clean = self.run_script(url, json.dumps({"data":{"sections":[{"sectionType":"NORMAL"}]}}))
        self.assertIsNone(clean["done"])
        self.assertEqual(clean["stringifyCount"], 0)

    def test_ad_getall_skips_already_empty_ad_list(self):
        changed = self.run_script("https://api.rr.tv/ad/getAll", json.dumps({"data":{"adList":[1]}}))
        self.assertEqual(changed["output"]["data"]["adList"], [])
        clean = self.run_script("https://api.rr.tv/ad/getAll", json.dumps({"data":{"adList":[]}}))
        self.assertIsNone(clean["done"])
        self.assertEqual(clean["stringifyCount"], 0)

    def test_video_flags_are_rewritten_with_one_string_scan(self):
        body = '{"currentQuality":"SD","canPlay":false,"canShowVip":true,"externalAds":true}'
        r = self.run_script("https://api.rr.tv/drama/detail?id=1", body)
        self.assertIn('"currentQuality":"AI_OD"', r["done"]["body"])
        self.assertIn('"canPlay":true', r["done"]["body"])
        self.assertIn('"canShowVip":false', r["done"]["body"])
        self.assertIn('"externalAds":false', r["done"]["body"])
        self.assertEqual(r["replaceCount"], 1)
        self.assertEqual(r["parseCount"], 0)
        self.assertEqual(r["stringifyCount"], 0)

    def test_clean_video_response_returns_without_new_body(self):
        body = '{"currentQuality":"AI_OD","canPlay":true,"canShowVip":false,"externalAds":false}'
        r = self.run_script("https://api.rr.tv/watch/v4?id=1", body)
        self.assertIsNone(r["done"])
        self.assertEqual(r["replaceCount"], 1)

    def test_config_and_level_routes_preserve_expected_fields(self):
        cfg = self.run_script("https://api.rr.tv/app/config/h5NativeBar", json.dumps({"data":{"homeBarPage":[]}}))
        self.assertEqual([x["name"] for x in cfg["output"]["data"]["homeBarPage"]], ["首页","快看","VIP","我的"])
        level = self.run_script("https://api.rr.tv/level/info", json.dumps({"data":{"level":"0","valid":False}}))
        self.assertEqual(level["output"]["data"], {"level":"1","expiredTime":4000000000000,"valid":True})

    def test_user_personal_and_unmatched_routes_keep_prior_behavior(self):
        user = self.run_script("https://api.rr.tv/user/personal", json.dumps({"data":{"user":{}}}))
        self.assertEqual(user["output"]["data"]["user"]["vipInfo"]["level"], "1")
        self.assertEqual(len(user["output"]["data"]["user"]["privilegeList"]), 10)
        unmatched = self.run_script("https://api.rr.tv/unmatched", '{"ok":true}')
        self.assertIsNone(unmatched["done"])
        self.assertEqual(unmatched["parseCount"], 0)


if __name__ == "__main__":
    unittest.main()
