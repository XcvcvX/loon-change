import json, shutil, subprocess, unittest
from pathlib import Path
from optimize_zhihu import LOCAL, REMOTE, MARKER, optimize_source, rewrite_plugin

ROOT=Path(__file__).resolve().parent
NODE=shutil.which("node")

class ZhihuOptimizerTests(unittest.TestCase):
    def test_source_snapshot_and_all_filters_are_compacted_in_place(self):
        src=(ROOT/"scripts/zhihu/zhihu.js").read_text(encoding="utf-8")
        self.assertIn(MARKER,src)
        self.assertEqual(optimize_source(src),src)
        self.assertEqual(src.count("compactInPlace(")-1,11)
        self.assertNotIn(".filter(",src)
        self.assertNotIn("Object.fromEntries(",src)
        self.assertNotIn("getUrlParamValue(item.fields.header.url",src)
        self.assertEqual(src.count("fallbackSearch"),2)

    def test_exact_eight_plugin_triggers_are_rewritten(self):
        dollar=chr(36)
        fixture="[Script]\n"+"\n".join(
            f'response if {dollar}{{url}} ~= /^https:\\/\\/zhihu{i}/ then script("{REMOTE}")'
            for i in range(8)
        )+"\n[MITM]\nhostname = api.zhihu.com\n"
        out=rewrite_plugin(fixture)
        self.assertEqual(out.count(LOCAL),8)
        self.assertNotIn(REMOTE,out)
        self.assertEqual(rewrite_plugin(out),out)

    def test_trigger_inventory_drift_fails_closed(self):
        fixture=f'[Script]\nresponse if {chr(36)}{{url}} ~= /^https:\\/\\/zhihu/ then script("{REMOTE}")\n'
        with self.assertRaisesRegex(ValueError,"trigger inventory changed"):rewrite_plugin(fixture)

    @unittest.skipUnless(NODE,"Node.js required for response runtime tests")
    def test_topstory_feed_compacts_once_and_preserves_video_ids(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/zhihu/zhihu.js","utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8"));let done;
const ctx={$request:{url:payload.url},$response:{body:JSON.stringify(payload.body)},$done:v=>done=v,
console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify(done));
"""
        body={"data":[
          {"type":"market_card","fields":{"header":{"url":"https://www.zhihu.com/video?videoID=market-1"},"body":{"video":{"id":"old-market"}}}},
          {"type":"common_card","extra":{"type":"drama"}},
          {"type":"common_card","common_card":{"feed_content":{"video":{"id":"old-fallback"}}}},
          {"type":"common_card","extra":{"type":"zvideo"},"common_card":{"feed_content":{"video":{"customized_page_url":"https://www.zhihu.com/video?x=1&videoID=custom-2","id":"old-custom"}}}},
          {"type":"common_card","common_card":{"footline":{"elements":[{"text":{"panel_text":"广告推广"}}]}}},
          {"type":"common_card","common_card":{"feed_content":{"source_line":{"elements":[{},{"text":{"panel_text":"盐选专栏"}}]}}}},
          {"type":"common_card","promotion_extra":{}},
          {"type":"aggregation_card"},
          {"type":"feed_advert"},
          {"type":"common_card","common_card":{"feed_content":{"video":{"id":"second-fallback"}}}},
          {"type":"normal_card"}
        ]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({"url":"https://api.zhihu.com/topstory/recommend?fixture=1","body":body}),
          cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)["body"]
        ids=[item["type"] for item in out["data"]]
        self.assertEqual(ids,["market_card","common_card","common_card","normal_card"])
        self.assertEqual(out["data"][0]["fields"]["body"]["video"]["id"],"market-1")
        self.assertEqual(out["data"][1]["common_card"]["feed_content"]["video"]["id"],'"old-fallback"')
        self.assertEqual(out["data"][2]["common_card"]["feed_content"]["video"]["id"],"custom-2")
        self.assertEqual([item["offset"] for item in out["data"]],[1,2,3,4])

    @unittest.skipUnless(NODE,"Node.js required for response runtime tests")
    def test_empty_body_ends_without_attempting_json_parse(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/zhihu/zhihu.js","utf8");
let calls=[];const ctx={$request:{url:"https://api.zhihu.com/topstory/recommend"},$response:{body:""},
$done:v=>calls.push(v),console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});process.stdout.write(JSON.stringify(calls));
"""
        run=subprocess.run([NODE,"-e",runner],cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        self.assertEqual(json.loads(run.stdout),[{}])
