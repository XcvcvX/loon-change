import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for response runtime tests")
class XianyuZhihuRouteGuardTests(unittest.TestCase):
    def run_script(self, relative_path, url, body):
        script = ROOT / relative_path
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const body = JSON.parse(process.argv[2]);
let result, parseCalls = 0, stringifyCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: process.argv[3] },
  $response: { body: nativeJSON.stringify(body) },
  $done(value) { result = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.runInNewContext(source, context, { timeout: 5000 });
process.stdout.write(nativeJSON.stringify({ result, parseCalls, stringifyCalls }));
"""
        completed = subprocess.run(
            [NODE, "-e", harness, str(script), __import__("json").dumps(body), url],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=10
        )
        return __import__("json").loads(completed.stdout)

    def test_xianyu_unknown_route_skips_parse_and_stringify(self):
        result = self.run_script(
            "scripts/xianyu/goofish.js",
            "https://acs.m.goofish.com/gw/mtop.taobao.idle.unknown/1.0/",
            {"data": {"large": "x" * 20000}}
        )
        self.assertEqual(result["result"], {})
        self.assertEqual(result["parseCalls"], 0)
        self.assertEqual(result["stringifyCalls"], 0)

    def test_xianyu_supported_route_keeps_existing_cleanup(self):
        result = self.run_script(
            "scripts/xianyu/goofish.js",
            "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/",
            {"data": {"widgetReturnDO": {"ad": 1}, "sections": [{"data": {"cardTypeValue": "Item", "id": "organic"}}], "homeTopList": []}}
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertNotIn("widgetReturnDO", __import__("json").loads(result["result"]["body"])["data"])

    def test_zhihu_unknown_route_skips_parse_and_stringify(self):
        result = self.run_script(
            "scripts/zhihu/zhihu.js",
            "https://api.zhihu.com/unhandled/large-feed",
            {"data": [{"payload": "x" * 20000}]}
        )
        self.assertEqual(result["result"], {})
        self.assertEqual(result["parseCalls"], 0)
        self.assertEqual(result["stringifyCalls"], 0)

    def test_zhihu_supported_route_keeps_existing_cleanup(self):
        result = self.run_script(
            "scripts/zhihu/zhihu.js",
            "https://api.zhihu.com/topstory/hot-lists/total",
            {"data": [{"id": 1, "ad": {}}, {"id": 2}]}
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        self.assertEqual(__import__("json").loads(result["result"]["body"])["data"], [{"id": 2}])
