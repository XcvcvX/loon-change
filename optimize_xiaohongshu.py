#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible performance transforms for the Xiaohongshu response script."""
import argparse
from pathlib import Path

REMOTE="https://github.com/fmz200/wool_scripts/raw/main/Scripts/xiaohongshu/xiaohongshu.js"
LOCAL="https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu.js"
MARKER="// loon-change: Xiaohongshu response hot-path optimization v1; upstream fmz200/wool_scripts@"

def once(s,a,b,label):
    n=s.count(a)
    if n!=1: raise ValueError(f"{label}: expected one match, found {n}")
    return s.replace(a,b,1)

def between(s,a,b,repl,label):
    if s.count(a)!=1 or s.count(b)!=1: raise ValueError(f"{label}: source boundary drift")
    i=s.index(a); j=s.index(b,i+len(a))
    if j<=i: raise ValueError(f"{label}: invalid source order")
    return s[:i]+repl+"\n\n"+s[j:]

HELPERS=r'''
function compactInPlace(items, keep) {
  let write = 0;
  for (let read = 0, length = items.length; read < length; read++) {
    const item = items[read];
    if (keep(item)) { if (write !== read) items[write] = item; write++; }
  }
  items.length = write;
  return items;
}
function appendUniqueLivePhotos(existing, incoming) {
  const seen = new Set(); let write = 0;
  for (let read = 0; read < existing.length; read++) {
    const item = existing[read];
    if (!seen.has(item.videId)) { seen.add(item.videId); existing[write++] = item; }
  }
  existing.length = write;
  for (const item of incoming) if (!seen.has(item.videId)) { seen.add(item.videId); existing.push(item); }
  return existing;
}
'''
IMAGE=r'''function imageEnhance(images) {
  if (!images || typeof images !== "object") return [];
  const quality=$.getdata("fmz200.xiaohongshu.imageQuality");
  const originalPattern=/\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern=/imageView2\/2\/w\/\d+\/format/g, heightPattern=/imageView2\/2\/h\/\d+\/format/g;
  let originalDone=false;
  const stack=[{value:images,index:0,keys:null}];
  while(stack.length) {
    const frame=stack[stack.length-1], value=frame.value;
    if(Array.isArray(value)) {
      if(frame.index>=value.length){stack.pop();continue;}
      const key=frame.index++, child=value[key];
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null});
    } else {
      if(frame.keys===null) frame.keys=Object.keys(value);
      if(frame.index>=frame.keys.length){stack.pop();continue;}
      const key=frame.keys[frame.index++], child=value[key];
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null});
    }
  }
  return images;
}'''
URLMAP=r'''function replaceUrlContent(collectionA, collectionB) {
  const byFileId=new Map();
  for(const item of collectionB) if(item && !byFileId.has(item.file_id)) byFileId.set(item.file_id,item);
  const videoBaseRegex=/(.*\.(mp4|mov|webm|m3u8|ts|avi|mkv|flv))/i;
  for(const item of collectionA) {
    if(!item) continue;
    const found=byFileId.get(item.file_id);
    if(!found) continue;
    if(item.url!==""){const match=found.url.match(videoBaseRegex);item.url=match?match[1]:found.url;}
    else item.url=found.url;
    item.author="@fmz200";
  }
}'''
DEDUP=r'''function deduplicateLivePhotos(items) {
  const seen=new Set();let write=0;
  for(let read=0;read<items.length;read++){const item=items[read];if(seen.has(item.videId))continue;seen.add(item.videId);if(write!==read)items[write]=item;write++;}
  items.length=write;return items;
}'''
TRAVERSE=r'''function replaceRedIdWithFmz200(obj) {
  const stack=[obj];
  while(stack.length){const current=stack.pop();
    if(Array.isArray(current)){for(let i=current.length-1;i>=0;i--)if(current[i]&&typeof current[i]==="object")stack.push(current[i]);}
    else if(current&&typeof current==="object"){if("red_id" in current){current.fmz200=current.red_id;delete current.red_id;}
      const childStart=stack.length;for(const key in current){if(!Object.prototype.hasOwnProperty.call(current,key))continue;const child=current[key];if(child&&typeof child==="object")stack.push(child);}for(let left=childStart,right=stack.length-1;left<right;left++,right--){const temp=stack[left];stack[left]=stack[right];stack[right]=temp;}}
  }
}'''
COMMENT_PROCESSOR="function processCommentTree(data, livePhotos, commentVideos, noteId) {\n  const topLevelComments = new WeakSet();\n  const commentNodes = new WeakSet();\n  const comments = data?.comments;\n  if (Array.isArray(comments)) {\n    for (const comment of comments) {\n      if (!comment || typeof comment !== \"object\") continue;\n      topLevelComments.add(comment);\n      commentNodes.add(comment);\n      if (Array.isArray(comment.sub_comments)) {\n        for (const subComment of comment.sub_comments) {\n          if (subComment && typeof subComment === \"object\") commentNodes.add(subComment);\n        }\n      }\n    }\n  }\n  const parsedVideoInfo = new Map();\n  const parseVideoInfo = raw => {\n    if (typeof raw !== \"string\" || raw.length === 0) return null;\n    if (!parsedVideoInfo.has(raw)) {\n      try { parsedVideoInfo.set(raw, JSON.parse(raw)); }\n      catch (_) { parsedVideoInfo.set(raw, null); }\n    }\n    return parsedVideoInfo.get(raw);\n  };\n  const stack = [data];\n  const visited = new WeakSet();\n  while (stack.length) {\n    const current = stack.pop();\n    if (!current || typeof current !== \"object\" || visited.has(current)) continue;\n    visited.add(current);\n    if (!Array.isArray(current)) {\n      if (\"red_id\" in current) { current.fmz200 = current.red_id; delete current.red_id; }\n      if (commentNodes.has(current)) {\n        fixCommentType(current);\n        if (Array.isArray(current.pictures)) {\n          for (const picture of current.pictures) {\n            if (!picture?.video_id) continue;\n            const info = parseVideoInfo(picture.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) livePhotos.push({videId: picture.video_id, videoUrl: stream.master_url});\n          }\n        }\n        if (topLevelComments.has(current) && Array.isArray(current.videos)) {\n          for (const video of current.videos) {\n            if (!video?.video_id || !video?.video_info) continue;\n            const info = parseVideoInfo(video.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) commentVideos.push({\n              videId: video.video_id, videoUrl: stream.master_url, commentId: current.id, noteId,\n              width: stream.width, height: stream.height, bitrate: stream.video_bitrate, hdr: stream.hdr_type === 1\n            });\n          }\n        }\n      }\n    }\n    if (Array.isArray(current)) {\n      for (let i = current.length - 1; i >= 0; i--) { const child = current[i]; if (child && typeof child === \"object\") stack.push(child); }\n    } else {\n      for (const key in current) {\n        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;\n        const child = current[key]; if (child && typeof child === \"object\") stack.push(child);\n      }\n    }\n  }\n}"
COMMENT_BRANCH="// 加载评论区\nif (url.includes(\"/api/sns/v5/note/comment/list?\") || url.includes(\"/api/sns/v3/note/comment/sub_comments?\")) {\n  const livePhotos = [];\n  const commentVideos = [];\n  const note_id = obj.data?.comments?.[0]?.note_id || \"\";\n  processCommentTree(obj.data, livePhotos, commentVideos, note_id);\n  if (livePhotos.length > 0) {\n    let commitsRsp;\n    const commitsCache = $.getdata(\"fmz200.xiaohongshu.comments.rsp\");\n    if (!commitsCache) commitsRsp = {noteId: note_id, livePhotos};\n    else {\n      commitsRsp = JSON.parse(commitsCache);\n      if (commitsRsp.noteId === note_id) commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);\n      else commitsRsp = {noteId: note_id, livePhotos};\n    }\n    $.setdata(JSON.stringify(commitsRsp), \"fmz200.xiaohongshu.comments.rsp\");\n  }\n  if (commentVideos.length > 0) {\n    let videosCache;\n    const commitsCache = $.getdata(\"fmz200.xiaohongshu.comments.videos.rsp\");\n    if (!commitsCache) videosCache = {noteId: note_id, videos: commentVideos};\n    else {\n      videosCache = JSON.parse(commitsCache);\n      if (videosCache.noteId === note_id) videosCache.videos = appendUniqueLivePhotos(videosCache.videos, commentVideos);\n      else videosCache = {noteId: note_id, videos: commentVideos};\n    }\n    $.setdata(JSON.stringify(videosCache), \"fmz200.xiaohongshu.comments.videos.rsp\");\n  }\n}"

