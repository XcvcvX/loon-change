import json
import shutil
import subprocess
import sys
import unittest

sys.setrecursionlimit(10000)
from pathlib import Path

from optimize_xiaohongshu_rstore import LOCAL, REMOTE, MARKER, optimize_source, rewrite_plugin, XIAOHONGSHU_V4_FUNCTION_ENTRY_MARKER, optimize_v4_function_entry_scan, VIDEO_SAVE_LOOKUP_MARKER, optimize_video_save_lookup

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts/xiaohongshu/xiaohongshu-rstore.js"
NODE = shutil.which("node")


class RStoreXiaohongshuOptimizerTests(unittest.TestCase):
    def test_generated_script_is_marked_and_idempotent(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(MARKER, source)
        optimized = optimize_source(source)
        self.assertIn("if (!$response.body) { $done({}); } else {", optimized)
        self.assertEqual(optimize_source(optimized), optimized)
        self.assertIn("// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1", source)
        self.assertIn("imageEnhance(images_list, livePhotoCache)", source)
        self.assertNotIn("for (const image of images_list)", source)
        self.assertIn("if (!$response.body) { $done({}); } else {", optimized)
        self.assertNotIn("imageEnhance(JSON.stringify(images_list))", source)
        self.assertIn("appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)", source)
        self.assertIn("const byFileId = new Map()", source)
        self.assertIn("function cleanCommentsAndCollectLivePhotos(data)", source)
        self.assertIn("Xiaohongshu flat comment stack frames v2;", source)
        self.assertIn("const commentFrameTag = {};", source)
        self.assertIn("stack.push(comment, commentFrameTag, true)", source)
        self.assertIn("stack.push(subComment, commentFrameTag, false)", source)
        self.assertNotIn("stack.push([commentFrameTag", source)
        self.assertNotIn("Array.isArray(entry) && entry[0] === commentFrameTag", source)
        self.assertNotIn("new WeakSet()", source)
        self.assertIn("const videoInfoCache = new Map()", source)
        self.assertIn("// loon-change: Xiaohongshu comment video-info cache single lookup v1", source)
        self.assertIn("let picObj = videoInfoCache.get(rawVideoInfo);", source)
        self.assertNotIn("videoInfoCache.has(rawVideoInfo)", source)
        self.assertIn("let commentPictures = null;", source)
        self.assertIn("commentPictures = current.pictures;", source)
        self.assertIn('const child = isCommentFrame && key === "pictures" ? commentPictures : current[key];', source)
        self.assertEqual(source.count(XIAOHONGSHU_V4_FUNCTION_ENTRY_MARKER), 1)
        self.assertIn("const functionEntryCount = functionEntries.length;", source)
        self.assertNotIn("functionEntries.some(", source)
        self.assertIn("// loon-change: Xiaohongshu parsed JSON tree traversal without visited WeakSet v1;", source)
        self.assertNotIn("const visited = new WeakSet()", source)
        self.assertNotIn("visited.has(current)", source)
        self.assertNotIn(".filter(v => !!v.master_url && !!v.height).sort(", source)
        self.assertNotIn("let newItems = []", source)

    def test_exactly_ten_live_rstore_triggers_are_routed_to_local_script(self):
        plugin = (ROOT / "allAdRewrite.plugin").read_text(encoding="utf-8")
        self.assertEqual(plugin.count(REMOTE), 0)
        self.assertEqual(plugin.count(LOCAL), 10)
        routed = rewrite_plugin(plugin)
        self.assertEqual(routed.count(LOCAL), 10)
        self.assertNotIn(REMOTE, routed)
        self.assertEqual(rewrite_plugin(routed), routed)

    def test_trigger_count_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected 10"):
            rewrite_plugin("[Script]\nhttp-response ^https://example.invalid script-path=" + REMOTE + "\n")

    def test_imagefeed_single_traversal_optimizer_is_idempotent_and_fails_closed(self):
        from optimize_xiaohongshu_rstore import IMAGE_FEED_MARKER, optimize_imagefeed_single_traversal
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(IMAGE_FEED_MARKER, source)
        self.assertEqual(optimize_imagefeed_single_traversal(source), source)
        damaged = source.replace("function imageEnhance(images, livePhotoCache)", "function imageEnhance(images)")
        with self.assertRaisesRegex(ValueError, "single-traversal image helper drifted"):
            optimize_imagefeed_single_traversal(damaged)

    def test_v4_function_entry_scan_is_indexed_idempotent_and_fails_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(optimize_v4_function_entry_scan(source), source)
        self.assertEqual(source.count(XIAOHONGSHU_V4_FUNCTION_ENTRY_MARKER), 1)
        self.assertNotIn("functionEntries.some(", source)
        damaged = source.replace("const functionEntryCount = functionEntries.length;", "const functionEntryCount = 0;", 1)
        with self.assertRaisesRegex(ValueError, "function-entry scan structure drift"):
            optimize_v4_function_entry_scan(damaged)

    def test_video_save_lookup_caches_note_id_and_uses_indexed_early_exit(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(source.count(VIDEO_SAVE_LOOKUP_MARKER), 1)
        self.assertIn("const saveData = obj.data;", source)
        self.assertIn("const noteId = saveData?.note_id;", source)
        self.assertIn("const videoFeedLength = videoFeed?.length || 0;", source)
        self.assertIn("for (let read = 0; read < videoFeedLength; read++)", source)
        self.assertIn("if (item.id === noteId)", source)
        self.assertIn("saveData.download_url = item.url;\n        break;", source)
        self.assertNotIn("obj.data.note_id", source)
        self.assertNotIn("obj.data.download_url", source)
        self.assertNotIn("for (let item of videoFeed)", source)
        self.assertEqual(optimize_video_save_lookup(source), source)
        damaged = source.replace("const noteId = saveData?.note_id;", "const noteId = null;", 1)
        with self.assertRaisesRegex(ValueError, "video-save lookup structure drift"):
            optimize_video_save_lookup(damaged)
        self.assertEqual(optimize_source(source), source)

    def test_array_filters_and_video_sort_are_removed_from_hot_paths(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("compactInPlace(obj.data.items", source)
        self.assertIn("compactInPlace(item.hash_tag", source)
        self.assertIn("for (const stream of h265List)", source)
        self.assertIn("let selectedHeight = -Infinity;", source)
        self.assertIn("const streamHeight = Number(stream.height);", source)
        self.assertIn("if (streamHeight > selectedHeight)", source)
        self.assertNotIn("Number(selectedStream.height)", source)
        self.assertNotIn("h265List.filter(", source)
        self.assertNotIn("obj.data = newItems", source)


@unittest.skipUnless(NODE, "Node.js is required for R-Store Xiaohongshu runtime tests")
class RStoreXiaohongshuRuntimeTests(unittest.TestCase):
    def run_script(self, url, body, store=None, raw_body=None, track_video_save_lookup_reads=False):
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const store = new Map(Object.entries(payload.store || {}));
let doneResult;
let imageArrayReads = 0;
let trackImageArrayReads = true;
let weakSetConstructCount = 0;
let mapGetCount = 0;
let mapHasCount = 0;
let videoDataReads = 0;
let videoNoteIdReads = 0;
let videoFeedLengthReads = 0;
let videoFeedIndexReads = 0;
let trackVideoSaveReads = false;
const NativeMap = Map;
class CountedMap extends NativeMap {
  get(key) {
    mapGetCount++;
    return super.get(key);
  }
  has(key) {
    mapHasCount++;
    return super.has(key);
  }
}
const NativeWeakSet = WeakSet;
class CountedWeakSet extends NativeWeakSet {
  constructor(...args) {
    super(...args);
    weakSetConstructCount++;
  }
}
const context = {
  $loon: {},
  $persistentStore: {
    read(key) { return store.has(key) ? store.get(key) : null; },
    write(value, key) { store.set(key, value); return true; }
  },
  $request: {url: payload.url},
  $response: {body: payload.rawBody === undefined ? JSON.stringify(payload.body) : payload.rawBody},
  $done(value) { doneResult = value; },
  WeakSet: CountedWeakSet,
  Map: CountedMap,
  JSON: {
    parseCount: 0,
    parse(value) {
      this.parseCount++;
      let parsed = JSON.parse(value);
      if (payload.trackVideoSaveLookupReads && parsed && !Array.isArray(parsed) && parsed.data && !trackVideoSaveReads) {
        let currentData = parsed.data;
        Object.defineProperty(parsed, "data", {
          enumerable: true, configurable: true,
          get() { if (trackVideoSaveReads) videoDataReads++; return currentData; },
          set(value) { currentData = value; }
        });
        let currentNoteId = currentData.note_id;
        Object.defineProperty(currentData, "note_id", {
          enumerable: true, configurable: true,
          get() { if (trackVideoSaveReads) videoNoteIdReads++; return currentNoteId; },
          set(value) { currentNoteId = value; }
        });
        trackVideoSaveReads = true;
      } else if (payload.trackVideoSaveLookupReads && Array.isArray(parsed) && trackVideoSaveReads) {
        const target = parsed;
        parsed = new Proxy(target, {
          get(object, key, receiver) {
            if (trackVideoSaveReads && key === "length") videoFeedLengthReads++;
            if (trackVideoSaveReads && typeof key === "string" && /^\d+$/.test(key)) videoFeedIndexReads++;
            return Reflect.get(object, key, receiver);
          }
        });
      }
      if (payload.url.includes("/note/imagefeed") || payload.url.includes("/note/feed")) {
        const images = parsed?.data?.[0]?.note_list?.[0]?.images_list;
        if (Array.isArray(images)) {
          parsed.data[0].note_list[0].images_list = new Proxy(images, {
            get(target, property, receiver) {
              if (trackImageArrayReads && typeof property === "string" && /^\d+$/.test(property)) {
                imageArrayReads++;
              }
              return Reflect.get(target, property, receiver);
            }
          });
        }
      }
      return parsed;
    },
    stringify(value) {
      const previous = trackImageArrayReads;
      const previousVideoTracking = trackVideoSaveReads;
      trackImageArrayReads = false;
      trackVideoSaveReads = false;
      try { return JSON.stringify(value); }
      finally {
        trackImageArrayReads = previous;
        trackVideoSaveReads = previousVideoTracking;
      }
    }
  },
  console: {log() {}, warn() {}, error() {}}
};
vm.runInNewContext(source, context, {timeout: 5000});
process.stdout.write(JSON.stringify({
  doneResult,
  parseCount: context.JSON.parseCount,
  imageArrayReads,
  weakSetConstructCount,
  mapGetCount,
  mapHasCount,
  videoDataReads,
  videoNoteIdReads,
  videoFeedLengthReads,
  videoFeedIndexReads,
  store: Object.fromEntries(store)
}));
"""
        completed = subprocess.run(
            [NODE, "-e", runner, str(SCRIPT)],
            input=json.dumps({
                "url": url, "body": body, "store": store or {},
                "trackVideoSaveLookupReads": track_video_save_lookup_reads,
                **({"rawBody": raw_body} if raw_body is not None else {})
            }),
            capture_output=True, text=True, check=False, timeout=10
        )
        if completed.returncode != 0:
            raise AssertionError("Node VM failed: " + completed.stderr + completed.stdout)
        return json.loads(completed.stdout)

    def test_empty_body_finishes_before_json_parse(self):
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture",
            None, raw_body=""
        )
        self.assertEqual(result["doneResult"], {})
        self.assertEqual(result["parseCount"], 0)

    def test_imagefeed_mutates_parsed_object_without_json_round_trip(self):
        original = "https://img.example/a.jpg?imageView2/2/w/1080/format/jpg"
        body = {"data": [{"note_list": [{
            "images_list": [{
                "url": original,
                "nested": {"url": original},
                "live_photo_file_id": "live-file-1",
                "live_photo": {"media": {
                    "video_id": "video-1",
                    "stream": {"h265": [{"master_url": "https://video.example/live.mp4"}]}
                }}
            }],
            "media_save_config": {"disable_save": True},
            "share_info": {"function_entries": [{"type": "share"}]},
            "hash_tag": [{"type": "normal"}, {"type": "interact_vote"}]
        }]}]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=fixture", body
        )
        response = json.loads(result["doneResult"]["body"])
        item = response["data"][0]["note_list"][0]
        self.assertIn("w/2160/format", item["images_list"][0]["url"])
        self.assertIn("w/2160/format", item["images_list"][0]["nested"]["url"])
        self.assertEqual([tag["type"] for tag in item["hash_tag"]], ["normal"])
        self.assertEqual(result["imageArrayReads"], 1)
        cached = json.loads(result["store"]["redBookLivePhoto"])
        self.assertEqual(cached, [{
            "file_id": "live-file-1",
            "video_id": "video-1",
            "url": "https://video.example/live.mp4"
        }])
        self.assertNotIn("nested", cached[0])
        self.assertLess(
            len(result["store"]["redBookLivePhoto"]),
            len(json.dumps(body["data"][0]["note_list"][0]["images_list"]))
        )


    def test_imagefeed_live_photo_cache_uses_same_traversal_and_only_top_level_records(self):
        body = {"data": [{"note_list": [
            {"images_list": [
                {
                    "url": "https://img.example/a.jpg?imageView2/2/w/1080/format/jpg",
                    "live_photo_file_id": "live-file-1",
                    "live_photo": {"media": {"video_id": "video-1", "stream": {"h265": [
                        {"master_url": "https://video.example/one.mp4"}
                    ]}}},
                    "nested": {
                        "live_photo_file_id": "nested-file-must-not-cache",
                        "live_photo": {"media": {"video_id": "nested-video", "stream": {"h265": [
                            {"master_url": "https://video.example/nested.mp4"}
                        ]}}}
                    }
                },
                {
                    "url": "https://img.example/b.jpg?imageView2/2/w/1080/format/jpg",
                    "live_photo_file_id": "live-file-2",
                    "live_photo": {"media": {"video_id": "video-2", "stream": {"h265": [
                        {"master_url": "https://video.example/two.mp4"}
                    ]}}}
                }
            ]}
        ]}]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/imagefeed?cursor=single-pass",
            body
        )
        output = json.loads(result["doneResult"]["body"])
        images = output["data"][0]["note_list"][0]["images_list"]
        self.assertIn("w/2160/format", images[0]["url"])
        self.assertIn("w/2160/format", images[1]["url"])
        self.assertEqual(result["imageArrayReads"], 2)
        cache = json.loads(result["store"]["redBookLivePhoto"])
        self.assertEqual(
            cache,
            [
                {"file_id": "live-file-1", "video_id": "video-1", "url": "https://video.example/one.mp4"},
                {"file_id": "live-file-2", "video_id": "video-2", "url": "https://video.example/two.mp4"}
            ]
        )

    def test_live_photo_save_consumes_compact_cache_records(self):
        compact = [{
            "file_id": "live-file-1",
            "video_id": "video-1",
            "url": "https://video.example/live.mp4"
        }]
        body = {"code": 0, "data": {"datas": [{
            "file_id": "live-file-1",
            "url": "https://placeholder.example/video.mp4"
        }]}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/live_photo/save",
            body,
            store={"redBookLivePhoto": json.dumps(compact)}
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(output["data"]["datas"][0]["url"], "https://video.example/live.mp4")

    def test_homefeed_compaction_is_stable_and_keeps_null_items(self):
        body = {"data": [
            {"id": "keep1", "related_ques": {}},
            None,
            {"id": "ad", "ads_info": {}},
            {"id": "live", "model_type": "live_v2"},
            {"id": "shop", "note_attributes": ["goods"]},
            {"id": "card", "card_icon": None},
            {"id": "keep2"}
        ]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v6/homefeed?cursor=fixture", body
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual([item["id"] for item in output["data"] if item], ["keep1", "keep2"])
        self.assertIsNone(output["data"][1])
        self.assertNotIn("related_ques", output["data"][0])

    def test_video_save_lookup_reads_note_id_and_feed_length_once(self):
        video_feed = [
            {"id": "note-first", "url": "https://video.example/first.mp4"},
            {"id": "note-target", "url": "https://video.example/target.mp4"},
            {"id": "note-after", "url": "https://video.example/after.mp4"},
        ]
        body = {"data": {"note_id": "note-target", "disable": True, "msg": "disabled"}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v1/note/video/save?fixture=lookup-cache",
            body,
            store={"redBookVideoFeed": json.dumps(video_feed)},
            track_video_save_lookup_reads=True,
        )
        output = json.loads(result["doneResult"]["body"])
        self.assertEqual(result["videoDataReads"], 1)
        self.assertEqual(result["videoNoteIdReads"], 1)
        self.assertEqual(result["videoFeedLengthReads"], 1)
        self.assertEqual(result["videoFeedIndexReads"], 2)
        self.assertEqual(output["data"]["download_url"], "https://video.example/target.mp4")
        self.assertEqual(output["data"]["status"], 2)
        self.assertNotIn("disable", output["data"])
        self.assertNotIn("msg", output["data"])

    def test_comment_picture_array_reference_is_read_once_per_processed_comment(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();
let doneResult,reads=0,tracking=false;
const nativeParse=JSON.parse.bind(JSON),nativeStringify=JSON.stringify.bind(JSON);
const trackedJSON={
  parse(value){
    const parsed=nativeParse(value);
    const track=comment=>{
      if(!comment||typeof comment!=="object")return;
      let pictures=comment.pictures;
      Object.defineProperty(comment,"pictures",{enumerable:true,configurable:true,
        get(){if(tracking)reads++;return pictures;},set(value){pictures=value;}});
    };
    for(const comment of parsed?.data?.comments||[]){
      track(comment);
      for(const child of comment.sub_comments||[])track(child);
    }
    tracking=true;
    return parsed;
  },
  stringify(value){tracking=false;return nativeStringify(value);}
};
const context={
  $loon:{},
  $persistentStore:{read(key){return store.has(key)?store.get(key):null;},write(value,key){store.set(key,value);return true;}},
  $request:{url:payload.url},
  $response:{body:nativeStringify(payload.body)},
  $done(value){doneResult=value;},
  JSON:trackedJSON,
  console:{log(){},warn(){},error(){}}
};
vm.createContext(context);
vm.runInNewContext(source,context,{timeout:5000});
process.stdout.write(nativeStringify({doneResult,reads,store:Object.fromEntries(store)}));
""";
        video_info = json.dumps({"stream": {"h265": [{"master_url": "https://video.example/live.mp4"}]}})
        body = {"data": {"comments": [{
            "note_id": "note-reads",
            "pictures": [{"video_id": "video-1", "video_info": video_info}],
            "sub_comments": [{"pictures": [{"video_id": "video-2", "video_info": video_info}]}]
        }]}}
        completed = subprocess.run(
            [NODE, "-e", runner],
            input=json.dumps({"url": "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=picture-reads", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["reads"], 2)
        cached = json.loads(result["store"]["xiaohongshu.comments.rsp"])
        self.assertEqual([item["videId"] for item in cached["livePhotos"]], ["video-1", "video-2"])

    def test_v4_video_feed_uses_indexed_function_entry_scan_without_some(self):
        runner = r"""
const fs=require("fs"),vm=require("vm"),source=fs.readFileSync(process.argv[1],"utf8");
const payload=JSON.parse(fs.readFileSync(0,"utf8")),store=new Map();
let doneResult;
const context={
  $loon:{},
  $persistentStore:{read(key){return store.has(key)?store.get(key):null;},write(value,key){store.set(key,value);return true;}},
  $request:{url:payload.url},
  $response:{body:JSON.stringify(payload.body)},
  $done(value){doneResult=value;},
  console:{log(){},warn(){},error(){}}
};
vm.createContext(context);
vm.runInNewContext("Array.prototype.some = function() { throw new Error('Array.some callback remains'); };",context);
vm.runInNewContext(source,context,{timeout:5000});
const output=JSON.parse(doneResult.body);
process.stdout.write(JSON.stringify(output));
""";
        body = {"data": [
            {"id": "note-existing", "share_info": {"function_entries": [
                {"type": "share"}, {"type": "video_download"}
            ]}},
            {"id": "note-missing", "share_info": {"function_entries": [
                {"type": "share"}
            ]}},
        ]}
        completed = subprocess.run(
            [NODE, "-e", runner],
            input=json.dumps({"url": "https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?cursor=function-entry-scan", "body": body}),
            capture_output=True, text=True, check=False, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        entries = {item["id"]: item["share_info"]["function_entries"] for item in output["data"]}
        self.assertEqual([entry["type"] for entry in entries["note-existing"]], ["share", "video_download"])
        self.assertEqual([entry["type"] for entry in entries["note-missing"]], ["share", "video_download"])

    def test_v4_video_stream_selection_uses_single_pass_highest_height(self):
        body = {"data": [{
            "id": "note-1",
            "video_info_v2": {"media": {"stream": {"h265": [
                {"master_url": "https://video.example/720.mp4", "height": 720},
                {"master_url": "https://video.example/2160.mp4", "height": 2160},
                {"master_url": "https://video.example/1080.mp4", "height": 1080}
            ]}}}
        }]}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v4/note/videofeed?cursor=fixture", body
        )
        cache = json.loads(result["store"]["redBookVideoFeed"])
        self.assertEqual(cache[0]["url"], "https://video.example/2160.mp4")

    def test_comment_cleanup_and_media_extraction_share_one_tree_walk(self):
        video_info = json.dumps({"stream": {"h265": [{"master_url": "https://video.example/live.mp4"}]}})
        body = {"data": {"comments": [{
            "note_id": "note-1", "red_id": "remove-top", "comment_type": 3,
            "media_source_type": 1,
            "pictures": [{"video_id": "video-1", "video_info": video_info}],
            "sub_comments": [{
                "red_id": "remove-child", "comment_type": 3, "media_source_type": 1,
                "pictures": [{"video_id": "video-2", "video_info": video_info}],
                "sub_comments": [{
                    "comment_type": 3,
                    "pictures": [{"video_id": "video-deep", "video_info": video_info}]
                }]
            }]
        }]}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture", body
        )
        output = json.loads(result["doneResult"]["body"])
        top = output["data"]["comments"][0]
        child = top["sub_comments"][0]
        deep = child["sub_comments"][0]
        self.assertNotIn("red_id", top)
        self.assertNotIn("red_id", child)
        self.assertEqual(top["comment_type"], 2)
        self.assertEqual(child["comment_type"], 2)
        self.assertEqual(deep["comment_type"], 3)
        cached = json.loads(result["store"]["xiaohongshu.comments.rsp"])
        self.assertEqual([x["videId"] for x in cached["livePhotos"]], ["video-1", "video-2"])
        self.assertEqual(result["parseCount"], 2)
        self.assertEqual(result["weakSetConstructCount"], 0)
        self.assertEqual(result["mapGetCount"], 2)
        self.assertEqual(result["mapHasCount"], 0)

    def test_comment_video_info_cache_uses_one_map_lookup_per_picture(self):
        video_info = json.dumps({"stream": {"h265": [
            {"master_url": "https://video.example/shared.mp4"}
        ]}})
        body = {"data": {"comments": [{
            "note_id": "note-cache",
            "pictures": [
                {"video_id": "video-1", "video_info": video_info},
                {"video_id": "video-2", "video_info": video_info},
                {"video_id": "video-3", "video_info": video_info}
            ]
        }]}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=cache-single-lookup",
            body
        )
        cached = json.loads(result["store"]["xiaohongshu.comments.rsp"])
        self.assertEqual(
            [item["videId"] for item in cached["livePhotos"]],
            ["video-1", "video-2", "video-3"]
        )
        self.assertEqual(result["parseCount"], 2)
        self.assertEqual(result["mapGetCount"], 3)
        self.assertEqual(result["mapHasCount"], 0)

    def test_comment_tree_cleanup_is_iterative_for_deep_objects(self):
        nested = {"red_id": "deep"}
        for index in range(400):
            nested = {"child": nested, "red_id": str(index)}
        body = {"data": {"red_id": "root", "nested": nested}}
        result = self.run_script(
            "https://edith.xiaohongshu.com/api/sns/v5/note/comment/list?cursor=fixture", body
        )
        output = json.loads(result["doneResult"]["body"])
        current = output["data"]
        while "nested" in current:
            self.assertNotIn("red_id", current)
            current = current["nested"]
        self.assertNotIn("red_id", current)
        self.assertEqual(result["weakSetConstructCount"], 0)


if __name__ == "__main__":
    unittest.main()
