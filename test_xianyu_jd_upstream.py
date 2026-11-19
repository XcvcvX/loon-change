import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class TargetedUpstreamAppRuleTests(unittest.TestCase):
    def test_merge_pipeline_keeps_only_targeted_local_xianyu_and_jd_additions(self):
        base_text = r"""#!name=fixture
[Rewrite]
^https?:\/\/m.360buyimg\.com\/mobilecms\/s1125x2436_jfs\/ reject-200
request if ${url} ~= /^https?:\/\/acs\.m\.goofish\.com\/gw\/mtop\.taobao\.idlecommerce\.splash\.ads\// then reject_dict(200)
[Script]
[Rule]
[MITM]
hostname = m.360buyimg.com, img*.360buyimg.com, acs.m.goofish.com, g-acs.m.goofish.com
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.plugin"
            output = root / "merged.plugin"
            provenance = root / "provenance.json"
            base.write_text(base_text, encoding="utf-8")
            command = [
                sys.executable, str(ROOT / "merge_plugins.py"),
                "--base", str(base),
                "--extra", "none",
                "--filter", "none",
                "--myblockads", "none",
                "--alipayadblock", "none",
                "--out", str(output),
                "--provenance-out", str(provenance),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + "\n" + completed.stderr)
            merged = output.read_text(encoding="utf-8")
            self.assertIn("GOOFISH-SPLASH", merged)
            self.assertIn("realTimeAd", (ROOT / "scripts/xianyu/goofish.js").read_text(encoding="utf-8"))
            self.assertIn(r"s1\d{3}x2\d{3}_jfs", merged)
            self.assertIn("material-video", merged)
            self.assertNotIn(r"idlecommerce\.splash", merged)
            self.assertNotIn("s1125x2436_jfs", merged)
            self.assertIn("xianyu_jd_targeted", provenance.read_text(encoding="utf-8"))

    def test_xianyu_script_removes_real_time_splash_node_without_parsing_empty_splash(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for the Xianyu runtime test")
        source_path = ROOT / "scripts" / "xianyu" / "goofish.js"
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
function run(url, body) {
  let result, parseCalls = 0, stringifyCalls = 0;
  const trackedJSON = {
    parse(...args) { parseCalls++; return JSON.parse(...args); },
    stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
  };
  vm.runInNewContext(source, {
    JSON: trackedJSON,
    $request: { url },
    $response: { body },
    $done(value) { result = value; },
    console: { log() {} }
  });
  return { result, parseCalls, stringifyCalls };
}
const splashUrl = "https://acs.m.goofish.com/gw/mtop.taobao.idlecommerce.splash.ads/1.0/";
const noAd = run(splashUrl, '{"data":{"other":1}}');
if (noAd.parseCalls !== 0 || noAd.stringifyCalls !== 0) throw new Error("empty splash fast path parsed JSON");
const ad = run(splashUrl, JSON.stringify({
  data: { realTimeAd: { mamaAd: { imageMaterial: { showNow: "true" } } }, keep: 1 }
}));
if (ad.parseCalls !== 1 || ad.stringifyCalls !== 1) throw new Error("splash should parse/stringify once");
const parsed = JSON.parse(ad.result.body);
if ("realTimeAd" in parsed.data || parsed.data.keep !== 1) throw new Error("realTimeAd removal changed unrelated data");
const feedUrl = "https://acs.m.goofish.com/gw/mtop.taobao.idlehome.home.nextfresh/1.0/";
const feed = run(feedUrl, JSON.stringify({ data: { sections: [
  { template: { name: "fish_home_advertise_card_d3" }, data: { cardTypeValue: "Item" } },
  { data: { cardType: "mamaAD", cardTypeValue: "Item" } },
  { data: { cardType: "homeMultiBanner", cardTypeValue: "Item" } },
  { data: { cardTypeValue: "Item", id: "organic" } }
] } }));
const sections = JSON.parse(feed.result.body).data.sections;
if (sections.length !== 1 || sections[0].data.id !== "organic") throw new Error("new Xianyu ad-card markers were not filtered");
if (feed.parseCalls !== 1 || feed.stringifyCalls !== 1) throw new Error("feed handler must retain one JSON round trip");
'''
        completed = subprocess.run(
            [node, "-e", harness, str(source_path)],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
