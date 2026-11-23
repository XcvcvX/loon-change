import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for response runtime tests")
class ResponseArrayCompactionTests(unittest.TestCase):
    def run_script(self, relative_path, url, body, argument=None):
        source = ROOT / relative_path
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult;
const context = {
  $request: { url: payload.url, headers: {} },
  $response: { body: JSON.stringify(payload.body) },
  $argument: payload.argument,
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(
  "const nativeParse = JSON.parse.bind(JSON); let parseCount = 0, stringifyCount = 0; JSON.parse = function(value) { parseCount++; return nativeParse(value); }; const nativeStringify = JSON.stringify.bind(JSON); JSON.stringify = function(value) { stringifyCount++; return nativeStringify(value); }; Array.prototype.filter = function() { throw new Error('allocating Array.filter remains'); }; Array.prototype.map = function() { throw new Error('allocating Array.map remains'); }; globalThis.__parseCount = () => parseCount; globalThis.__stringifyCount = () => stringifyCount;",
  context
);
vm.runInContext(source, context, { timeout: 5000 });
const passThrough = !doneResult || typeof doneResult.body !== "string";
const output = passThrough ? null : JSON.parse(doneResult.body);
process.stdout.write(JSON.stringify({ output, passThrough, parseCount: context.__parseCount(), stringifyCount: context.__stringifyCount() }));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(source)],
            input=json.dumps({"url": url, "body": body, "argument": argument}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def assert_single_parse(self, result):
        self.assertEqual(result["parseCount"], 1)

    def test_goofish_feed_compacts_in_place_and_preserves_kept_order(self):
        body = {"data": {"sections": [
            {"data": {"cardTypeValue": "Item", "bizType": "normal"}, "id": "a"},
            {"data": {"cardTypeValue": "Item", "bizType": "AD"}, "id": "ad"},
            {"data": {"cardTypeValue": "Item", "bizType": "normal"}, "id": "b"},
            {"data": {"cardTypeValue": "Other", "bizType": "normal"}, "id": "other"},
        ]}}
        result = self.run_script(
            "scripts/xianyu/goofish.js",
            "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/",
            body,
        )
        self.assert_single_parse(result)
        self.assertEqual([x["id"] for x in result["output"]["data"]["sections"]], ["a", "b"])
        self.assertEqual(result["output"]["data"]["homeTopList"], [])

    def test_meituan_mine_compacts_without_array_filter(self):
        body = {"children": [
            {"name": "mine_cross_recommend"},
            {"name": "orders"},
            {"name": "settings"},
        ]}
        result = self.run_script(
            "scripts/meituan/meituan.js",
            "https://mt-personalcenter.meituan.com/usercenter/display",
            body,
        )
        self.assert_single_parse(result)
        self.assertEqual([x["name"] for x in result["output"]["children"]], ["orders", "settings"])

    def test_jd_welcome_home_uses_one_compaction_pass(self):
        body = {
            "floorList": [
                {"type": "topTab"}, {"type": "float"}, {"type": "recommend"},
                {"type": "unknown"}, {"type": "login"}
            ],
            "webViewFloorList": [{"type": "web"}],
            "promotionTabs": [{"id": 1}],
        }
        result = self.run_script(
            "scripts/jingdong/jd.js",
            "https://api.m.jd.com/client.action?functionId=welcomeHome",
            body,
        )
        self.assert_single_parse(result)
        self.assertEqual(
            [x["type"] for x in result["output"]["floorList"]],
            ["topTab", "recommend", "login"],
        )
        self.assertEqual(result["output"]["webViewFloorList"], [])
        self.assertNotIn("promotionTabs", result["output"])

    def test_pdd_homepage_uses_native_jq_in_aggregate_plugin(self):
        from apply_local_overrides import PDD_HOMEPAGE_NATIVE_JQ_RULE
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        matching = [
            line for line in plugin.splitlines()
            if "api.pinduoduo.com/api/alexa/homepage/hub" in line
            and "response.json.jq(" in line
        ]
        self.assertEqual(matching, [PDD_HOMEPAGE_NATIVE_JQ_RULE])
        self.assertNotIn("pdd-homepage.js", plugin)

    def test_meituan_linglong_image_scans_headers_without_key_array(self):
        source = ROOT / "scripts" / "meituan" / "meituan.js"
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let result;
const headers = Object.create(payload.inherited ? { ai: "inherited" } : null);
Object.assign(headers, payload.headers || {});
const context = {
  $request: { url: "https://p1.meituan.net/linglong/test.jpg", headers },
  $response: {},
  $done(value) { result = value; },
  console: { log() {} }
};
vm.createContext(context);
vm.runInContext(
  "Object.keys = function() { throw new Error('Object.keys allocated on Meituan image hot path'); };",
  context
);
vm.runInContext(source, context, { timeout: 5000 });
process.stdout.write(JSON.stringify(result || {}));
"""
        def run(headers=None, inherited=False):
            completed = subprocess.run(
                [NODE, "-e", runner, str(source)],
                input=json.dumps({"headers": headers or {}, "inherited": inherited}),
                capture_output=True, text=True, check=True, timeout=10,
            )
            return json.loads(completed.stdout)

        blocked = run({"Ai": "trace"})
        self.assertEqual(blocked.get("status"), "HTTP/1.1 204 No Content")
        self.assertEqual(blocked.get("body"), "")
        self.assertEqual(blocked.get("headers"), "")

        unmarked = run({"User-Agent": "Meituan"})
        self.assertEqual(unmarked, {})

        inherited = run({}, inherited=True)
        self.assertEqual(inherited, {})


if __name__ == "__main__":
    unittest.main()