STREAM=r'''function selectBestStream(h265List,h264List) {
  const choose=list=>{if(!Array.isArray(list)||!list.length)return null;let best=null,pixelsBest=0,rateBest=0;
    for(const item of list){if(!item||!item.master_url)continue;const pixels=(item.width||0)*(item.height||0),rate=Number(item.avg_bitrate)||0;
      if(best===null||pixels>pixelsBest||(pixels===pixelsBest&&rate>rateBest)){best=item;pixelsBest=pixels;rateBest=rate;}}
    return best;};
  return choose(h265List)||choose(h264List);
}'''

def apply_comment_optimization(src):
    src=between(src,"function replaceRedIdWithFmz200(obj) {","\n/**\n * 从流列表",COMMENT_PROCESSOR,"combined comment traversal")
    src=between(src,"// 加载评论区","// 下载评论区live图/评论区视频",COMMENT_BRANCH,"comment processing branch")
    return src

def optimize_source(src,commit="unknown"):
    if MARKER in src:
        if "Object.keys(current)" in src: raise ValueError("Xiaohongshu traversal optimization is stale")
        if "function processCommentTree(data, livePhotos, commentVideos, noteId)" in src and "processCommentTree(obj.data, livePhotos, commentVideos, note_id);" in src:
            return src
        return apply_comment_optimization(src)
    src=once(src,"const url = $request.url;","const url = $request.url;\n"+HELPERS.strip(),"helpers")
    src=once(src,"  console.log('打印原body：' + JSON.stringify(obj));\n","","full-body logging")
    src=once(src,'''      obj.data[0].note_list[0].images_list = imageEnhance(JSON.stringify(images_list));
      // 保存无水印信息
      $.setdata(JSON.stringify(images_list), "fmz200.xiaohongshu.feed.rsp");
      console.log('已存储无水印信息♻️');''','''      // Cache only the live-photo fields required by the save endpoint.
      const livePhotoCache = [];
      if (Array.isArray(images_list)) {
        for (const image of images_list) {
          const stream = image?.live_photo?.media?.stream?.h265?.[0];
          const videoId = image?.live_photo?.media?.video_id;
          if (image?.live_photo_file_id && videoId && stream?.master_url) {
            livePhotoCache.push({
              live_photo_file_id: image.live_photo_file_id,
              video_id: videoId,
              url: stream.master_url
            });
          }
        }
      }
      $.setdata(JSON.stringify(livePhotoCache), "fmz200.xiaohongshu.feed.rsp");
      obj.data[0].note_list[0].images_list = imageEnhance(images_list);''',"image-feed JSON round trip")
    src=between(src,"  const cache_body = JSON.parse(rsp);","  if (obj.data.datas)",'''  const cache_body = JSON.parse(rsp);
  const new_data = [];
  for (const images of cache_body) {
    // Accept compact cache records and legacy full-image cache records.
    const fileId = images.file_id || images.live_photo_file_id;
    const videoId = images.video_id || images.live_photo?.media?.video_id;
    const videoUrl = images.url || images.live_photo?.media?.stream?.h265?.[0]?.master_url;
    if (fileId && videoId && videoUrl) {
      new_data.push({file_id: fileId, video_id: videoId, url: videoUrl});
    }
  }''',"compact live-photo cache consumer")
    for old,new,label in [
      ('obj.data.items = obj.data.items.filter((i) => i.model_type === "note");','compactInPlace(obj.data.items, item => item?.model_type === "note");',"search"),
      ('item.hash_tag = item.hash_tag.filter(tag => tag.type !== "interact_vote");','compactInPlace(item.hash_tag, tag => tag?.type !== "interact_vote");',"hashtags"),
      ('obj.data.items = obj.data.items.filter((i) => i?.recommend_reason === "friend_post");','compactInPlace(obj.data.items, item => item?.recommend_reason === "friend_post");',"follow feed"),
      ('obj.data.items = obj.data.items.filter((i) => !["recommend_user"].includes(i.recommend_reason));','compactInPlace(obj.data.items, item => item?.recommend_reason !== "recommend_user");',"follow list")]:
        src=once(src,old,new,label)
    home_old='''    let newItems = [];
    for (let item of obj.data) {
      if (item?.model_type === "live_v2") {
        // 信息流-直播
      } else if (item?.hasOwnProperty("ads_info")) {
        // 信息流-赞助
      } else if (item?.hasOwnProperty("card_icon")) {
        // 信息流-带货
      } else if (item?.note_attributes?.includes("goods")) {
        // 信息流-商品
      } else {
        if (item?.related_ques) {
          delete item.related_ques;
        }
        newItems.push(item);
      }
    }
    obj.data = newItems;'''
    home_new='''    compactInPlace(obj.data, item => {
      if (!item) return true;
      if (item.model_type === "live_v2" ||
          Object.prototype.hasOwnProperty.call(item, "ads_info") ||
          Object.prototype.hasOwnProperty.call(item, "card_icon") ||
          item.note_attributes?.includes("goods")) return false;
      if (item.related_ques) delete item.related_ques;
      return true;
    });'''
    src=once(src,home_old,home_new,"homefeed")
    src=between(src,"function imageEnhance(jsonStr) {","\nfunction replaceUrlContent(",IMAGE,"imageEnhance")
    src=between(src,"function replaceUrlContent(collectionA, collectionB) {","\nfunction deduplicateLivePhotos(",URLMAP,"live-photo URL lookup")
    src=between(src,"function deduplicateLivePhotos(livePhotos) {","\nfunction replaceRedIdWithFmz200(",DEDUP,"live-photo dedup")
    src=between(src,"function selectBestStream(h265List, h264List) {","\n/**\n * 修复评论类型",STREAM,"stream selection")
    src=src.replace("commitsRsp.livePhotos = deduplicateLivePhotos(commitsRsp.livePhotos.concat(livePhotos));","commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);")
    src=src.replace("videosCache.videos = deduplicateLivePhotos(videosCache.videos.concat(commentVideos));","videosCache.videos = appendUniqueLivePhotos(videosCache.videos, commentVideos);")
    log_tokens = (
        "原body：", "读取缓存key", "缓存无内容", "新body：", "本次note_id",
        "读取缓存val", "缓存note_id", "增量数据", "更换数据", "写入缓存val",
        "目标video_id", "匹配到无水印链接", "comment_id:", "video_id：",
        "没有[", "修改评论类型", "修改媒体类型", "提取成功", "未找到可用视频",
        "已缓存普通视频", "添加下载按钮", "[缓存] ID:",
    )
    src = "".join(
        line for line in src.splitlines(keepends=True)
        if not ("console.log(" in line and any(token in line for token in log_tokens))
    )
    result=MARKER+commit+"\n"+src
    for token in ("imageEnhance(images_list)","compactInPlace(obj.data","appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)","const byFileId=new Map()"):
        if token not in result:raise ValueError("missing optimizer invariant: "+token)
    if "imageEnhance(JSON.stringify(images_list))" in result:raise ValueError("image-feed serialization round trip remains")
    return apply_comment_optimization(result)

