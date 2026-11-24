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
        self.assertIn("// loon-change: Baidu protobuf single-encode MD5 header patch v1", helper)
        self.assertIn("const encodedHeader = repHeadType.encode(repHeadMessage).finish();", helper)
        self.assertIn("encodedHeader[digestOffset + i] = digest.charCodeAt(i);", helper)
        self.assertNotIn("encodedHeader.byteLength !== headerLength", helper)
        self.assertEqual(helper.count("repHeadType.encode(repHeadMessage).finish()"), 1)


    def test_only_result_and_ads_fields_create_binary_payload_views(self):
        marker = "// loon-change: Baidu protobuf target-only byte views v1"
        self.assertIn(marker, self.source)
        start = self.source.index("for(let i = 0; i < messageHeadLength; i++)")
        end = self.source.index("\n}\n\nif (modifiedAds && resultOffset !== -1)", start)
        loop = self.source[start:end]
        self.assertEqual(loop.count("binaryBody.subarray("), 1)
        self.assertIn("if(name === 'Result'){", loop)
        self.assertIn("resultOffset = dataBeginOffset + messageHead.offset;", loop)
        self.assertNotIn("newResult = binaryBody.subarray", loop)
        self.assertIn("}else if(name === 'Ads'){", loop)
        self.assertIn("const targetData = binaryBody.subarray(currentOffset, currentOffset + targetDataLength);", loop)
        self.assertNotIn("const targetData = binaryBody.subarray", loop.split("if(name === 'Result'){", 1)[0])
        deferred = self.source[end:self.source.index("\n\nif(!adsFound", end)]
        self.assertIn("if (modifiedAds && resultOffset !== -1)", deferred)
        self.assertIn("newResult = binaryBody.subarray(resultOffset, resultOffset + resultLength);", deferred)

    def test_rephead_message_head_collection_and_length_are_cached(self):
        marker = "// loon-change: Baidu protobuf header collection cache v1"
        self.assertIn(marker, self.source)
        start = self.source.index(marker)
        end = self.source.index("\n}\n\nif (modifiedAds && resultOffset !== -1)", start)
        loop = self.source[start:end]
        self.assertIn("const messageHeadEntries = repHeadMessage.messageHead;", loop)
        self.assertIn("const messageHeadLength = messageHeadEntries.length;", loop)
        self.assertIn("for(let i = 0; i < messageHeadLength; i++)", loop)
        self.assertIn("let messageHead = messageHeadEntries[i];", loop)
        self.assertNotIn("repHeadMessage.messageHead.length", loop)
        self.assertNotIn("repHeadMessage.messageHead[i]", loop)

    def test_response_assembly_caches_header_entries(self):
        start = self.source.index("function assembleBaiduResponse(")
        end = self.source.index("\n}\n", start) + 2
        helper = self.source[start:end]
        self.assertIn("const messageHead = repHeadMessage.messageHead;", helper)
        self.assertIn("const resultHead = messageHead[0];", helper)
        self.assertIn("const adsHead = messageHead[1];", helper)
        self.assertNotIn("repHeadMessage.messageHead[0]", helper)
        self.assertNotIn("repHeadMessage.messageHead[1]", helper)


    def test_ads_content_collection_and_length_are_cached(self):
        marker = "// loon-change: Baidu protobuf Ads content array cache v1"
        self.assertIn(marker, self.source)
        start = self.source.index(marker)
        end = self.source.index("if(modifiedAds) newAds = adsType.encode(adsMessage).finish();", start)
        loop = self.source[start:end]
        self.assertIn("const adsContent = adsMessage.content;", loop)
        self.assertIn("const adsContentLength = adsContent.length;", loop)
        self.assertIn("for(let j = 0; j < adsContentLength; j++)", loop)
        self.assertIn("const item = adsContent[j];", loop)
        self.assertIn("item.start !== 1648746061", loop)
        self.assertIn("item.end !== 1648832461", loop)
        self.assertNotIn("const start = item.start;", loop)
        self.assertNotIn("const end = item.end;", loop)
        self.assertNotIn("adsMessage.content.length", loop)
        self.assertNotIn("adsMessage.content[j]", loop)


    def test_result_payload_view_is_deferred_until_ads_change(self):
        marker = "// loon-change: Baidu protobuf target-only byte views v1"
        self.assertIn(marker, self.source)
        start = self.source.index("let newResult = null;")
        end = self.source.index("\n\nif(!adsFound", start)
        loop = self.source[start:end]
        self.assertIn("let resultOffset = -1;", loop)
        self.assertIn("resultOffset = dataBeginOffset + messageHead.offset;", loop)
        self.assertNotIn("newResult = binaryBody.subarray(currentOffset", loop)
        self.assertIn("if (modifiedAds && resultOffset !== -1)", loop)
        self.assertIn("newResult = binaryBody.subarray(resultOffset, resultOffset + resultLength);", loop)

    def test_binary_input_reuses_existing_uint8array(self):
        self.assertIn("const binaryBody = responseBytes instanceof Uint8Array", self.source)
        self.assertNotIn("new Uint8Array($response.bodyBytes)", self.source)
        self.assertIn("$done({bodyBytes: body.buffer})", self.source)
        self.assertNotIn("body.buffer.slice(", self.source)
        self.assertIn("function createBaiduMd5() {", self.source)
        self.assertIn("newAds, createBaiduMd5());", self.source)

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
let encodeCalls = 0;
const context = {
  Uint8Array,
  DataView,
  TextEncoder,
  md5(bytes) {
    return crypto.createHash("md5").update(Buffer.from(bytes)).digest("hex");
  },
  repHeadType: {
    encode(value) {
      encodeCalls++;
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
if (encodeCalls !== 1) throw new Error("RepHead must be encoded exactly once");
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


    def test_rephead_md5_placeholder_is_patched_without_reencoding(self):
        start = self.source.index("function assembleBaiduResponse(")
        end = self.source.index("\n}\n", start) + 2
        helper = self.source[start:end]
        self.assertEqual(helper.count("repHeadType.encode(repHeadMessage).finish()"), 1)
        self.assertIn("let digestOffset = -1;", helper)
        self.assertIn("encodedHeader[digestOffset + i] = digest.charCodeAt(i);", helper)
        self.assertIn('throw new Error("BaiduMap MD5 placeholder is ambiguous");', helper)

    def test_md5_placeholder_scan_uses_native_candidate_indexing(self):
        start = self.source.index("function assembleBaiduResponse(")
        end = self.source.index("\n}\n", start) + 2
        helper = self.source[start:end]
        self.assertIn("// loon-change: Baidu protobuf MD5 placeholder indexed scan v1", helper)
        self.assertIn("let candidateOffset = encodedHeader.indexOf(0x30);", helper)
        self.assertIn("encodedHeader.indexOf(0x30, candidateOffset + 1)", helper)
        self.assertNotIn("for (let i = 0; i <= encodedHeader.byteLength - 32; i++)", helper)
        self.assertIn('throw new Error("BaiduMap MD5 placeholder is ambiguous");', helper)
        self.assertIn('throw new Error("BaiduMap MD5 placeholder not found in encoded RepHead");', helper)


class ResponseScriptAuditTests(unittest.TestCase):
    def test_taobao_handler_has_one_parse_and_no_allocating_array_transform(self):
        source = (ROOT / "scripts/taobao/taobao.js").read_text(encoding="utf-8")
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)
        self.assertNotIn(".filter(", source)
        self.assertNotIn(".map(", source)

    def test_taobao_handler_skips_serialization_for_unchanged_responses(self):
        source = (ROOT / "scripts/taobao/taobao.js").read_text(encoding="utf-8")
        self.assertIn("let modified = false;", source)
        self.assertIn('$done(modified ? {body: JSON.stringify(obj)} : {});', source)
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)

    def test_didi_response_triggers_use_the_local_compacted_runtime(self):
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        source = (ROOT / "scripts/didi/didi.js").read_text(encoding="utf-8")
        legacy_source = (ROOT / "scripts/didi/didi-ads.js").read_text(encoding="utf-8")
        local_target = "script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/didi/didi.js"
        remote_target = "script-path=https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js"
        self.assertEqual(plugin.count(local_target), 4)
        self.assertNotIn(remote_target, plugin)
        self.assertNotIn("scripts/didi/didi-ads.js", plugin)
        self.assertIn("function compactDidiByField(items, field, mode)", source)
        self.assertNotIn(".filter(", source)
        self.assertIn("function filterInPlace", legacy_source)



class TaobaoLazySerializationRuntimeTests(unittest.TestCase):
    runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
let doneResult, parseCalls = 0, stringifyCalls = 0;
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) { parseCalls++; return nativeJSON.parse(value); },
  stringify(value) { stringifyCalls++; return nativeJSON.stringify(value); }
};
const context = {
  JSON: trackedJSON,
  $request: { url: payload.url },
  $response: { body: payload.body === null ? "" : nativeJSON.stringify(payload.body) },
  $done(value) { doneResult = value; }
};
vm.runInNewContext(source, context, { timeout: 5000 });
process.stdout.write(nativeJSON.stringify({
  done: doneResult || null,
  parseCalls,
  stringifyCalls
}));
"""

    def run_script(self, url, body):
        if not NODE:
            self.skipTest("Node.js is required for Taobao runtime tests")
        completed = subprocess.run(
            [NODE, "-e", self.runner, str(ROOT / "scripts/taobao/taobao.js")],
            input=__import__("json").dumps({"url": url, "body": body}),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return __import__("json").loads(completed.stdout)

    def test_noop_video_splash_and_poplayer_responses_skip_stringify(self):
        cases = [
            (
                "https://guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query",
                {"data": {"duration": 0, "resources": [], "caches": [], "respTimeInMs": 0}},
            ),
            (
                "https://guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get",
                {"data": {"containers": {"splash_home_base": {"base": {"sections": [
                    {"bizData": {"normal": {"data": [{"id": "keep"}]}}}
                ]}}}}},
            ),
            (
                "https://poplayer.template.alibaba.com/example.json",
                {"res": {"images": [], "videos": []}, "enable": False, "mainRes": {"images": []}},
            ),
        ]
        for url, body in cases:
            with self.subTest(url=url):
                result = self.run_script(url, body)
                self.assertEqual(result["done"], {})
                self.assertEqual(result["parseCalls"], 1)
                self.assertEqual(result["stringifyCalls"], 0)

    def test_video_query_mutations_still_serialize_once(self):
        result = self.run_script(
            "https://guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query",
            {"data": {"duration": "12", "resources": [1], "caches": [2], "respTimeInMs": 3}},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        body = __import__("json").loads(result["done"]["body"])
        self.assertEqual(body["data"]["duration"], "0")
        self.assertEqual(body["data"]["resources"], [])
        self.assertEqual(body["data"]["caches"], [])
        self.assertEqual(body["data"]["respTimeInMs"], "3818332800000")

    def test_splash_mutations_still_apply_to_target_creative_items(self):
        result = self.run_script(
            "https://guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get",
            {"data": {"containers": {"splash_home_base": {"base": {"sections": [
                {"bizData": {"taobao-splash": {"data": [
                    {"waitTime": "5", "imgUrl": "https://img.example/ad.jpg", "videoUrl": "https://video.example/ad.mp4"}
                ]}}}
            ]}}}}},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        item = __import__("json").loads(result["done"]["body"])["data"]["containers"]["splash_home_base"]["base"]["sections"][0]["bizData"]["taobao-splash"]["data"][0]
        self.assertEqual(item["waitTime"], "0")
        self.assertEqual(item["times"], "0")
        self.assertEqual(item["startTime"], "3818332800000")
        self.assertEqual(item["imgUrl"], "")
        self.assertEqual(item["videoUrl"], "")

    def test_poplayer_mutations_still_clear_creatives_once(self):
        result = self.run_script(
            "https://poplayer.template.alibaba.com/example.json",
            {"res": {"images": [1], "videos": [2]}, "enable": True, "mainRes": {"images": [3]}},
        )
        self.assertEqual(result["parseCalls"], 1)
        self.assertEqual(result["stringifyCalls"], 1)
        body = __import__("json").loads(result["done"]["body"])
        self.assertEqual(body["res"]["images"], [])
        self.assertEqual(body["res"]["videos"], [])
        self.assertFalse(body["enable"])
        self.assertEqual(body["mainRes"]["images"], [])

    def test_empty_body_returns_without_json_work(self):
        result = self.run_script("https://poplayer.template.alibaba.com/example.json", None)
        self.assertEqual(result["done"], {})
        self.assertEqual(result["parseCalls"], 0)
        self.assertEqual(result["stringifyCalls"], 0)



class BaiduMapAdsPreflightTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")

    def test_ads_preflight_runs_before_payload_view_and_protobuf_decode(self):
        self.assertIn("// loon-change: Baidu protobuf raw-signature Ads preflight v2", self.source)
        start = self.source.index("}else if(name === 'Ads'){")
        end = self.source.index("const adsType = baiduMapRoot.lookupType(name);", start)
        block = self.source[start:end]
        self.assertIn("if (!hasBaiduTargetAds(binaryBody, currentOffset, targetDataLength)) continue;", block)
        self.assertLess(block.index("hasBaiduTargetAds("), block.index("const targetData = binaryBody.subarray("))
        self.assertIn("buffer.indexOf(95, start)", self.source)
        self.assertIn("buffer.indexOf(95, index + 1)", self.source)
        self.assertNotIn("function readVarint(limit)", self.source)
        self.assertNotIn("function skipField(wireType, limit)", self.source)

    @unittest.skipUnless(NODE, "Node.js is required for BaiduMap protobuf preflight tests")
    def test_preflight_skips_non_target_content_and_decodes_target_content(self):
        cases = [
            ("home_banner", True),
            ("splash_screen1040", True),
            ("normal", False),
            ("ordinary_creative", False),
        ]
        for content_type, expected_body in cases:
            with self.subTest(content_type=content_type):
                result = BaiduMapNoopRebuildRuntimeTests().run_script(content_type, 1, 2)
                self.assertEqual(result["hasBody"], expected_body)
                if not expected_body:
                    self.assertEqual(result["subarrayCount"], 1)
                    self.assertEqual(result["adsContentReads"], 0)


class BaiduMapNoopRebuildRuntimeTests(unittest.TestCase):
    runner = r"""
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync(process.argv[1], "utf8").replace(
  "function createBaiduMd5() {",
  "function createBaiduMd5() { globalThis.__md5InitCount = (globalThis.__md5InitCount || 0) + 1;"
);
source = source.replace(
  "const isQuanX =",
  "function countedSubarray(buffer, ...args) { globalThis.__subarrayCount = (globalThis.__subarrayCount || 0) + 1; return buffer.subarray(...args); }\nconst isQuanX ="
);
source = source
  .replace("hash(body.subarray(payloadOffset))", "hash(countedSubarray(body, payloadOffset))")
  .replace("binaryBody.subarray(beginOffset, beginOffset + prefixLength)", "countedSubarray(binaryBody, beginOffset, beginOffset + prefixLength)")
  .replace("binaryBody.subarray(currentOffset, currentOffset + targetDataLength)", "countedSubarray(binaryBody, currentOffset, currentOffset + targetDataLength)")
  .replace("binaryBody.subarray(resultOffset, resultOffset + resultLength)", "countedSubarray(binaryBody, resultOffset, resultOffset + resultLength)");


