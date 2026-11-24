import json
import shutil
import subprocess
import unittest
from pathlib import Path

NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parent / "scripts" / "taobao" / "taobao.js"
from optimize_taobao import KELEE_PATH, LOCAL, CLEAR_ARRAY_PROPERTY_MARKER, optimize_clear_array_property_access, optimize_runtime_source, rewrite_plugin

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
  __stringifyCount: 0,
  __parseCount: 0
};
vm.createContext(context);
vm.runInContext(
  "const native = JSON.stringify.bind(JSON); JSON.stringify = function(value) { __stringifyCount++; return native(value); }; const nativeParse = JSON.parse.bind(JSON); JSON.parse = function(value) { __parseCount++; return nativeParse(value); };",
  context
);
vm.runInContext(source, context, { timeout: 5000 });
const result = { parseCount: context.__parseCount, stringifyCount: context.__stringifyCount, passThrough: !doneResult || typeof doneResult.body !== "string" };
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
        result = self.run_script("https://guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get", body)
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


    def test_unrelated_response_skips_json_parse(self):
        result = self.run_script("https://acs.m.taobao.com/gw/mtop.taobao.detail.getdetail", {"large": [1, 2, 3]})
        self.assertTrue(result["passThrough"])
        self.assertEqual(result["parseCount"], 0)
        self.assertEqual(result["stringifyCount"], 0)

    def test_splash_traversal_uses_cached_references_and_indexed_loops(self):
        from optimize_taobao import SPLASH_LOOP_MARKER, optimize_runtime_source
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(SPLASH_LOOP_MARKER, source)
        self.assertIn("const sectionCount = sections.length;", source)
        self.assertIn("const bizData = sections[sectionIndex]?.bizData;", source)
        self.assertIn('const splashItems = bizData?.["taobao-splash"]?.data;', source)
        self.assertIn("const itemCount = splashItems.length;", source)
        self.assertIn("for (let sectionIndex = 0; sectionIndex < sectionCount; sectionIndex++)", source)
        self.assertIn("for (let itemIndex = 0; itemIndex < itemCount; itemIndex++)", source)
        self.assertNotIn("for (let items of splash.base.sections)", source)
        self.assertNotIn('for (let item of items.bizData["taobao-splash"].data)', source)
        self.assertEqual(optimize_runtime_source(source), source)

    def test_splash_optimizer_fails_closed_on_unknown_upstream_shape(self):
        from optimize_taobao import optimize_splash_loop
        source = SCRIPT.read_text(encoding="utf-8")
        damaged = source.replace("// loon-change: Taobao indexed splash traversal v1", "", 1)
        damaged = damaged.replace("const sections = obj.data.containers.splash_home_base.base?.sections;", "const sections = obj.data.other;", 1)
        with self.assertRaisesRegex(ValueError, "splash traversal anchor"):
            optimize_splash_loop(damaged)

    def test_supported_routes_are_guarded_before_parse_and_guard_is_idempotent(self):
        from optimize_taobao import RUNTIME_MARKER, optimize_runtime_source
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(RUNTIME_MARKER, source)
        self.assertLess(source.index("const shouldProcess ="), source.index("JSON.parse($response.body)"))
        self.assertEqual(optimize_runtime_source(source), source)

    def test_route_classification_is_cached_once_and_reused(self):
        from optimize_taobao import ROUTE_CLASSIFICATION_MARKER, optimize_runtime_source
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(ROUTE_CLASSIFICATION_MARKER, source)
        self.assertEqual(source.count('url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query")'), 1)
        self.assertEqual(source.count('url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get")'), 1)
        self.assertEqual(source.count('url.includes("poplayer.template.alibaba.com/")'), 1)
        self.assertIn("if (isCloudVideo) {", source)
        self.assertIn("} else if (isSplash) {", source)
        self.assertIn("} else if (isPoplayer) {", source)
        self.assertEqual(optimize_runtime_source(source), source)

    def test_route_optimizer_repairs_original_upstream_form(self):
        from optimize_taobao import OLD_ROUTE_GUARD, optimize_route_classification
        source = SCRIPT.read_text(encoding="utf-8")
        current_guard = source[source.index("  // loon-change: Taobao pre-parse supported-route guard v1"):source.index("  const obj = JSON.parse($response.body);")]
        source = source.replace(current_guard, OLD_ROUTE_GUARD + "\\n", 1)
        source = source.replace("if (isCloudVideo) {", 'if (url.includes("mtop.taobao.cloudvideo.video.query")) {', 1)
        source = source.replace("} else if (isSplash) {", '} else if (url.includes("mtop.taobao.wireless.home.splash.awesome.get")) {', 1)
        source = source.replace("} else if (isPoplayer) {", '} else if (url.includes("poplayer.template.alibaba.com")) {', 1)
        repaired = optimize_route_classification(source)
        self.assertIn("const isCloudVideo = url.includes(", repaired)
        self.assertIn("if (isCloudVideo) {", repaired)
        self.assertEqual(optimize_route_classification(repaired), repaired)