def rewrite_plugin(plugin):
    if LOCAL in plugin:
        if REMOTE in plugin:raise ValueError("mixed local and upstream script URLs")
        return plugin
    section=None;count=0;out=[]
    for line in plugin.splitlines():
        t=line.strip()
        if t.startswith("[") and t.endswith("]"):section=t[1:-1].strip().lower()
        if section=="script" and REMOTE in line:count+=line.count(REMOTE);line=line.replace(REMOTE,LOCAL)
        out.append(line)
    if count==0:return plugin
    if count!=9:raise ValueError(f"Xiaohongshu trigger inventory changed: expected 9, got {count}")
    result="\n".join(out)
    if REMOTE in result:raise ValueError("upstream URL remains")
    return result+("\n" if plugin.endswith("\n") else "")

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source");p.add_argument("--output");p.add_argument("--upstream-commit",default="unknown");p.add_argument("--plugin");a=p.parse_args()
    if a.source or a.output:
        if not a.source or not a.output:p.error("--source and --output must be supplied together")
        result=optimize_source(Path(a.source).read_text(encoding="utf-8-sig"),a.upstream_commit)
        Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(result,encoding="utf-8");print("Optimized Xiaohongshu source",len(result))
    if a.plugin:
        path=Path(a.plugin);path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")),encoding="utf-8");print("Routed 9 response triggers to local script")
    if not(a.source or a.output or a.plugin):p.error("provide source/output and/or plugin")

if __name__=="__main__":main()