source = source.replace(
  "const adsMessage = adsType.decode(targetData);",
  "const adsMessage = adsType.decode(targetData);\n" +
  "globalThis.__adsContentReads = 0; globalThis.__adsStartReads = 0; globalThis.__adsEndReads = 0; globalThis.__trackAdsProperties = true;\n" +
  "let trackedAdsContent = adsMessage.content; Object.defineProperty(adsMessage, 'content', { configurable: true, enumerable: true, get() { if (globalThis.__trackAdsProperties) globalThis.__adsContentReads++; return trackedAdsContent; }, set(value) { trackedAdsContent = value; } });\n" +
  "for (let k = 0; k < trackedAdsContent.length; k++) { const target = trackedAdsContent[k]; trackedAdsContent[k] = new Proxy(target, { get(target, key, receiver) { if (globalThis.__trackAdsProperties && key === 'start') globalThis.__adsStartReads++; if (globalThis.__trackAdsProperties && key === 'end') globalThis.__adsEndReads++; return Reflect.get(target, key, receiver); } }); }"
);
source = source.replace(
  "if(modifiedAds) newAds = adsType.encode(adsMessage).finish();",
  "if(modifiedAds) { globalThis.__trackAdsProperties = false; newAds = adsType.encode(adsMessage).finish(); }"
);


