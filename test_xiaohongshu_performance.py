import json, shutil, subprocess, unittest
from pathlib import Path
from optimize_xiaohongshu import LOCAL, REMOTE, MARKER, IMAGE_FEED_MARKER, VIDEO_SAVE_LOOKUP_MARKER, VIDEO_SAVE_LAZY_PARSE_MARKER, STREAM_SELECTION_MARKER, VIDEO_ENTRY_MARKER, IMAGE_LIVE_PHOTO_CACHE_MARKER, COMMENT_MEDIA_CACHE_MARKER, COMMENT_STACK_FRAME_MARKER, FUNCTION_SWITCH_MARKER, VIDEO_V3_ITEM_CACHE_MARKER, V4_FEED_ARRAY_LENGTH_MARKER, optimize_v4_feed_array_length_snapshot, optimize_v3_video_feed_item_reference_cache, VIDEO_FEED_REFERENCE_CACHE_MARKER, optimize_v4_video_feed_nested_reference_cache, optimize_v4_function_switch_indexed_scan, optimize_comment_stack_frame_allocation, optimize_comment_media_property_cache, optimize_imagefeed_live_photo_property_cache, optimize_comment_video_info_cache, optimize_imagefeed_single_traversal, optimize_video_save_cache_lookup, optimize_video_save_lazy_cache_parse, optimize_stream_selection_no_closure, optimize_v4_video_feed_function_entry_scan, optimize_comment_node_array_classification, COMMENT_NODE_ARRAY_MARKER, IMAGE_ARRAY_LENGTH_MARKER, optimize_imagefeed_array_length_cache, COMMENT_ARRAY_LENGTH_MARKER, optimize_comment_array_length_cache, optimize_source, rewrite_plugin

ROOT=Path(__file__).resolve().parent
SCRIPT=ROOT/"scripts/xiaohongshu/xiaohongshu.js"
NODE=shutil.which("node")