if __name__ == "__main__":
    unittest.main()


class TaobaoClearArrayPropertyAccessTests(unittest.TestCase):
    def test_clear_array_optimizer_is_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_clear_array_property_access(source), source)
        self.assertEqual(source.count(CLEAR_ARRAY_PROPERTY_MARKER), 1)
        damaged = source.replace("const current = target[key];", "const current = target.payload;", 1)
        self.assertNotEqual(damaged, source)
        with self.assertRaisesRegex(ValueError, "cached property access drifted"):
            optimize_clear_array_property_access(damaged)

    @unittest.skipUnless(NODE, "Node.js is required for Taobao property access runtime tests")
    def test_poplayer_clear_array_reads_each_target_property_once(self):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const source = fs.readFileSync(process.argv[1], "utf8");
let doneResult, trackReads = true;
const reads = Object.create(null);
const nativeJSON = JSON;
const trackedJSON = {
  parse(value) {
    const parsed = nativeJSON.parse(value);
    const wrap = (name, target) => new Proxy(target, {
      get(object, key, receiver) {
        if (trackReads && (key === "images" || key === "videos")) {
          const index = name + "." + String(key);
          reads[index] = (reads[index] || 0) + 1;
        }
        return Reflect.get(object, key, receiver);
      }
    });
    if (parsed.res) parsed.res = wrap("res", parsed.res);
    if (parsed.mainRes) parsed.mainRes = wrap("mainRes", parsed.mainRes);
    return parsed;
  },
  stringify(value) {
    trackReads = false;
    try { return nativeJSON.stringify(value); }
    finally { trackReads = true; }
  }
};
const context = {
  JSON: trackedJSON,
  $request: { url: payload.url },
  $response: { body: nativeJSON.stringify(payload.body) },
  $done(value) { doneResult = value; },
  console: { log() {}, warn() {}, error() {} }
};
vm.createContext(context);
vm.runInContext(source, context, { timeout: 5000 });
const output = doneResult && typeof doneResult.body === "string" ? nativeJSON.parse(doneResult.body) : null;
process.stdout.write(nativeJSON.stringify({ output, reads }));
"""
        body = {
            "res": {"images": ["ad.png"], "videos": ["ad.mp4"]},
            "mainRes": {"images": ["main-ad.png"]},
            "enable": True,
        }
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({
                "url": "https://poplayer.template.alibaba.com/mtop",
                "body": body,
            }),
            capture_output=True, text=True, check=True, timeout=10,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["reads"], {
            "res.images": 1,
            "res.videos": 1,
            "mainRes.images": 1,
        })
        self.assertEqual(result["output"]["res"]["images"], [])
        self.assertEqual(result["output"]["res"]["videos"], [])
        self.assertEqual(result["output"]["mainRes"]["images"], [])
        self.assertFalse(result["output"]["enable"])

    def test_runtime_optimizer_generates_cached_clear_array_helper(self):
        source = SCRIPT.read_text(encoding="utf-8")
        generated = optimize_runtime_source(source)
        self.assertIn(CLEAR_ARRAY_PROPERTY_MARKER, generated)
        self.assertEqual(optimize_runtime_source(generated), generated)


class TaobaoCachedResponseObjectTests(unittest.TestCase):
    def test_video_and_poplayer_reuse_route_objects(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("// loon-change: Taobao cached video response object v1", source)
        self.assertIn("// loon-change: Taobao cached Poplayer response objects v1", source)
        self.assertIn("const videoData = obj?.data;", source)
        self.assertIn("const poplayerRes = obj?.res;", source)
        self.assertIn("const mainRes = obj?.mainRes;", source)
        self.assertIn("const poplayerEnabled = obj?.enable;", source)
        self.assertNotIn("clearArray(obj?.res || {},", source)
        self.assertNotIn("clearArray(obj?.mainRes || {},", source)
        self.assertEqual(source.count("JSON.parse("), 1)
        self.assertEqual(source.count("JSON.stringify("), 1)

    def test_object_cache_optimizer_is_idempotent_and_fails_closed(self):
        from optimize_taobao import OBJECT_CACHE_MARKER, optimize_route_object_access
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_route_object_access(source), source)
        self.assertEqual(source.count(OBJECT_CACHE_MARKER), 1)
        damaged = source.replace("const videoData = obj?.data;", "const videoData = obj?.payload;", 1)
        with self.assertRaisesRegex(ValueError, "cached response object access drifted"):
            optimize_route_object_access(damaged)
