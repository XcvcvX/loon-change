import json, shutil, subprocess, unittest
from pathlib import Path
from optimize_xiaohongshu import LOCAL, REMOTE, MARKER, optimize_source, rewrite_plugin

ROOT=Path(__file__).resolve().parent
NODE=shutil.which("node")

class XiaohongshuOptimizerTests(unittest.TestCase):
    def test_optimizer_snapshot_idempotence(self):
        src=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn(MARKER,src)
        self.assertEqual(optimize_source(src),src)
        self.assertNotIn("imageEnhance(JSON.stringify(images_list))",src)
        self.assertIn("imageEnhance(images_list)",src)
        self.assertIn("const byFileId=new Map()",src)
        self.assertNotIn("console.log('新body：' + JSON.stringify(obj))",src)
        self.assertNotIn('console.log("写入缓存val：" + JSON.stringify(commitsRsp))',src)

    def test_plugin_rewrites_exact_nine_triggers(self):
        dollar=chr(36)
        fixture="[Script]\n"+"\n".join(
          f'response if {dollar}{{url}} ~= /^https:\\/\\/xhs{i}/ then script("{REMOTE}")' for i in range(9)
        )+"\n[MITM]\nhostname = example.com\n"
        out=rewrite_plugin(fixture)
        self.assertEqual(out.count(LOCAL),9)
        self.assertNotIn(REMOTE,out)
        self.assertEqual(rewrite_plugin(out),out)

    def test_trigger_count_drift_fails_closed(self):
        fixture=f'[Script]\nresponse if {chr(36)}{{url}} ~= /^https:\\/\\/xhs/ then script("{REMOTE}")\n'
        with self.assertRaisesRegex(ValueError,"trigger inventory changed"):rewrite_plugin(fixture)

    @unittest.skipUnless(NODE,"Node required for runtime test")
    def test_imagefeed_cache_remains_original_and_response_is_enhanced(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done;
const ctx={$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:JSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify({body:JSON.parse(done.body),store:Object.fromEntries(store)}));
"""
        original="https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"
        body={"data":[{"note_list":[{"images_list":[{"url":original,"nested":{"url":original}}],
          "media_save_config":{"disable_save":True},"share_info":{"function_entries":[{"type":"share"}]},
          "note_text_press_options":[{"key":"copy"}],"hash_tag":[{"type":"normal"},{"type":"interact_vote"}]}]}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({"url":"https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed","body":body}),
          cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout);item=out["body"]["data"][0]["note_list"][0]
        self.assertIn("w/2160/format",item["images_list"][0]["url"])
        self.assertIn("w/2160/format",item["images_list"][0]["nested"]["url"])
        cache=json.loads(out["store"]["fmz200.xiaohongshu.feed.rsp"])
        self.assertEqual(cache[0]["url"],original)
        self.assertEqual(cache[0]["nested"]["url"],original)
        self.assertEqual([x["type"] for x in item["hash_tag"]],["normal"])

    @unittest.skipUnless(NODE,"Node required for runtime test")
    def test_homefeed_filters_stably_and_removes_related_question(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8"));let done;
const ctx={$loon:{},$persistentStore:{read(){return null},write(){return true}},
$request:{url:p.url},$response:{body:JSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});process.stdout.write(JSON.stringify(JSON.parse(done.body)));
"""
        body={"data":[{"id":"keep1","related_ques":{}},None,{"id":"ad","ads_info":{}},{"id":"live","model_type":"live_v2"},
          {"id":"shop","note_attributes":["goods"]},{"id":"card","card_icon":None},{"id":"keep2"}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({"url":"https://edith.xiaohongshu.com/api/sns/v6/homefeed","body":body}),
          cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        self.assertEqual([x["id"] for x in out["data"] if x],["keep1","keep2"])
        self.assertIsNone(out["data"][1])
        self.assertNotIn("related_ques",out["data"][0])
