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
        self.assertFalse(any("console.log(" in line and any(token in line for token in ("原body：","新body：","写入缓存val","comment_id:","video_id：")) for line in src.splitlines()))

    def test_comment_processing_combines_tree_cleanup_and_media_extraction(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn("function processCommentTree(data, livePhotos, commentVideos, noteId)",source)
        self.assertNotIn("replaceRedIdWithFmz200(obj.data)",source)
        self.assertNotIn("function replaceRedIdWithFmz200(obj)",source)
        self.assertIn("const parsedVideoInfo = new Map()",source)
        self.assertIn("processCommentTree(obj.data, livePhotos, commentVideos, note_id);",source)

    @unittest.skipUnless(NODE,"Node required for comment runtime test")
    def test_comment_tree_single_pass_preserves_cleanup_and_media_caches(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,parseCalls=0;
const nativeJSON=JSON;
const trackedJSON={parse(value){parseCalls++;return nativeJSON.parse(value);},stringify(value){return nativeJSON.stringify(value);}};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),store:Object.fromEntries(store),parseCalls}));
'''
        video_info=json.dumps({"stream":{"h265":[
            {"master_url":"https://video.example/720.mp4","width":1280,"height":720},
            {"master_url":"https://video.example/2160.mp4","width":3840,"height":2160}
        ]}})
        body={"data":{"red_id":"root","comments":[{
            "id":"top","note_id":"note-1","red_id":"top-red","comment_type":3,"media_source_type":1,
            "pictures":[{"video_id":"live-1","video_info":video_info}],
            "videos":[{"video_id":"comment-video-1","video_info":video_info}],
            "sub_comments":[{"id":"sub","red_id":"sub-red","comment_type":3,"pictures":[
                {"video_id":"live-2","video_info":video_info}
            ],"nested":{"red_id":"deep-red"}}]
        }]}}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout);comment=out["body"]["data"]["comments"][0]
        sub=comment["sub_comments"][0]
        self.assertNotIn("red_id",out["body"]["data"])
        self.assertNotIn("red_id",comment)
        self.assertNotIn("red_id",sub)
        self.assertNotIn("red_id",sub["nested"])
        self.assertEqual(comment["fmz200"],"top-red")
        self.assertEqual(sub["fmz200"],"sub-red")
        self.assertEqual(comment["comment_type"],2)
        self.assertEqual(comment["media_source_type"],0)
        self.assertEqual(sub["comment_type"],2)
        live=json.loads(out["store"]["fmz200.xiaohongshu.comments.rsp"])
        videos=json.loads(out["store"]["fmz200.xiaohongshu.comments.videos.rsp"])
        self.assertEqual([x["videId"] for x in live["livePhotos"]],["live-1","live-2"])
        self.assertEqual(live["livePhotos"][0]["videoUrl"],"https://video.example/2160.mp4")
        self.assertEqual(videos["videos"][0]["videId"],"comment-video-1")
        self.assertEqual(videos["videos"][0]["videoUrl"],"https://video.example/2160.mp4")
        self.assertEqual(out["parseCalls"],2)
    def test_comment_processing_combines_tree_cleanup_and_media_extraction(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn("function processCommentTree(data, livePhotos, commentVideos, noteId)",source)
        self.assertNotIn("replaceRedIdWithFmz200(obj.data)",source)
        self.assertNotIn("function replaceRedIdWithFmz200(obj)",source)
        self.assertIn("const parsedVideoInfo = new Map()",source)
        self.assertIn("processCommentTree(obj.data, livePhotos, commentVideos, note_id);",source)

    @unittest.skipUnless(NODE,"Node required for comment runtime test")
    def test_comment_tree_single_pass_preserves_cleanup_and_media_caches(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,parseCalls=0;
const nativeJSON=JSON;
const trackedJSON={parse(value){parseCalls++;return nativeJSON.parse(value);},stringify(value){return nativeJSON.stringify(value);}};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),store:Object.fromEntries(store),parseCalls}));
'''
        video_info=json.dumps({"stream":{"h265":[
            {"master_url":"https://video.example/720.mp4","height":720},
            {"master_url":"https://video.example/2160.mp4","height":2160}
        ]}})
        body={"data":{"red_id":"root","comments":[{
            "id":"top","note_id":"note-1","red_id":"top-red","comment_type":3,"media_source_type":1,
            "pictures":[{"video_id":"live-1","video_info":video_info}],
            "videos":[{"video_id":"comment-video-1","video_info":video_info}],
            "sub_comments":[{"id":"sub","red_id":"sub-red","comment_type":3,"pictures":[
                {"video_id":"live-2","video_info":video_info}
            ],"nested":{"red_id":"deep-red"}}]
        }]}}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout);comment=out["body"]["data"]["comments"][0]
        sub=comment["sub_comments"][0]
        self.assertNotIn("red_id",out["body"]["data"])
        self.assertNotIn("red_id",comment)
        self.assertNotIn("red_id",sub)
        self.assertNotIn("red_id",sub["nested"])
        self.assertEqual(comment["fmz200"],"top-red")
        self.assertEqual(sub["fmz200"],"sub-red")
        self.assertEqual(comment["comment_type"],2)
        self.assertEqual(comment["media_source_type"],0)
        self.assertEqual(sub["comment_type"],2)
        live=json.loads(out["store"]["fmz200.xiaohongshu.comments.rsp"])
        videos=json.loads(out["store"]["fmz200.xiaohongshu.comments.videos.rsp"])
        self.assertEqual([x["videId"] for x in live["livePhotos"]],["live-1","live-2"])
        self.assertEqual(live["livePhotos"][0]["videoUrl"],"https://video.example/2160.mp4")
        self.assertEqual(videos["videos"][0]["videId"],"comment-video-1")
        self.assertEqual(videos["videos"][0]["videoUrl"],"https://video.example/2160.mp4")
        self.assertEqual(out["parseCalls"],2)
    def test_comment_tree_walk_avoids_object_keys_temporary_arrays(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertNotIn("Object.keys(current)",source)
        self.assertIn("for (const key in current)",source)
        self.assertIn("const visited = new WeakSet()",source)
        self.assertIn("Object.prototype.hasOwnProperty.call(current, key)",source)
        self.assertIn("processCommentTree(obj.data, livePhotos, commentVideos, note_id);",source)

    def test_plugin_rewrites_exact_nine_triggers(self):
        dollar=chr(36)
        fixture="[Script]\n"+"\n".join(
          f'response if {dollar}{{url}} ~= /^https:\\/\\/xhs{i}/ then script("{REMOTE}")' for i in range(9)
        )+"\n[MITM]\nhostname = example.com\n"
        out=rewrite_plugin(fixture)
        self.assertEqual(out.count(LOCAL),9)
        self.assertNotIn(REMOTE,out)
        self.assertEqual(rewrite_plugin(out),out)

    def test_preserves_base_only_plugin_without_retired_xhs_triggers(self):
        fixture = "[Script]\nhttp-response ^https?:\\\\/\\\\/example\\\\.com script-path=https://example.invalid/keep.js\n[MITM]\nhostname = example.com\n"
        self.assertEqual(rewrite_plugin(fixture), fixture)

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
        body={"data":[{"note_list":[{"images_list":[{"url":original,"nested":{"url":original},
          "live_photo_file_id":"live-file-1","live_photo":{"media":{"video_id":"video-1","stream":{"h265":[{"master_url":"https://video.example/live.mp4"}]}}}}],
          "media_save_config":{"disable_save":True},"share_info":{"function_entries":[{"type":"share"}]},
          "note_text_press_options":[{"key":"copy"}],"hash_tag":[{"type":"normal"},{"type":"interact_vote"}]}]}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({"url":"https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=fixture","body":body}),
          cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout);item=out["body"]["data"][0]["note_list"][0]
        self.assertIn("w/2160/format",item["images_list"][0]["url"])
        self.assertIn("w/2160/format",item["images_list"][0]["nested"]["url"])
        cache=json.loads(out["store"]["fmz200.xiaohongshu.feed.rsp"])
        self.assertEqual(cache, [{
            "live_photo_file_id": "live-file-1",
            "video_id": "video-1",
            "url": "https://video.example/live.mp4"
        }])
        self.assertNotIn("nested", cache[0])
        self.assertLess(len(out["store"]["fmz200.xiaohongshu.feed.rsp"]), len(json.dumps(body["data"][0]["note_list"][0]["images_list"])))
        self.assertEqual([x["type"] for x in item["hash_tag"]],["normal"])

    @unittest.skipUnless(NODE,"Node required for runtime test")
    def test_live_photo_save_reads_compact_cache(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map(Object.entries(p.store));let done;
const ctx={$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:JSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify(JSON.parse(done.body)));
"""
        compact=[{"live_photo_file_id":"live-file-1","video_id":"video-1","url":"https://video.example/live.mp4"}]
        body={"code":0,"data":{"datas":[{"file_id":"live-file-1","url":"https://placeholder.example/video.mp4"}]}}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v1/note/live_photo/save",
            "body":body,"store":{"fmz200.xiaohongshu.feed.rsp":json.dumps(compact)}}),
            cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        self.assertEqual(out["data"]["datas"][0]["url"],"https://video.example/live.mp4")

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