class XiaohongshuOptimizerTests(unittest.TestCase):
    def test_optimizer_snapshot_idempotence(self):
        src=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn(MARKER,src)
        self.assertEqual(optimize_source(src),src)
        self.assertNotIn("imageEnhance(JSON.stringify(images_list))",src)
        self.assertIn("imageEnhance(images_list, livePhotoCache)",src)
        self.assertIn(IMAGE_FEED_MARKER,src)
        self.assertIn(IMAGE_ARRAY_LENGTH_MARKER,src)
        self.assertIn("frame.index>=frame.length",src)
        self.assertIn(COMMENT_ARRAY_LENGTH_MARKER,src)
        self.assertIn("const currentLength = current.length;",src)
        self.assertIn("const commentsLength = child.length;",src)
        self.assertIn("const subCommentsLength = child.length;",src)
        self.assertNotIn("if(frame.index>=value.length)",src)
        self.assertNotIn("for (const image of images_list)",src)
        self.assertIn("const byFileId=new Map()",src)
        self.assertIn("// loon-change: Xiaohongshu comment video-info cache single lookup v2;",src)
        self.assertNotIn("parsedVideoInfo.has(raw)",src)
        self.assertIn(VIDEO_SAVE_LOOKUP_MARKER,src)
        self.assertIn(VIDEO_SAVE_LAZY_PARSE_MARKER,src)
        self.assertIn('const noteId = obj.data?.note_id;',src)
        self.assertNotIn('let videoFeed = JSON.parse($.getdata("redBookVideoFeed"));',src)
        self.assertIn("for (let i = videoFeed.length - 1; i >= 0; i--)",src)
        self.assertNotIn("for (let item of videoFeed)",src)
        self.assertIn(STREAM_SELECTION_MARKER,src)
        stream_start=src.index("function selectBestStream(h265List,h264List) {")
        stream_end=src.index("\n\n\n/**",stream_start)
        stream_block=src[stream_start:stream_end]
        self.assertNotIn("const choose",stream_block)
        self.assertNotIn("=>",stream_block)
        self.assertNotIn("console.log('新body：' + JSON.stringify(obj))",src)
        self.assertNotIn('console.log("写入缓存val：" + JSON.stringify(commitsRsp))',src)
        self.assertFalse(any("console.log(" in line and any(token in line for token in ("原body：","新body：","写入缓存val","comment_id:","video_id：")) for line in src.splitlines()))


    def test_optimizer_wires_comment_array_cache_for_fresh_and_cached_sources(self):
        optimizer=(ROOT/"optimize_xiaohongshu.py").read_text(encoding="utf-8")
        self.assertIn("src = optimize_comment_array_length_cache(src)",optimizer)
        self.assertIn("result = optimize_comment_array_length_cache(result)",optimizer)
        self.assertIn("COMMENT_ARRAY_LENGTH_MARKER,",optimizer)

    def test_imagefeed_optimizer_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn(IMAGE_FEED_MARKER,source)
        self.assertEqual(optimize_imagefeed_single_traversal(source),source)
        damaged=source.replace("frame.root && livePhotoTarget","false && livePhotoTarget")
        with self.assertRaisesRegex(ValueError,"imagefeed single-traversal structure drifted"):
            optimize_imagefeed_single_traversal(damaged)


    def test_imagefeed_live_photo_property_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn(IMAGE_LIVE_PHOTO_CACHE_MARKER,source)
        self.assertEqual(optimize_imagefeed_live_photo_property_cache(source),source)
        self.assertIn("const livePhoto = child.live_photo;",source)
        self.assertIn("const media = livePhoto?.media;",source)
        self.assertIn("const masterUrl = stream?.master_url;",source)
        self.assertNotIn("child.live_photo?.media?.stream?.h265?.[0]",source)
        damaged=source.replace("const masterUrl = stream?.master_url;","const masterUrl = undefined;",1)
        with self.assertRaisesRegex(ValueError,"property-cache marker is stale"):
            optimize_imagefeed_live_photo_property_cache(damaged)

    def test_comment_processing_combines_tree_cleanup_and_media_extraction(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertIn("function processCommentTree(data, livePhotos, commentVideos, noteId)",source)
        self.assertNotIn("replaceRedIdWithFmz200(obj.data)",source)
        self.assertNotIn("function replaceRedIdWithFmz200(obj)",source)
        self.assertIn("const parsedVideoInfo = new Map()",source)
        self.assertIn(COMMENT_MEDIA_CACHE_MARKER,source)
        self.assertIn("const pictures = current.pictures;",source)
        self.assertIn("const videos = current.videos;",source)
        self.assertIn("processCommentTree(obj.data, livePhotos, commentVideos, note_id);",source)
        self.assertIn("Xiaohongshu comment classification stack frames v1;",source)
        self.assertIn("const commentFrameTag = {};",source)
        self.assertIn(COMMENT_STACK_FRAME_MARKER,source)
        self.assertNotIn("new WeakSet()",source)


    def test_comment_node_array_classification_is_cached_and_fails_closed(self):
        source = (ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(source.count(COMMENT_NODE_ARRAY_MARKER), 1)
        self.assertEqual(optimize_comment_node_array_classification(source), source)
        start = source.index("function processCommentTree")
        end = source.index("\n\n\n/**", start)
        block = source[start:end]
        self.assertEqual(block.count("Array.isArray(current)"), 1)
        self.assertEqual(block.count("if (currentIsArray) {"), 1)
        damaged = source.replace("const currentIsArray = Array.isArray(current);", "const currentIsArray = Boolean(current);", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_comment_node_array_classification(damaged)


    def test_comment_array_length_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_array_length_cache(source),source)
        self.assertEqual(source.count(COMMENT_ARRAY_LENGTH_MARKER),1)
        start=source.index("function processCommentTree")
        end=source.index("\n\n\n/**",start)
        block=source[start:end]
        self.assertEqual(block.count("current.length"),1)
        self.assertEqual(block.count("child.length"),2)
        self.assertIn("for (let i = currentLength - 1; i >= 0; i--)",block)
        self.assertIn("for (let i = commentsLength - 1; i >= 0; i--)",block)
        self.assertIn("for (let i = subCommentsLength - 1; i >= 0; i--)",block)
        damaged=source.replace("const commentsLength = child.length;","const commentsLength = 0;",1)
        with self.assertRaisesRegex(ValueError,"array-length cache marker is stale"):
            optimize_comment_array_length_cache(damaged)

    @unittest.skipUnless(NODE,"Node required for comment array-length runtime test")
    def test_comment_tree_reads_each_traversal_array_length_once(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,track=true;
const nativeJSON=JSON,lengthReads=Object.create(null);
function wrap(value,path){
  if(Array.isArray(value)){
    const mapped=value.map((child,index)=>wrap(child,path+"["+index+"]"));
    const tracked=path==="data.comments"||path==="data.comments[0].sub_comments"||path==="data.deep_array";
    return tracked?new Proxy(mapped,{get(target,key,receiver){
      if(track&&key==="length")lengthReads[path]=(lengthReads[path]||0)+1;
      return Reflect.get(target,key,receiver);
    }}):mapped;
  }
  if(value&&typeof value==="object"){
    for(const key of Object.keys(value))value[key]=wrap(value[key],path?path+"."+key:key);
  }
  return value;
}
const trackedJSON={
  parse(value){const parsed=nativeJSON.parse(value);return p.url.includes("/note/comment/list")?wrap(parsed,""):parsed;},
  stringify(value){const previous=track;track=false;try{return nativeJSON.stringify(value);}finally{track=previous;}}
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),lengthReads}));
"""
        body={"data":{"comments":[
            {"id":"top-1","comment_type":3,"sub_comments":[{"id":"sub-1","red_id":"sub-red-1"},{"id":"sub-2","red_id":"sub-red-2"}]},
            {"id":"top-2","red_id":"top-red-2"},
            {"id":"top-3","red_id":"top-red-3"}
        ],"deep_array":[{"red_id":"array-red-1"},{"red_id":"array-red-2"}]}}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=array-length","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        comments=out["body"]["data"]["comments"]
        self.assertEqual(len(comments),3)
        self.assertEqual(comments[0]["comment_type"],2)
        self.assertEqual(comments[0]["sub_comments"][1]["fmz200"],"sub-red-2")
        self.assertEqual(out["body"]["data"]["deep_array"][1]["fmz200"],"array-red-2")
        self.assertEqual(out["lengthReads"],{
            "data.comments":1,
            "data.comments[0].sub_comments":1,
            "data.deep_array":1
        })

    def test_comment_stack_frames_use_flat_stack_without_tuple_allocations(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_stack_frame_allocation(source),source)
        self.assertIn(COMMENT_STACK_FRAME_MARKER,source)
        self.assertIn("const isCommentFrame = entry === commentFrameTag;",source)
        self.assertIn("stack.push(true, comment, commentFrameTag);",source)
        self.assertIn("stack.push(false, subComment, commentFrameTag);",source)
        self.assertNotIn("stack.push([commentFrameTag, comment, true]);",source)
        self.assertNotIn("stack.push([commentFrameTag, subComment, false]);",source)
        damaged=source.replace("stack.push(true, comment, commentFrameTag);","stack.push(comment, commentFrameTag);",1)
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_comment_stack_frame_allocation(damaged)


    def test_comment_media_property_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_media_property_cache(source),source)
        self.assertIn(COMMENT_MEDIA_CACHE_MARKER,source)
        self.assertIn("const pictureVideoId = picture?.video_id;",source)
        self.assertIn("const pictureVideoInfo = picture.video_info;",source)
        self.assertIn("const videoId = video?.video_id;",source)
        self.assertIn("const videoInfo = video?.video_info;",source)
        damaged=source.replace("const pictureVideoId = picture?.video_id;","const pictureVideoId = undefined;",1)
        with self.assertRaisesRegex(ValueError,"property-cache marker is stale"):
            optimize_comment_media_property_cache(damaged)


    def test_comment_video_info_cache_optimizer_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_comment_video_info_cache(source),source)
        damaged=source.replace("let parsed = parsedVideoInfo.get(raw);","let parsed = parsedVideoInfo.has(raw);")
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_comment_video_info_cache(damaged)


    def test_v4_function_switch_indexed_scan_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_v4_function_switch_indexed_scan(source),source)
        self.assertIn(FUNCTION_SWITCH_MARKER,source)
        self.assertIn("const functionSwitch = item?.function_switch;",source)
        self.assertIn("for (let switchIndex = 0; switchIndex < functionSwitchLength; switchIndex++)",source)
        self.assertNotIn("for (let switchItem of item.function_switch)",source)
        marker_start=source.index(FUNCTION_SWITCH_MARKER)
        damaged=source[:marker_start]+source[marker_start:].replace(
            "const switchItem = functionSwitch[switchIndex];",
            "const switchItem = functionSwitch[switchIndex + 1];",1)
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_v4_function_switch_indexed_scan(damaged)


    def test_v4_function_entry_scan_is_cached_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_v4_video_feed_function_entry_scan(source),source)
        self.assertIn("const functionEntries = item?.share_info?.function_entries;",source)
        self.assertNotIn("function_entries.some(",source)
        self.assertIn(VIDEO_ENTRY_MARKER,source)
        from optimize_xiaohongshu import VIDEO_ENTRY_INDEXED_MARKER, optimize_v4_video_feed_function_entry_indexed_scan
        self.assertIn(VIDEO_ENTRY_INDEXED_MARKER,source)
        self.assertIn("const functionEntriesLength = functionEntries?.length || 0;",source)
        self.assertIn("for (let entryIndex = 0; entryIndex < functionEntriesLength; entryIndex++)",source)
        self.assertNotIn("for (const entry of functionEntries)",source)
        self.assertEqual(optimize_v4_video_feed_function_entry_indexed_scan(source),source)
        damaged=source.replace("for (let entryIndex = 0; entryIndex < functionEntriesLength; entryIndex++)","for (let entryIndex = 0; entryIndex < functionEntries.length; entryIndex++)",1)
        with self.assertRaisesRegex(ValueError,"marker/structure drift"):
            optimize_v4_video_feed_function_entry_indexed_scan(damaged)

    def test_v3_video_feed_item_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_v3_video_feed_item_reference_cache(source),source)
        self.assertIn(VIDEO_V3_ITEM_CACHE_MARKER,source)
        self.assertIn("const mediaSaveConfig = item?.media_save_config;",source)
        self.assertIn("const functionEntries = item?.share_info?.function_entries;",source)
        self.assertIn("const firstFunctionEntry = functionEntries[0];",source)
        start=source.index('if (url.includes("/v3/note/videofeed?")) {')
        end=source.index("\n\n// 信息流 视频\nif (url.includes(\"/v4/note/videofeed\")) {",start)
        v3_block=source[start:end]
        self.assertNotIn('const addItem = {type: "video_download"};',v3_block)
        damaged=source[:start]+source[start:].replace(
            "const firstFunctionEntry = functionEntries[0];",
            "const firstFunctionEntry = functionEntries[1];",1)
        with self.assertRaisesRegex(ValueError,"reference-cache marker/structure drift"):
            optimize_v3_video_feed_item_reference_cache(damaged)

    def test_v4_video_feed_reference_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_v4_video_feed_nested_reference_cache(source),source)
        self.assertIn(VIDEO_FEED_REFERENCE_CACHE_MARKER,source)
        self.assertIn("const mediaSaveConfig = item?.media_save_config;",source)
        self.assertIn("const videoInfo = item?.video_info_v2;",source)
        self.assertIn("const videoMedia = videoInfo?.media;",source)
        self.assertIn("const videoStream = videoMedia?.stream;",source)
        self.assertIn("const itemId = item?.id;",source)
        self.assertIn("const selectedMasterUrl = selectedStream?.master_url;",source)
        damaged=source.replace("const videoMedia = videoInfo?.media;","const videoMedia = undefined;",1)
        with self.assertRaisesRegex(ValueError,"reference-cache marker/structure drift"):
            optimize_v4_video_feed_nested_reference_cache(damaged)

    @unittest.skipUnless(NODE,"Node required for v3 video-feed property-read runtime test")
    def test_v3_video_feed_reuses_references_and_defers_entry_allocation(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8"));let done,tracking=false;
const reads=p.data.map(()=>({media_save_config:0,share_info:0,function_entries:0,first_entry:0}));
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    (parsed.data||[]).forEach((item,index)=>{
      let mediaSave=item.media_save_config;
      Object.defineProperty(item,"media_save_config",{enumerable:true,configurable:true,get(){if(tracking)reads[index].media_save_config++;return mediaSave;},set(v){mediaSave=v;}});
      let shareInfo=item.share_info;
      Object.defineProperty(item,"share_info",{enumerable:true,configurable:true,get(){if(tracking)reads[index].share_info++;return shareInfo;},set(v){shareInfo=v;}});
      if(shareInfo){
        let entries=shareInfo.function_entries;
        Object.defineProperty(shareInfo,"function_entries",{enumerable:true,configurable:true,get(){if(tracking)reads[index].function_entries++;return entries;},set(v){entries=v;}});
        if(Array.isArray(entries)&&entries.length){
          let first=entries[0];
          Object.defineProperty(entries,"0",{enumerable:true,configurable:true,get(){if(tracking)reads[index].first_entry++;return first;},set(v){first=v;}});
        }
      }
    });
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read(){return null},write(){return true;}},
$request:{url:"https://edith.xiaohongshu.com/api/sns/v3/note/videofeed?cursor=fixture"},
$response:{body:nativeStringify(p)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeStringify({body:nativeParse(done.body),reads}));
'''
        body={"data":[
            {"id":"already","media_save_config":{"disable_save":True,"disable_watermark":False,"disable_weibo_cover":False},
             "share_info":{"function_entries":[{"type":"video_download"},{"type":"share"}]}},
            {"id":"first-share","media_save_config":{"disable_save":True,"disable_watermark":False,"disable_weibo_cover":False},
             "share_info":{"function_entries":[{"type":"share"},{"type":"video_download"}]}},
            {"id":"empty","media_save_config":{"disable_save":True,"disable_watermark":False,"disable_weibo_cover":False},
             "share_info":{"function_entries":[]}}
        ]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps(body),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        items=out["body"]["data"]
        self.assertEqual(items[0]["share_info"]["function_entries"],[{"type":"video_download"},{"type":"share"}])
        self.assertEqual(items[1]["share_info"]["function_entries"],[{"type":"video_download"},{"type":"share"},{"type":"video_download"}])
        self.assertEqual(items[2]["share_info"]["function_entries"],[])
        self.assertEqual(out["reads"],[
            {"media_save_config":1,"share_info":1,"function_entries":1,"first_entry":1},
            {"media_save_config":1,"share_info":1,"function_entries":1,"first_entry":2},
            {"media_save_config":1,"share_info":1,"function_entries":1,"first_entry":0}
        ])
        for item in items:
            self.assertFalse(item["media_save_config"]["disable_save"])
            self.assertTrue(item["media_save_config"]["disable_watermark"])
            self.assertTrue(item["media_save_config"]["disable_weibo_cover"])

    @unittest.skipUnless(NODE,"Node required for v4 video-feed runtime test")
    def test_v4_video_feed_download_entry_scan_preserves_behavior(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8"));let done;
const ctx={$loon:{},$persistentStore:{read(){return null},write(){return true}},
$request:{url:"https://edith.xiaohongshu.com/api/sns/v4/note/videofeed"},$response:{body:JSON.stringify(p)},
$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify(JSON.parse(done.body)));
'''
        body={"data":[
            {"id":"missing","share_info":{"function_entries":[{"type":"share"},{"type":"copy"}]}},
            {"id":"present","share_info":{"function_entries":[{"type":"video_download"},{"type":"share"}]}},
            {"id":"empty","share_info":{"function_entries":[]}},
            {"id":"absent","share_info":{}},
            {"id":"no-share"},
            {"id":"switches","function_switch":[
                {"type":"video_download","enable":False,"reason":"restricted"},
                {"type":"other","enable":False,"reason":"keep"}
            ]}
        ]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps(body),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        items=out["data"]
        self.assertEqual(items[0]["share_info"]["function_entries"],[{"type":"share"},{"type":"copy"},{"type":"video_download"}])
        self.assertEqual(items[1]["share_info"]["function_entries"],[{"type":"video_download"},{"type":"share"}])
        self.assertEqual(items[2]["share_info"]["function_entries"],[])
        self.assertEqual(items[3]["share_info"],{})
        self.assertNotIn("share_info",items[4])
        self.assertTrue(items[5]["function_switch"][0]["enable"])
        self.assertNotIn("reason",items[5]["function_switch"][0])
        self.assertFalse(items[5]["function_switch"][1]["enable"])
        self.assertEqual(items[5]["function_switch"][1]["reason"],"keep")

    def test_stream_selection_optimizer_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_stream_selection_no_closure(source),source)
        damaged=source.replace("for (let pass = 0; pass < 2; pass++)","for (let pass = 0; pass < 1; pass++)",1)
        self.assertNotEqual(damaged,source)
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_stream_selection_no_closure(damaged)

    @unittest.skipUnless(NODE,"Node required for stream selection runtime test")
    @unittest.skipUnless(NODE,"Node required for v4 video-feed property-read runtime test")
    def test_v4_video_feed_nested_references_are_read_once_per_item(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8"));let done,tracking=false;
const reads={media_save_config:0,video_info_v2:0,media:0,stream:0,h265:0,h264:0,id:0};
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    for(const item of parsed.data||[]){
      let mediaSave=item.media_save_config;
      Object.defineProperty(item,"media_save_config",{enumerable:true,configurable:true,get(){if(tracking)reads.media_save_config++;return mediaSave;},set(v){mediaSave=v;}});
      let videoInfo=item.video_info_v2;
      if(videoInfo){
        Object.defineProperty(item,"video_info_v2",{enumerable:true,configurable:true,get(){if(tracking)reads.video_info_v2++;return videoInfo;},set(v){videoInfo=v;}});
        let media=videoInfo.media;
        if(media){
          Object.defineProperty(videoInfo,"media",{enumerable:true,configurable:true,get(){if(tracking)reads.media++;return media;},set(v){media=v;}});
          let stream=media.stream;
          if(stream){
            Object.defineProperty(media,"stream",{enumerable:true,configurable:true,get(){if(tracking)reads.stream++;return stream;},set(v){stream=v;}});
            for(const key of ["h265","h264"]){
              let value=stream[key];
              Object.defineProperty(stream,key,{enumerable:true,configurable:true,get(){if(tracking)reads[key]++;return value;},set(v){value=v;}});
            }
          }
        }
      }
      let id=item.id;
      Object.defineProperty(item,"id",{enumerable:true,configurable:true,get(){if(tracking)reads.id++;return id;},set(v){id=v;}});
    }
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const store=new Map();
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:"https://edith.xiaohongshu.com/api/sns/v4/note/videofeed"},$response:{body:nativeStringify(p)},
$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeStringify({body:nativeParse(done.body),cache:nativeParse(store.get("redBookVideoFeed")),reads}));
'''
        body={"data":[{
            "id":"cache-item",
            "media_save_config":{"disable_save":True,"disable_watermark":False,"disable_weibo_cover":False},
            "share_info":{"function_entries":[{"type":"video_download"}]},
            "function_switch":[{"type":"video_download","enable":True}],
            "video_info_v2":{"media":{"stream":{
                "h265":[{"master_url":"https://video.example/cache.mp4","width":1280,"height":720,"avg_bitrate":20}],
                "h264":[]
            }}}
        }]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps(body),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        self.assertEqual(out["reads"],{
            "media_save_config":1,"video_info_v2":1,"media":1,"stream":1,"h265":1,"h264":1,"id":1
        })
        self.assertEqual(out["cache"],[{"id":"cache-item","url":"https://video.example/cache.mp4"}])
        item=out["body"]["data"][0]
        self.assertFalse(item["media_save_config"]["disable_save"])
        self.assertTrue(item["media_save_config"]["disable_watermark"])
        self.assertTrue(item["media_save_config"]["disable_weibo_cover"])

    def test_video_feed_stream_selection_preserves_codec_resolution_bitrate_priority(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done;
const ctx={$loon:{},$persistentStore:{read:k=>store.has(k)?store.get(k):null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:JSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify({body:JSON.parse(done.body),cache:JSON.parse(store.get("redBookVideoFeed"))}));
'''
        body={"data":[
            {"id":"prefer-h265","video_info_v2":{"media":{"stream":{
                "h265":[
                    {"master_url":"","width":7680,"height":4320,"avg_bitrate":999},
                    {"master_url":"https://video.example/h265-720.mp4","width":1280,"height":720,"avg_bitrate":30},
                    {"master_url":"https://video.example/h265-1080-low.mp4","width":1920,"height":1080,"avg_bitrate":40},
                    {"master_url":"https://video.example/h265-1080-high.mp4","width":1920,"height":1080,"avg_bitrate":80}
                ],
                "h264":[{"master_url":"https://video.example/h264-4k.mp4","width":3840,"height":2160,"avg_bitrate":999}]
            }}}},
            {"id":"h264-fallback","video_info_v2":{"media":{"stream":{
                "h265":[],
                "h264":[
                    {"master_url":"https://video.example/h264-720.mp4","width":1280,"height":720,"avg_bitrate":20},
                    {"master_url":"https://video.example/h264-1080.mp4","width":1920,"height":1080,"avg_bitrate":40}
                ]
            }}}},
            {"id":"invalid-h265-fallback","video_info_v2":{"media":{"stream":{
                "h265":[{"width":7680,"height":4320,"avg_bitrate":999}],
                "h264":[{"master_url":"https://video.example/h264-valid.mp4","width":640,"height":360,"avg_bitrate":5}]
            }}}},
            {"id":"stable-tie","video_info_v2":{"media":{"stream":{
                "h265":[
                    {"master_url":"https://video.example/first-tie.mp4","width":1920,"height":1080,"avg_bitrate":50},
                    {"master_url":"https://video.example/second-tie.mp4","width":1920,"height":1080,"avg_bitrate":50}
                ],"h264":[]
            }}}}
        ]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?cursor=fixture","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        self.assertEqual([item["url"] for item in out["cache"]],[
            "https://video.example/h265-1080-high.mp4",
            "https://video.example/h264-1080.mp4",
            "https://video.example/h264-valid.mp4",
            "https://video.example/first-tie.mp4"
        ])

    def test_video_save_cache_optimizer_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_video_save_cache_lookup(source),source)
        damaged=source.replace("if (item.id === noteId)","if (item.other_id === noteId)",1)
        self.assertNotEqual(damaged,source)
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_video_save_cache_lookup(damaged)

    def test_video_save_lazy_cache_parse_optimizer_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_video_save_lazy_cache_parse(source),source)
        damaged=source.replace('if (noteId !== "") {','if (noteId === "") {',1)
        with self.assertRaisesRegex(ValueError,"lazy-cache marker is stale"):
            optimize_video_save_lazy_cache_parse(damaged)

    @unittest.skipUnless(NODE,"Node required for video-save cache runtime test")
    def test_video_save_cache_reverse_lookup_stops_at_last_duplicate(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map(Object.entries(p.store));let done,cacheIndexReads=0,cacheReads=0,cacheParseCalls=0;
const nativeJSON=JSON;
const trackedJSON={
  parse(value){if(value===store.get("redBookVideoFeed"))cacheParseCalls++;const parsed=nativeJSON.parse(value);if(Array.isArray(parsed))return new Proxy(parsed,{get(target,key,receiver){
    if(typeof key==="string"&&/^\d+$/.test(key))cacheIndexReads++;
    return Reflect.get(target,key,receiver);
  }});return parsed;},
  stringify(value){return nativeJSON.stringify(value);}
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>{if(k==="redBookVideoFeed")cacheReads++;return store.has(k)?store.get(k):null;},write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),cacheIndexReads,cacheReads,cacheParseCalls}));
'''
        cache=[
            {"id":"target","url":"https://video.example/first.mp4"},
            {"id":"other","url":"https://video.example/other.mp4"},
            {"id":"target","url":"https://video.example/last.mp4"},
            {"id":"tail","url":"https://video.example/tail.mp4"}
        ]
        body={"data":{"note_id":"target","download_url":"https://video.example/original.mp4","disable":True,"msg":"restricted"}}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v10/note/video/save","body":body,
            "store":{"redBookVideoFeed":json.dumps(cache)}
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout);data=out["body"]["data"]
        self.assertEqual(data["download_url"],"https://video.example/last.mp4")
        self.assertNotIn("disable",data)
        self.assertNotIn("msg",data)
        self.assertEqual(data["status"],2)
        self.assertEqual(out["cacheIndexReads"],2)
        self.assertEqual(out["cacheReads"],1)
        self.assertEqual(out["cacheParseCalls"],1)

        empty_body={"data":{"note_id":"","disable":True,"msg":"restricted"}}
        empty_run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v10/note/video/save","body":empty_body,
            "store":{"redBookVideoFeed":"not-json"}
        }),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(empty_run.returncode,0,empty_run.stderr)
        empty_out=json.loads(empty_run.stdout)
        self.assertEqual(empty_out["cacheReads"],0)
        self.assertEqual(empty_out["cacheParseCalls"],0)
        self.assertEqual(empty_out["body"]["data"]["status"],2)
        self.assertNotIn("disable",empty_out["body"]["data"])

    @unittest.skipUnless(NODE,"Node required for comment runtime test")
    def test_comment_tree_single_pass_preserves_cleanup_and_media_caches(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,parseCalls=0,weakSetConstructCount=0,mapGetCount=0,mapHasCount=0;
const nativeJSON=JSON,NativeWeakSet=WeakSet;
class CountedWeakSet extends NativeWeakSet { constructor(...args){super(...args);weakSetConstructCount++;} }
const trackedJSON={parse(value){parseCalls++;return nativeJSON.parse(value);},stringify(value){return nativeJSON.stringify(value);}};
class CountedMap extends Map { get(key){mapGetCount++;return super.get(key);} has(key){mapHasCount++;return super.has(key);} }
const ctx={JSON:trackedJSON,WeakSet:CountedWeakSet,Map:CountedMap,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),store:Object.fromEntries(store),parseCalls,weakSetConstructCount,mapGetCount,mapHasCount}));
'''
        video_info=json.dumps({"stream":{"h265":[
            {"master_url":"https://video.example/2160.mp4","width":3840,"height":2160}
        ]}})
        deep={"red_id":"deep-400"}
        for depth in range(400):
            deep={"nested":deep,"red_id":f"deep-{depth}"}
        body={"data":{"red_id":"root","deep":deep,"comments":[{
            "id":"top","note_id":"note-1","red_id":"top-red","comment_type":3,"media_source_type":1,
            "pictures":[{"video_id":"live-1","video_info":video_info}],
            "videos":[{"video_id":"comment-video-1","video_info":video_info}],
            "sub_comments":[{"id":"sub","red_id":"sub-red","comment_type":3,"pictures":[
                {"video_id":"live-2","video_info":video_info}
            ],"nested":{"red_id":"deep-red"},"sub_comments":[{"comment_type":3,"pictures":[{"video_id":"deep-live","video_info":video_info}]}]}]
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
        self.assertEqual(sub["sub_comments"][0]["comment_type"],3)
        live=json.loads(out["store"]["fmz200.xiaohongshu.comments.rsp"])
        videos=json.loads(out["store"]["fmz200.xiaohongshu.comments.videos.rsp"])
        self.assertEqual([x["videId"] for x in live["livePhotos"]],["live-1","live-2"])
        self.assertTrue(live["livePhotos"][0]["videoUrl"].startswith("https://video.example/"))
        self.assertEqual(videos["videos"][0]["videId"],"comment-video-1")
        self.assertEqual(videos["videos"][0]["videoUrl"],live["livePhotos"][0]["videoUrl"])
        self.assertEqual(out["parseCalls"],2)
        self.assertEqual(out["mapGetCount"],3)
        self.assertEqual(out["mapHasCount"],0)
        self.assertEqual(out["weakSetConstructCount"],0)
        cursor=out["body"]["data"]["deep"]
        depth=0
        while isinstance(cursor,dict):
            self.assertNotIn("red_id",cursor)
            cursor=cursor.get("nested")
            depth+=1
        self.assertEqual(depth,401)
    def test_video_feed_does_not_log_each_cached_item(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertNotIn("console.log(`[缓存] ID:",source)
        self.assertIn('$.setdata(JSON.stringify(videoData), "redBookVideoFeed");',source)
        self.assertIn("const selectedStream = selectBestStream(h265List, h264List);",source)
    def test_comment_tree_walk_avoids_object_keys_temporary_arrays(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertNotIn("Object.keys(current)",source)
        self.assertIn("for (const key in current)",source)
        self.assertNotIn("const visited = new WeakSet()",source)
        self.assertNotIn("visited.has(current)",source)
        self.assertIn("Xiaohongshu parsed JSON comment tree without visited WeakSet v1;",source)
        self.assertIn("Object.prototype.hasOwnProperty.call(current, key)",source)
        self.assertIn("processCommentTree(obj.data, livePhotos, commentVideos, note_id);",source)
        self.assertIn("Xiaohongshu comment classification stack frames v1;",source)
        self.assertIn("const commentFrameTag = {};",source)
        self.assertIn(COMMENT_STACK_FRAME_MARKER,source)
        self.assertNotIn("new WeakSet()",source)

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
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map(Object.entries(p.store||{}));let done,imageArrayReads=0,trackImageArrayReads=true;
const nativeJSON=JSON;
const trackedJSON={
  parse(value){
    const parsed=nativeJSON.parse(value);
    if(p.url.includes("/note/imagefeed?")||p.url.includes("/note/feed?")){
      const images=parsed?.data?.[0]?.note_list?.[0]?.images_list;
      if(Array.isArray(images)) parsed.data[0].note_list[0].images_list=new Proxy(images,{
        get(target,property,receiver){
          if(trackImageArrayReads&&typeof property==="string"&&/^\d+$/.test(property)) imageArrayReads++;
          return Reflect.get(target,property,receiver);
        }
      });
    }
    return parsed;
  },
  stringify(value){
    const previous=trackImageArrayReads;trackImageArrayReads=false;
    try{return nativeJSON.stringify(value);}finally{trackImageArrayReads=previous;}
  }
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.has(k)?store.get(k):null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify({body:nativeJSON.parse(done.body),store:Object.fromEntries(store),imageArrayReads}));
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
        self.assertEqual(out["imageArrayReads"],1)

    @unittest.skipUnless(NODE,"Node required for runtime test")
    def test_imagefeed_cache_and_enhancement_share_one_root_array_traversal(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,imageArrayReads=0,track=true;
const nativeJSON=JSON;
const trackedJSON={
  parse(value){const parsed=nativeJSON.parse(value);if(p.url.includes("/note/imagefeed?")){
    const images=parsed?.data?.[0]?.note_list?.[0]?.images_list;
    if(Array.isArray(images))parsed.data[0].note_list[0].images_list=new Proxy(images,{get(target,key,receiver){
      if(track&&typeof key==="string"&&/^\d+$/.test(key))imageArrayReads++;return Reflect.get(target,key,receiver);
    }});
  }return parsed;},
  stringify(value){const prior=track;track=false;try{return nativeJSON.stringify(value);}finally{track=prior;}}
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify({body:nativeJSON.parse(done.body),store:Object.fromEntries(store),imageArrayReads}));
"""
        original="https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"
        body={"data":[{"note_list":[{"images_list":[
            {"url":original,"live_photo_file_id":"file-1","live_photo":{"media":{"video_id":"video-1","stream":{"h265":[{"master_url":"https://video.example/one.mp4"}]}}}},
            {"url":original,"live_photo_file_id":"file-2","live_photo":{"media":{"video_id":"video-2","stream":{"h265":[{"master_url":"https://video.example/two.mp4"}]}}},"nested":{
                "live_photo_file_id":"nested-file","live_photo":{"media":{"video_id":"nested-video","stream":{"h265":[{"master_url":"https://video.example/nested.mp4"}]}}}
            }}
        ]}]}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=two-items","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        images=out["body"]["data"][0]["note_list"][0]["images_list"]
        self.assertEqual(out["imageArrayReads"],2)
        self.assertTrue(all("w/2160/format" in item["url"] for item in images))
        self.assertEqual(json.loads(out["store"]["fmz200.xiaohongshu.feed.rsp"]),[
            {"live_photo_file_id":"file-1","video_id":"video-1","url":"https://video.example/one.mp4"},
            {"live_photo_file_id":"file-2","video_id":"video-2","url":"https://video.example/two.mp4"}
        ])

    @unittest.skipUnless(NODE,"Node required for runtime test")
    def test_original_quality_replacement_remains_single_and_live_photo_cache_is_unchanged(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map([["fmz200.xiaohongshu.imageQuality","original"]]);let done;
const ctx={$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:JSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(JSON.stringify({body:JSON.parse(done.body),store:Object.fromEntries(store)}));
"""
        original="https://img.example/a.jpg?imageView2/2/w/1080/format/jpg&redImage/frame/0"
        second="https://img.example/b.jpg?imageView2/2/w/1080/format/jpg&redImage/frame/0"
        body={"data":[{"note_list":[{"images_list":[
            {"url":original,"live_photo_file_id":"file-1","live_photo":{"media":{"video_id":"video-1","stream":{"h265":[{"master_url":"https://video.example/live.mp4"}]}}}},
            {"url":second}
        ]}]}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=original-mode","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        images=out["body"]["data"][0]["note_list"][0]["images_list"]
        self.assertIn("imageView2/0/format/png",images[0]["url"])
        self.assertIn("imageView2/2/w/1080/format",images[1]["url"])
        self.assertEqual(json.loads(out["store"]["fmz200.xiaohongshu.feed.rsp"]),[
            {"live_photo_file_id":"file-1","video_id":"video-1","url":"https://video.example/live.mp4"}
        ])

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


    def test_imagefeed_array_frame_length_cache_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_imagefeed_array_length_cache(source),source)
        self.assertEqual(source.count(IMAGE_ARRAY_LENGTH_MARKER),1)
        self.assertIn("length:Array.isArray(images)?images.length:0",source)
        self.assertIn("if(frame.index>=frame.length)",source)
        self.assertEqual(source.count("length:Array.isArray(child)?child.length:0"),2)
        damaged=source.replace("if(frame.index>=frame.length)", "if(frame.index>=value.length)", 1)
        with self.assertRaisesRegex(ValueError,"marker is stale"):
            optimize_imagefeed_array_length_cache(damaged)

    @unittest.skipUnless(NODE,"Node required for image traversal runtime test")
    def test_imagefeed_array_lengths_are_read_once_per_array_frame(self):
        runner=r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();let done,track=true;
const lengthReads=Object.create(null),nativeJSON=JSON;
function wrapArrays(value,path){
  if(Array.isArray(value)){
    const wrapped=value.map((child,index)=>wrapArrays(child,path+"["+index+"]"));
    return new Proxy(wrapped,{get(target,key,receiver){
      if(track&&key==="length")lengthReads[path]=(lengthReads[path]||0)+1;
      return Reflect.get(target,key,receiver);
    }});
  }
  if(value&&typeof value==="object"){
    for(const key of Object.keys(value))value[key]=wrapArrays(value[key],path+"."+key);
  }
  return value;
}
const trackedJSON={
  parse(value){
    const parsed=nativeJSON.parse(value);
    if(p.url.includes("/note/imagefeed?")){
      const images=parsed?.data?.[0]?.note_list?.[0]?.images_list;
      if(Array.isArray(images))parsed.data[0].note_list[0].images_list=wrapArrays(images,"root");
    }
    return parsed;
  },
  stringify(value){const previous=track;track=false;try{return nativeJSON.stringify(value);}finally{track=previous;}}
};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeJSON.stringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeJSON.stringify({body:nativeJSON.parse(done.body),lengthReads}));
"""
        original="https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"
        body={"data":[{"note_list":[{"images_list":[
            {"url":original,"nested":[{"url":original},{"url":original}]},
            {"url":original}
        ]}]}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=array-length","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=True,timeout=10)
        out=json.loads(run.stdout)
        images=out["body"]["data"][0]["note_list"][0]["images_list"]
        self.assertIn("w/2160/format",images[0]["url"])
        self.assertIn("w/2160/format",images[0]["nested"][0]["url"])
        self.assertIn("w/2160/format",images[1]["url"])
        self.assertEqual(out["lengthReads"],{"root":1,"root[0].nested":1})


    def test_v4_feed_array_length_snapshot_is_idempotent_and_fails_closed(self):
        source=(ROOT/"scripts/xiaohongshu/xiaohongshu.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_v4_feed_array_length_snapshot(source),source)
        self.assertIn(V4_FEED_ARRAY_LENGTH_MARKER,source)
        self.assertIn("const videoDataLength = videoDataSource?.length || 0;",source)
        self.assertIn("for (let videoIndex = 0; videoIndex < videoDataLength; videoIndex++)",source)
        self.assertIn("const functionSwitchLength = functionSwitch?.length || 0;",source)
        self.assertIn("for (let switchIndex = 0; switchIndex < functionSwitchLength; switchIndex++)",source)
        damaged=source.replace("const videoDataLength = videoDataSource?.length || 0;","const videoDataLength = 0;",1)
        with self.assertRaisesRegex(ValueError,"array-length marker is stale"):
            optimize_v4_feed_array_length_snapshot(damaged)

    @unittest.skipUnless(NODE,"Node required for v4 feed array-length runtime test")
    def test_v4_feed_and_function_switch_lengths_are_read_once(self):
        runner=r'''
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync("scripts/xiaohongshu/xiaohongshu.js","utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
let done,tracking=false;const reads={data:0,functionSwitch:0};
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    if(p.url.includes("/v4/note/videofeed")&&Array.isArray(parsed.data)){
      const item=parsed.data[0];
      if(item&&Array.isArray(item.function_switch)){
        item.function_switch=new Proxy(item.function_switch,{get(target,key,receiver){if(tracking&&key==="length")reads.functionSwitch++;return Reflect.get(target,key,receiver);}});
      }
      parsed.data=new Proxy(parsed.data,{get(target,key,receiver){if(tracking&&key==="length")reads.data++;return Reflect.get(target,key,receiver);}});
    }
    tracking=true;return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const store=new Map();
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeStringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});
process.stdout.write(nativeStringify({body:nativeParse(done.body),reads,cache:nativeParse(store.get("redBookVideoFeed"))}));
'''
        body={"data":[{"id":"one","function_switch":[{"type":"video_download","enable":False,"reason":"disabled"}],
            "share_info":{"function_entries":[{"type":"share"}]},
            "video_info_v2":{"media":{"stream":{"h265":[{"master_url":"https://video.example/one.mp4","width":1280,"height":720,"avg_bitrate":20}],"h264":[]}}}},
            {"id":"two","function_switch":[],"share_info":{"function_entries":[{"type":"video_download"}]},
            "video_info_v2":{"media":{"stream":{"h265":[],"h264":[]}}}}]}
        run=subprocess.run([NODE,"-e",runner],input=json.dumps({"url":"https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?cursor=length","body":body}),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        out=json.loads(run.stdout)
        self.assertEqual(out["reads"],{"data":1,"functionSwitch":1})
        item=out["body"]["data"][0]
        self.assertTrue(item["function_switch"][0]["enable"])
        self.assertNotIn("reason",item["function_switch"][0])
        self.assertEqual(item["share_info"]["function_entries"],[{"type":"share"},{"type":"video_download"}])
        self.assertEqual(out["cache"],[{"id":"one","url":"https://video.example/one.mp4"}])

class XiaohongshuFeedNestedLoopPropertyCacheTests(unittest.TestCase):
    def test_feed_nested_loop_cache_markers_and_legacy_scans(self):
        from optimize_xiaohongshu import FEED_NESTED_LOOP_MARKER, optimize_feed_nested_loop_property_cache
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(FEED_NESTED_LOOP_MARKER), 3)
        self.assertEqual(optimize_feed_nested_loop_property_cache(source), source)
        self.assertIn("const adsGroupLength = adsGroups?.length || 0;", source)
        self.assertIn("const noteList = firstFeedPage?.note_list;", source)
        self.assertIn("const functionSwitchLength = functionSwitch?.length || 0;", source)
        self.assertIn("const videoFeedLength = videoFeed?.length || 0;", source)
        self.assertNotIn("options.some(item => item.key === 'copy')", source)
        self.assertNotIn("item.function_switch.forEach(", source)
        damaged = source.replace("const noteList = firstFeedPage?.note_list;", "const noteList = obj.data[0].note_list;", 1)
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_feed_nested_loop_property_cache(damaged)

    @unittest.skipUnless(NODE, "Node.js is required for feed array-access counter tests")
    def test_imagefeed_nested_arrays_are_length_read_once_and_mutations_preserved(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
let done,tracking=false;const reads={feedData:0,noteList:0,functionSwitch:0,options:0};
const trackedJSON={parse(raw){const root=nativeParse(raw);if(p.url.includes("/note/imagefeed")){
 const wrap=(array,key)=>new Proxy(array,{get(target,prop,receiver){if(tracking&&prop==="length")reads[key]++;return Reflect.get(target,prop,receiver);}});
 root.data=wrap(root.data,"feedData");root.data[0].note_list=wrap(root.data[0].note_list,"noteList");
 for(const item of root.data[0].note_list){item.function_switch=wrap(item.function_switch,"functionSwitch");item.note_text_press_options=wrap(item.note_text_press_options,"options");}
 }tracking=true;return root;},stringify(value){tracking=false;return nativeStringify(value);}};
const store=new Map();const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read:k=>store.get(k)||null,write:(v,k)=>(store.set(k,v),true)},
$request:{url:p.url},$response:{body:nativeStringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});process.stdout.write(nativeStringify({body:nativeParse(done.body),reads}));
""";
        body={"data":[{"note_list":[
            {"media_save_config":{},"share_info":{"function_entries":[{"type":"share"}]},
             "function_switch":[{"type":"image_download","enable":False}],
             "note_text_press_options":[{"key":"share"}],"hash_tag":[{"type":"interact_vote"},{"type":"normal"}],"images_list":[]},
            {"media_save_config":{},"share_info":{"function_entries":[{"type":"video_download"}]},
             "function_switch":[{"type":"other"}],"note_text_press_options":[{"key":"copy"}],"hash_tag":[],"images_list":[]}
        ]}]}
        run=subprocess.run([NODE,"-e",runner,str(SCRIPT)],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/web/v1/note/imagefeed?cursor=counter","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        # Array.prototype.push reads the target array length once when inserting the missing copy option.
        self.assertEqual(result["reads"],{"feedData":1,"noteList":1,"functionSwitch":2,"options":3})
        first=result["body"]["data"][0]["note_list"][0]
        self.assertTrue(first["media_save_config"]["disable_watermark"])
        self.assertTrue(first["function_switch"][0]["enable"])
        self.assertEqual(first["note_text_press_options"],[{"key":"share"},{"key":"copy","extra":""}])
        self.assertEqual([tag["type"] for tag in first["hash_tag"]],["normal"])

    @unittest.skipUnless(NODE, "Node.js is required for feed array-access counter tests")
    def test_splash_nested_arrays_are_length_read_once_and_mutations_preserved(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const p=JSON.parse(fs.readFileSync(0,"utf8")),nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
let done,tracking=false;const reads={groups:0,ads:0};
const trackedJSON={parse(raw){const root=nativeParse(raw);const wrap=(array,key)=>new Proxy(array,{get(target,prop,receiver){if(tracking&&prop==="length")reads[key]++;return Reflect.get(target,prop,receiver);}});
 root.data.ads_groups=wrap(root.data.ads_groups,"groups");for(const group of root.data.ads_groups)group.ads=wrap(group.ads,"ads");tracking=true;return root;},
 stringify(value){tracking=false;return nativeStringify(value);}};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read(){return null},write(){return true;}},
$request:{url:p.url},$response:{body:nativeStringify(p.body)},$done:v=>done=v,console:{log(){},warn(){},error(){}}};
vm.runInNewContext(source,ctx,{timeout:5000});process.stdout.write(nativeStringify({body:nativeParse(done.body),reads}));
""";
        body={"data":{"ads_groups":[{"ads":[{},{}]},{"ads":[{}]}]}}
        run=subprocess.run([NODE,"-e",runner,str(SCRIPT)],input=json.dumps({
            "url":"https://edith.xiaohongshu.com/api/sns/web/v1/system_service/splash_config","body":body
        }),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        self.assertEqual(result["reads"],{"groups":1,"ads":2})
        for group in result["body"]["data"]["ads_groups"]:
            self.assertEqual(group["start_time"],3818332800)
            for ad in group["ads"]:
                self.assertEqual(ad["end_time"],3818419199)




class XiaohongshuV4FunctionEntryIndexedScanTests(unittest.TestCase):
    def test_indexed_scan_optimizer_is_idempotent_and_fails_closed(self):
        from optimize_xiaohongshu import VIDEO_ENTRY_INDEXED_MARKER, optimize_v4_video_feed_function_entry_indexed_scan
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(VIDEO_ENTRY_INDEXED_MARKER), 1)
        self.assertEqual(optimize_v4_video_feed_function_entry_indexed_scan(source), source)
        self.assertIn("const functionEntriesLength = functionEntries?.length || 0;", source)
        self.assertIn("for (let entryIndex = 0; entryIndex < functionEntriesLength; entryIndex++)", source)
        self.assertNotIn("for (const entry of functionEntries)", source)
        marker_start = source.index(VIDEO_ENTRY_INDEXED_MARKER)
        v4_block = source[marker_start:]
        damaged_block = v4_block.replace("const functionEntriesLength = functionEntries?.length || 0;", "const functionEntriesLength = 0;", 1)
        damaged = source[:marker_start] + damaged_block
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_v4_video_feed_function_entry_indexed_scan(damaged)

    @unittest.skipUnless(NODE, "Node.js is required for function-entry indexed scan counter tests")
    def test_function_entries_use_cached_length_without_array_iterator(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const payload=JSON.parse(fs.readFileSync(0,"utf8"));
let done,tracking=false;
const counts={length:0,iterator:0};
const trackedJSON={parse(raw){
  const root=nativeParse(raw);
  for(const item of root.data){
    const entries=item.share_info && item.share_info.function_entries;
    if(!Array.isArray(entries)) continue;
    item.share_info.function_entries=new Proxy(entries,{get(target,prop,receiver){
      if(tracking&&prop==="length") counts.length++;
      if(tracking&&prop===Symbol.iterator) counts.iterator++;
      return Reflect.get(target,prop,receiver);
    }});
  }
  tracking=true;return root;
},stringify(value){tracking=false;return nativeStringify(value);}};
const ctx={JSON:trackedJSON,$loon:{},$persistentStore:{read(){return null},write(){return true}},
__stopTrack(){tracking=false;},
$request:{url:"https://edith.xiaohongshu.com/api/sns/v4/note/videofeed"},
$response:{body:nativeStringify(payload)},$done:value=>done=value,console:{log(){},warn(){},error(){}}};
let instrumented=source.replace("      // 提取最佳视频流","      globalThis.__stopTrack();\n      // 提取最佳视频流");
vm.runInNewContext(instrumented,ctx,{timeout:5000});
const out=nativeParse(done.body);
process.stdout.write(nativeStringify({counts,entries:out.data.map(x=>x.share_info.function_entries)}));
"""
        body={"data":[
            {"share_info":{"function_entries":[{"type":"share"},{"type":"video_download"},{"type":"copy"}]}}
        ]}
        run=subprocess.run([NODE,"-e",runner,str(SCRIPT)],input=json.dumps(body),cwd=ROOT,capture_output=True,text=True,check=False,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        # The existing download-entry scan performs one explicit length read.
        self.assertEqual(result["counts"],{"length":1,"iterator":0})
        self.assertEqual(result["entries"][0],[{"type":"share"},{"type":"video_download"},{"type":"copy"}])

