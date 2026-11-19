import json
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parent / "scripts" / "taobao" / "taobao.js"
from optimize_taobao import KELEE_PATH, LOCAL, rewrite_plugin

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "allAdRewrite.plugin"


def fixture(guide=True, poplayer=True, extra=False):
    lines = [
        "[Script]",
        "http-response guide-acs cloudvideo splash script-path=" + LOCAL + ",tag=TAOBAO,requires-body=true",
        "http-response poplayer script-path=" + LOCAL + ",tag=TAOBAO-2,requires-body=true",
    ]
    base = "https://raw.githubusercontent.com/ifflagged/Romeo/abc123" + KELEE_PATH
    if guide:
        lines.append(f'response if ${{url}} ~= /^guide-acs.*cloudvideo.*splash/ then script("{base}") with tag="Taobao", requires_body=true')
    if poplayer:
        lines.append(f'response if ${{url}} ~= /^poplayer/ then script("{base}") with tag="Taobao", requires_body=true')
    if extra:
        lines.append(f'response if ${{url}} ~= /^unexpected/ then script("{base}") with tag="Other", requires_body=true')
    lines.extend([
        'response if ${url} ~= /mdkd/ then script("https://example.invalid/pdd.js") with tag="PDD", requires_body=true',
        "[MITM]",
        "hostname = guide-acs.m.taobao.com,poplayer.template.alibaba.com",
    ])
    return "\n".join(lines) + "\n"


class TaobaoDeduplicationTests(unittest.TestCase):
    def test_exact_duplicate_handlers_are_removed_and_local_triggers_remain(self):
        result = rewrite_plugin(fixture())
        self.assertEqual(result.count(LOCAL), 2)
        self.assertNotIn(KELEE_PATH, result)
        self.assertIn("mdkd", result)
        self.assertIn("[MITM]", result)
        self.assertEqual(rewrite_plugin(result), result)

    def test_repository_snapshot_contains_only_local_optimized_handlers_after_cleanup(self):
        result = rewrite_plugin(PLUGIN.read_text(encoding="utf-8"))
        self.assertNotIn(KELEE_PATH, result)
        self.assertEqual(result.count(LOCAL), 2)
        self.assertEqual(rewrite_plugin(result), result)

    def test_missing_local_coverage_fails_closed(self):
        broken = fixture().replace(LOCAL, "https://example.invalid/taobao.js", 1)
        with self.assertRaisesRegex(ValueError, "Local optimized Taobao trigger inventory changed"):
            rewrite_plugin(broken)

    def test_partial_or_unknown_kelee_inventory_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "trigger inventory changed"):
            rewrite_plugin(fixture(poplayer=False))
        with self.assertRaisesRegex(ValueError, "Unrecognized Taobao Kelee URL matcher"):
            rewrite_plugin(fixture(extra=True))

    def test_no_duplicate_handlers_is_a_noop(self):
        original = fixture(guide=False, poplayer=False)
        self.assertEqual(rewrite_plugin(original), original)


@unittest.skipUnless(NODE, "Node.js is required for Taobao response runtime tests")
class TaobaoLazySerializationTests(unittest.TestCase):
    def run_script(self, url, body):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(process.argv[1], "utf8");
let doneResult;
const context = {
  $request: { url: payload.url },
  $response: { body: JSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  __stringifyCount: 0
};
vm.createContext(context);
vm.runInContext(
  "const native = JSON.stringify.bind(JSON); JSON.stringify = function(value) { __stringifyCount++; return native(value); };",
  context
);
vm.runInContext(source, context, { timeout: 5000 });
const result = { stringifyCount: context.__stringifyCount, passThrough: !doneResult || typeof doneResult.body !== "string" };
if (!result.passThrough) result.output = JSON.parse(doneResult.body);
process.stdout.write(JSON.stringify(result));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({"url": url, "body": body}),
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_already_normalized_splash_skips_serialization(self):
        item = {
            "waitTime": "0", "times": "0", "hotStart": "false", "haveVoice": "false",
            "hideTBLogo": "false", "enable4G": "false", "coldStart": "false",
            "startTime": "3818332800000", "endTime": "3818419199000",
            "gmtStart": "2090-12-31 00:00:00", "gmtEnd": "2090-12-31 23:59:59",
            "gmtStartMs": "3818332800000", "gmtEndMs": "3818419199000",
            "imgUrl": "", "videoUrl": "",
        }
        body = {"data": {"containers": {"splash_home_base": {
            "base": {"sections": [{"bizData": {"taobao-splash": {"data": [item]}}}]}
        }}}}
        result = self.run_script("https://guide-acs.m.taobao.com/mtop.taobao.wireless.home.splash.awesome.get", body)
        self.assertTrue(result["passThrough"])
        self.assertEqual(result["stringifyCount"], 0)

    def test_poplayer_main_images_are_cleared_and_serialized_once(self):
        body = {"res": {"images": []}, "mainRes": {"images": ["ad.png"]}, "enable": True}
        result = self.run_script("https://poplayer.template.alibaba.com/mtop", body)
        self.assertFalse(result["passThrough"])
        self.assertEqual(result["stringifyCount"], 1)
        self.assertEqual(result["output"]["mainRes"]["images"], [])
        self.assertFalse(result["output"]["enable"])

    def test_already_clean_poplayer_skips_serialization(self):
        body = {"res": {"images": [], "videos": []}, "mainRes": {"images": []}, "enable": False}
        result = self.run_script("https://poplayer.template.alibaba.com/mtop", body)
        self.assertTrue(result["passThrough"])
        self.assertEqual(result["stringifyCount"], 0)


if __name__ == "__main__":
    unittest.main()
