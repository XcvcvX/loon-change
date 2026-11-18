import shutil
import subprocess
import unittest
from pathlib import Path

from optimize_cnftp import LOCAL_URL, REMOTE_URL, SOURCE_MARKER, optimize_source, rewrite_plugin

ROOT = Path(__file__).parent
SOURCE_PATH = ROOT / "scripts" / "cnftp" / "cnftp.js"


class CnftpPerformanceTests(unittest.TestCase):
    def test_optimized_source_is_idempotent_and_uses_stable_compaction(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_MARKER, source)
        self.assertEqual(optimize_source(source), source)
        start = source.index('  } else if (url.includes("columbus.home.query/")) {')
        end = source.index('  } else if (url.includes("columbus.uc.query/")) {', start)
        branch = source[start:end]
        self.assertIn("compactInPlace(objData.nodes", branch)
        self.assertNotIn("newNodes1", branch)
        self.assertNotIn("newNode2", branch)
        self.assertNotIn("newNode3", branch)
        self.assertNotIn("newNode4", branch)
        self.assertNotIn('console.log("移除首页的轮播广告")', branch)

    def test_rewrites_exact_cnftp_trigger_inventory_and_is_idempotent(self):
        fixture = "[Script]\n" + "\n".join(
            'response if ${url} ~= /^https:\\/\\/example\\.com\\/%d/ then script("%s") with requires_body=true' % (i, REMOTE_URL)
            for i in range(10)
        ) + "\n[MITM]\nhostname = example.com\n"
        result = rewrite_plugin(fixture)
        self.assertEqual(result.count(LOCAL_URL), 10)
        self.assertNotIn(REMOTE_URL, result)
        self.assertEqual(rewrite_plugin(result), result)

    def test_preserves_base_only_plugin_when_cnftp_handler_is_absent(self):
        fixture = "[Script]\nhttp-response ^https?:\\\\/\\\\/example\\\\.com script-path=https://example.invalid/keep.js\n[MITM]\nhostname = example.com\n"
        self.assertEqual(rewrite_plugin(fixture), fixture)

    def test_fails_closed_when_cnftp_trigger_count_drifts(self):
        fixture = "[Script]\n" + 'response if ${url} ~= /^https:\\/\\/example/ then script("%s")' % REMOTE_URL + "\n[MITM]\n"
        with self.assertRaisesRegex(ValueError, "trigger inventory changed"):
            rewrite_plugin(fixture)

    def test_node_runtime_preserves_nested_youku_home_query_results(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for CNFTP runtime tests")
        harness = r'''
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const data = {
  data: {
    "2019061000": {
      data: {
        data: { indexPositionResult: [{id: 1}] },
        nodes: [
          { data: { nodeKey: "CHILD" }, nodes: [{id: 999}] },
          {
            data: { nodeKey: "KEEP", indexPositionResult: [{id: 2}], refreshImg: "bg" },
            nodes: [
              { typeName: "UC广告抽屉", data: { crmSale: true } },
              {
                id: 31476,
                typeName: "NORMAL",
                data: { crmSale: true, keywords: ["hot"] },
                nodes: [
                  { typeName: "PHONE_FEED_CARD_B_AD", id: 1, nodes: [] },
                  {
                    typeName: "KEEP",
                    id: 2,
                    nodes: [
                      { typeName: "PHONE_FEED_CARD_S_AD", data: {} },
                      { typeName: "KEEP", data: {} },
                      { typeName: "KEEP", data: { ad: true } }
                    ]
                  },
                  { typeName: "KEEP", id: 272768, nodes: [] }
                ]
              },
              { id: 35505, data: {} },
              { id: 37335, data: {} },
              { id: 50000, nodes: [{id: 272768}, {id: 3, data: {}}] }
            ]
          }
        ]
      }
    }
  }
};
let parseCalls = 0, stringifyCalls = 0, doneResult;
const trackedJSON = {
  parse(...args) { parseCalls++; return JSON.parse(...args); },
  stringify(...args) { stringifyCalls++; return JSON.stringify(...args); }
};
vm.runInNewContext(source, {
  JSON: trackedJSON,
  $request: { url: "https://acs.youku.com/gw/mtop.youku.columbus.home.query/" },
  $response: { body: JSON.stringify(data) },
  $done(value) { doneResult = value; },
  console: { log() { throw new Error("home.query should not emit logs"); } }
});
if (parseCalls !== 1 || stringifyCalls !== 1) throw new Error("JSON parse/stringify count changed: " + parseCalls + "/" + stringifyCalls);
if (!doneResult || typeof doneResult.body !== "string") throw new Error("response body missing");
const output = JSON.parse(doneResult.body);
const root = output.data["2019061000"].data;
if (root.nodes.length !== 1 || root.nodes[0].data.nodeKey !== "KEEP") throw new Error("root nodes not filtered in stable order");
if (root.data.indexPositionResult.length !== 0) throw new Error("home indexPositionResult not cleared");
const node1 = root.nodes[0];
if (node1.data.indexPositionResult.length !== 0 || "refreshImg" in node1.data) throw new Error("node1 fields not cleaned");
if (node1.nodes.length !== 2 || node1.nodes[0].id !== 31476 || node1.nodes[1].id !== 50000) throw new Error("node2 compaction/order mismatch");
const node2 = node1.nodes[0];
if ("crmSale" in node2.data || "keywords" in node2.data) throw new Error("node2 promo fields not removed");
if (node2.nodes.length !== 1 || node2.nodes[0].id !== 2) throw new Error("node3 compaction/order mismatch");
if (node2.nodes[0].nodes.length !== 1 || node2.nodes[0].nodes[0].data.ad) throw new Error("node4 compaction mismatch");
if (node1.nodes[1].nodes.length !== 1 || node1.nodes[1].nodes[0].id !== 3) throw new Error("node3 id filter mismatch");
'''
        result = subprocess.run(
            [node, "-e", harness, str(SOURCE_PATH)],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