function varint(value) {
  const out = [];
  value >>>= 0;
  while (value > 127) { out.push((value & 127) | 128); value >>>= 7; }
  out.push(value);
  return out;
}
function bytesField(id, value) {
  return [...varint((id << 3) | 2), ...varint(value.length), ...value];
}
function stringField(id, value) {
  return bytesField(id, Array.from(Buffer.from(value, "utf8")));
}
function intField(id, value) {
  return [...varint(id << 3), ...varint(value)];
}
function content(type, start, end) {
  return [
    ...stringField(1, type),
    ...intField(4, start),
    ...intField(5, end)
  ];
}
function fixture(type, start, end, includeAds) {
  const result = [8, 0];
  const fields = [
    bytesField(3, [
      ...intField(1, 0), ...intField(2, result.length), ...stringField(3, "Result")
    ])
  ];
  const payload = result.slice();
  if (includeAds) {
    const contentCount = Math.max(1, Number(process.argv[6]) || 1);
    const ads = [];
    for (let index = 0; index < contentCount; index++) {
      ads.push(...bytesField(2, content(type, start, end)));
    }
    fields.push(bytesField(3, [
      ...intField(1, result.length), ...intField(2, ads.length), ...stringField(3, "Ads")
    ]));
    payload.push(...ads);
  }
  const head = [...stringField(1, "0123456789abcdef0123456789abcdef")];
  for (const field of fields) head.push(...field);
  const prefix = Buffer.alloc(4);
  prefix.writeInt32BE(head.length, 0);
  return new Uint8Array(Buffer.concat([prefix, Buffer.from(head), Buffer.from(payload)]));
}

