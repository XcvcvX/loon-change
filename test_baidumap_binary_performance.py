import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE = shutil.which("node")


class BaiduMapBinaryPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")

    def test_response_assembly_uses_one_payload_allocation_and_hashes_a_view(self):
        start = self.source.index("function assembleBaiduResponse(")
        end = self.source.index("\n}\n", start) + 2
        helper = self.source[start:end]

        self.assertIn('new Uint8Array(payloadOffset + payloadLength)', helper)
        self.assertIn("hash(body.subarray(payloadOffset))", helper)
        self.assertNotIn("mergeResultAndAds", helper)
        self.assertIn("encodedHeader.byteLength !== headerLength", helper)

    def test_binary_input_reuses_existing_uint8array(self):
        self.assertIn("const binaryBody = responseBytes instanceof Uint8Array", self.source)
        self.assertNotIn("new Uint8Array($response.bodyBytes)", self.source)
        self.assertIn("$done({bodyBytes: body.buffer})", self.source)
        self.assertNotIn("body.buffer.slice(", self.source)

    @unittest.skipUnless(NODE, "Node.js is required for binary assembly regression tests")
    def test_actual_assembly_helper_preserves_payload_and_header_metadata(self):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const crypto = require("crypto");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("function assembleBaiduResponse(");
if (start < 0) throw new Error("assembly helper not found");
const end = source.indexOf("\n}\n", start) + 2;
if (end < 2) throw new Error("assembly helper end not found");
const context = {
  Uint8Array,
  DataView,
  TextEncoder,
  md5(bytes) {
    return crypto.createHash("md5").update(Buffer.from(bytes)).digest("hex");
  },
  repHeadType: {
    encode(value) {
      return { finish() { return new TextEncoder().encode(JSON.stringify(value)); } };
    }
  }
};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + "; globalThis.run = assembleBaiduResponse;", context);
const result = new Uint8Array([1, 2, 3, 4]);
const ads = new Uint8Array([9, 8, 7]);
const header = {
  md5: "",
  messageHead: [
    { name: "Result", offset: 0, length: 0 },
    { name: "Ads", offset: 0, length: 0 }
  ]
};
const body = context.run(header, context.repHeadType, result, ads, context.md5);
const headerLength = new DataView(body.buffer, body.byteOffset, 4).getInt32(0);
const decodedHeader = JSON.parse(new TextDecoder().decode(body.subarray(4, 4 + headerLength)));
const payloadOffset = 4 + headerLength;
const payload = body.subarray(payloadOffset);
const expectedPayload = Buffer.concat([Buffer.from(result), Buffer.from(ads)]);
if (!Buffer.from(payload).equals(expectedPayload)) throw new Error("payload bytes/order changed");
const expectedHash = crypto.createHash("md5").update(expectedPayload).digest("hex");
if (decodedHeader.md5 !== expectedHash) throw new Error("MD5 mismatch");
if (decodedHeader.messageHead[0].length !== result.length) throw new Error("Result length mismatch");
if (decodedHeader.messageHead[1].offset !== result.length) throw new Error("Ads offset mismatch");
if (decodedHeader.messageHead[1].length !== ads.length) throw new Error("Ads length mismatch");
process.stdout.write("ok");
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(ROOT / "scripts/baidumap/baidu-map-protobuf.js")],
            capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertEqual(completed.stdout, "ok")


class ResponseScriptAuditTests(unittest.TestCase):
    def test_taobao_handler_has_one_parse_and_no_allocating_array_transform(self):
        source = (ROOT / "scripts/taobao/taobao.js").read_text(encoding="utf-8")
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)

    def test_didi_local_script_is_not_the_active_plugin_target(self):
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        source = (ROOT / "scripts/didi/didi-ads.js").read_text(encoding="utf-8")
        self.assertIn("script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js", plugin)
        self.assertNotIn("scripts/didi/didi-ads.js", plugin)
        self.assertIn("function filterInPlace", source)


if __name__ == "__main__":
    unittest.main()