const input = fixture(process.argv[2], Number(process.argv[3]), Number(process.argv[4]), process.argv[5] !== "no-ads");
let doneResult;
const context = {
  $response: { body: input },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.runInNewContext(source, context, { timeout: 10000 });
const testRoot = vm.runInContext("baiduMapRoot", context);
if (!doneResult) throw new Error("script did not call $done");

let output = null;
if (doneResult.body) {
  output = new Uint8Array(doneResult.body);
  context.__outputBytes = Array.from(output);
  const decoded = vm.runInContext(`(() => {
    const bytes = new Uint8Array(__outputBytes);
    const headerLength = new DataView(bytes.buffer, bytes.byteOffset, 4).getInt32(0);
    const header = baiduMapRoot.lookupType("RepHead").decode(bytes.subarray(4, 4 + headerLength));
    const adsHead = header.messageHead.find(item => item.name === "Ads");
    const adsStart = 4 + headerLength + adsHead.offset;
    const ads = baiduMapRoot.lookupType("Ads").decode(bytes.subarray(adsStart, adsStart + adsHead.length));
    return { md5: header.md5, item: ads.content[0] };
  })()`, context);
  process.stdout.write(JSON.stringify({
    hasBody: true,
    originalLength: input.length,
    outputLength: output.length,
    md5: decoded.md5,
    md5InitCount: context.__md5InitCount || 0,
    subarrayCount: context.__subarrayCount || 0,
    adsContentReads: context.__adsContentReads || 0,
    adsStartReads: context.__adsStartReads || 0,
    adsEndReads: context.__adsEndReads || 0,
    item: decoded.item
  }));
} else {
  process.stdout.write(JSON.stringify({
    hasBody: false,
    originalLength: input.length,
    md5InitCount: context.__md5InitCount || 0,
    subarrayCount: context.__subarrayCount || 0,
    adsContentReads: context.__adsContentReads || 0,
    adsStartReads: context.__adsStartReads || 0,
    adsEndReads: context.__adsEndReads || 0
  }));
}
"""

    def run_script(self, content_type, start, end, include_ads=True, content_count=1):
        if not NODE:
            self.skipTest("Node.js is required for BaiduMap protobuf runtime tests")
        completed = subprocess.run(
            [NODE, "-e", self.runner, str(ROOT / "scripts/baidumap/baidu-map-protobuf.js"),
             content_type, str(start), str(end), "with-ads" if include_ads else "no-ads", str(content_count)],
            capture_output=True, text=True, check=False, timeout=15,
        )
        if completed.returncode:
            raise AssertionError(completed.stderr or completed.stdout)
        return __import__("json").loads(completed.stdout)

    def test_end_field_is_read_only_when_start_already_matches(self):
        count = 3
        result = self.run_script("home_banner", 1648746061, 1, content_count=count)
        self.assertTrue(result["hasBody"])
        self.assertEqual(result["adsContentReads"], 1)
        self.assertEqual(result["adsStartReads"], count)
        self.assertEqual(result["adsEndReads"], count)
        self.assertEqual(result["item"]["start"], 1648746061)
        self.assertEqual(result["item"]["end"], 1648832461)

    def test_missing_ads_section_passes_through_without_reassembly(self):
        result = self.run_script("normal", 1, 2, include_ads=False)
        self.assertFalse(result["hasBody"])
        self.assertEqual(result["md5InitCount"], 0)
        self.assertEqual(result["subarrayCount"], 1)

    def test_non_target_ads_skip_protobuf_decode_encode_md5_and_payload_view(self):
        result = self.run_script("normal", 1, 2)
        self.assertFalse(result["hasBody"])
        self.assertEqual(result["md5InitCount"], 0)
        self.assertEqual(result["subarrayCount"], 1)
        self.assertEqual(result["adsContentReads"], 0)
        self.assertEqual(result["adsStartReads"], 0)
        self.assertEqual(result["adsEndReads"], 0)

    def test_already_clean_target_ads_skip_protobuf_encode_md5_and_body_reassembly(self):
        result = self.run_script("home_banner", 1648746061, 1648832461)
        self.assertFalse(result["hasBody"])
        self.assertEqual(result["md5InitCount"], 0)
        self.assertEqual(result["subarrayCount"], 2)
        self.assertEqual(result["adsContentReads"], 1)
        self.assertEqual(result["adsStartReads"], 1)
        self.assertEqual(result["adsEndReads"], 1)

    def test_changed_target_ads_still_rebuild_with_correct_values(self):
        result = self.run_script("home_banner", 1, 2)
        self.assertTrue(result["hasBody"])
        self.assertEqual(result["item"]["start"], 1648746061)
        self.assertEqual(result["item"]["end"], 1648832461)
        self.assertEqual(len(result["md5"]), 32)
        self.assertGreater(result["outputLength"], 0)
        self.assertEqual(result["md5InitCount"], 1)
        self.assertEqual(result["subarrayCount"], 4)
        self.assertEqual(result["adsContentReads"], 1)
        self.assertEqual(result["adsStartReads"], 1)
        self.assertEqual(result["adsEndReads"], 0)

    def test_large_ads_content_array_reads_collection_once_and_preserves_short_circuit(self):
        count = 64
        result = self.run_script("home_banner", 1, 2, content_count=count)
        self.assertTrue(result["hasBody"])
        self.assertEqual(result["adsContentReads"], 1)
        self.assertEqual(result["adsStartReads"], count)
        self.assertEqual(result["adsEndReads"], 0)
        self.assertEqual(result["item"]["start"], 1648746061)
        self.assertEqual(result["item"]["end"], 1648832461)


    def test_raw_signature_scan_uses_native_underscore_index(self):
        self.source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")
        marker = "// loon-change: BaiduMap underscore-indexed Ads signature scan v1"
        self.assertIn(marker, self.source)
        start = self.source.index(marker)
        end = self.source.index("\n}", start) + 2
        helper = self.source[start:end]
        self.assertIn("buffer.indexOf(95, start)", helper)
        self.assertIn("buffer.indexOf(95, index + 1)", helper)
        self.assertNotIn("for (let i = start; i < end; i++)", helper)

    @unittest.skipUnless(NODE, "Node.js is required for BaiduMap signature scan tests")
    def test_indexed_signature_scan_matches_reference_across_bounds_and_payloads(self):
        runner = r"""
const fs = require("fs"), vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const marker = "// loon-change: BaiduMap underscore-indexed Ads signature scan v1";
const start = source.indexOf(marker);
const end = source.indexOf("\n}", start) + 2;
const context = {};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + "; globalThis.scan = hasBaiduTargetAds;", context);
function reference(buffer, start, length) {
  if (start < 0 || length < 0 || start > buffer.length || length > buffer.length - start) return true;
  const end = start + length;
  for (let i = start; i < end; i++) {
    const byte = buffer[i];
    if (byte === 95 && i + 6 < end && buffer[i+1] === 98 && buffer[i+2] === 97 && buffer[i+3] === 110 && buffer[i+4] === 110 && buffer[i+5] === 101 && buffer[i+6] === 114) return true;
    if (byte === 115 && i + 16 < end && buffer[i+1] === 112 && buffer[i+2] === 108 && buffer[i+3] === 97 && buffer[i+4] === 115 && buffer[i+5] === 104 && buffer[i+6] === 95 && buffer[i+7] === 115 && buffer[i+8] === 99 && buffer[i+9] === 114 && buffer[i+10] === 101 && buffer[i+11] === 101 && buffer[i+12] === 110 && buffer[i+13] === 49 && buffer[i+14] === 48 && buffer[i+15] === 52 && buffer[i+16] === 48) return true;
  }
  return false;
}
const cases = [
  ["xx_bannerzz", 2, 7, true], ["xxsplash_screen1040zz", 2, 17, true],
  ["xxordinary_creativezz", 2, 18, false], ["_banner", 0, 7, true],
  ["splash_screen1040", 0, 17, true], ["splash_screen104", 0, 16, false],
  ["x_banner", 1, 6, false], ["x_banner", 2, 7, true],
  ["splash_screen1040", 1, 16, false], ["splash_screen1040", -1, 5, true],
  ["splash_screen1040", 0, 99, true]
];
for (const [raw, offset, length, expected] of cases) {
  const bytes = new Uint8Array(Buffer.from(raw));
  const actual = context.scan(bytes, offset, length);
  if (actual !== expected || actual !== reference(bytes, offset, length)) throw new Error("fixture mismatch " + raw);
}
let seed = 0x12345678;
for (let n = 0; n < 500; n++) {
  const length = n % 257, bytes = new Uint8Array(length + 8);
  for (let i = 0; i < bytes.length; i++) { seed = (seed * 1664525 + 1013904223) >>> 0; bytes[i] = seed >>> 24; }
  if (n % 3 === 0 && length >= 7) bytes.set(Buffer.from("_banner"), 4 + (n % (length - 6)));
  if (n % 5 === 0 && length >= 17) bytes.set(Buffer.from("splash_screen1040"), 4 + (n % (length - 16)));
  const from = n % 5 === 0 ? 4 : 0, span = n % 7 === 0 ? length : Math.max(0, length - (n % 9));
  if (context.scan(bytes, from, span) !== reference(bytes, from, span)) throw new Error("random mismatch " + n);
}
process.stdout.write("ok");
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(ROOT / "scripts/baidumap/baidu-map-protobuf.js")],
            capture_output=True, text=True, check=True, timeout=10,
        )
        self.assertEqual(completed.stdout, "ok")


    def test_ads_reencoding_is_gated_by_current_segment_mutation(self):
        marker = "// loon-change: Baidu protobuf per-segment Ads mutation gate v1"
        self.assertIn(marker, self.source)
        start = self.source.index(marker)
        end = self.source.index("    }\n  }\n}", start)
        segment = self.source[start:end]
        self.assertIn("let adsSegmentModified = false;", segment)
        self.assertIn("adsSegmentModified = true;", segment)
        self.assertIn("if (adsSegmentModified) {", segment)
        self.assertIn("modifiedAds = true;", segment)
        self.assertIn("newAds = adsType.encode(adsMessage).finish();", segment)
        self.assertNotIn("if(modifiedAds) newAds =", segment)
        self.assertEqual(segment.count("adsType.encode(adsMessage).finish()"), 1)


if __name__ == "__main__":
    unittest.main()
