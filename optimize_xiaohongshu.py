#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
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
IMAGE=r'''// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1
function imageEnhance(images, livePhotoCache) {
  if (!images || typeof images !== "object") return [];
  const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;
  const quality=$.getdata("fmz200.xiaohongshu.imageQuality");
  const originalPattern=/\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern=/imageView2\/2\/w\/\d+\/format/g, heightPattern=/imageView2\/2\/h\/\d+\/format/g;
  let originalDone=false;
  const stack=[{value:images,index:0,keys:null,root:true}];
  while(stack.length) {
    const frame=stack[stack.length-1], value=frame.value;
    if(Array.isArray(value)) {
      if(frame.index>=value.length){stack.pop();continue;}
      const key=frame.index++, child=value[key];
      if(frame.root && livePhotoTarget && child && typeof child === "object") {
        const stream = child.live_photo?.media?.stream?.h265?.[0];
        const videoId = child.live_photo?.media?.video_id;
        if (child.live_photo_file_id && videoId && stream?.master_url) {
          livePhotoTarget.push({
            live_photo_file_id: child.live_photo_file_id,
            video_id: videoId,
            url: stream.master_url
          });
        }
      }
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null,root:false});
    } else {
      if(frame.keys===null) frame.keys=Object.keys(value);
      if(frame.index>=frame.keys.length){stack.pop();continue;}
      const key=frame.keys[frame.index++], child=value[key];
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null,root:false});
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
COMMENT_PROCESSOR="function processCommentTree(data, livePhotos, commentVideos, noteId) {\n  // loon-change: Xiaohongshu comment classification stack frames v1;\n  const commentFrameTag = {};\n  const parsedVideoInfo = new Map();\n  const parseVideoInfo = raw => {\n    if (typeof raw !== \"string\" || raw.length === 0) return null;\n    // loon-change: Xiaohongshu comment video-info cache single lookup v2;\n    let parsed = parsedVideoInfo.get(raw);\n    if (parsed === undefined) {\n      try { parsed = JSON.parse(raw); }\n      catch (_) { parsed = null; }\n      parsedVideoInfo.set(raw, parsed);\n    }\n    return parsed;\n  };\n  // loon-change: Xiaohongshu parsed JSON comment tree without visited WeakSet v1;\n  // JSON.parse creates a tree with no cycles or shared object references.\n  // Comment classification travels with only comment stack entries; other nodes\n  // remain plain references and require no WeakSet membership structure.\n  const stack = [data];\n  while (stack.length) {\n    const entry = stack.pop();\n    const isCommentFrame = Array.isArray(entry) && entry[0] === commentFrameTag;\n    const current = isCommentFrame ? entry[1] : entry;\n    const isTopLevelComment = isCommentFrame && entry[2] === true;\n    if (!current || typeof current !== \"object\") continue;\n    if (!Array.isArray(current)) {\n      if (\"red_id\" in current) { current.fmz200 = current.red_id; delete current.red_id; }\n      if (isCommentFrame) {\n        fixCommentType(current);\n        if (Array.isArray(current.pictures)) {\n          for (const picture of current.pictures) {\n            if (!picture?.video_id) continue;\n            const info = parseVideoInfo(picture.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) livePhotos.push({videId: picture.video_id, videoUrl: stream.master_url});\n          }\n        }\n        if (isTopLevelComment && Array.isArray(current.videos)) {\n          for (const video of current.videos) {\n            if (!video?.video_id || !video?.video_info) continue;\n            const info = parseVideoInfo(video.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) commentVideos.push({\n              videId: video.video_id, videoUrl: stream.master_url, commentId: current.id, noteId,\n              width: stream.width, height: stream.height, bitrate: stream.video_bitrate, hdr: stream.hdr_type === 1\n            });\n          }\n        }\n      }\n    }\n    if (Array.isArray(current)) {\n      for (let i = current.length - 1; i >= 0; i--) {\n        const child = current[i];\n        if (child && typeof child === \"object\") stack.push(child);\n      }\n    } else {\n      for (const key in current) {\n        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;\n        const child = current[key];\n        if (!child || typeof child !== \"object\") continue;\n        if (current === data && key === \"comments\" && Array.isArray(child)) {\n          for (let i = child.length - 1; i >= 0; i--) {\n            const comment = child[i];\n            if (comment && typeof comment === \"object\") stack.push([commentFrameTag, comment, true]);\n          }\n        } else if (isCommentFrame && isTopLevelComment && key === \"sub_comments\" && Array.isArray(child)) {\n          for (let i = child.length - 1; i >= 0; i--) {\n            const subComment = child[i];\n            if (subComment && typeof subComment === \"object\") stack.push([commentFrameTag, subComment, false]);\n          }\n        } else stack.push(child);\n      }\n    }\n  }\n}"
COMMENT_BRANCH="// 加载评论区\nif (url.includes(\"/api/sns/v5/note/comment/list?\") || url.includes(\"/api/sns/v3/note/comment/sub_comments?\")) {\n  const livePhotos = [];\n  const commentVideos = [];\n  const note_id = obj.data?.comments?.[0]?.note_id || \"\";\n  processCommentTree(obj.data, livePhotos, commentVideos, note_id);\n  if (livePhotos.length > 0) {\n    let commitsRsp;\n    const commitsCache = $.getdata(\"fmz200.xiaohongshu.comments.rsp\");\n    if (!commitsCache) commitsRsp = {noteId: note_id, livePhotos};\n    else {\n      commitsRsp = JSON.parse(commitsCache);\n      if (commitsRsp.noteId === note_id) commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);\n      else commitsRsp = {noteId: note_id, livePhotos};\n    }\n    $.setdata(JSON.stringify(commitsRsp), \"fmz200.xiaohongshu.comments.rsp\");\n  }\n  if (commentVideos.length > 0) {\n    let videosCache;\n    const commitsCache = $.getdata(\"fmz200.xiaohongshu.comments.videos.rsp\");\n    if (!commitsCache) videosCache = {noteId: note_id, videos: commentVideos};\n    else {\n      videosCache = JSON.parse(commitsCache);\n      if (videosCache.noteId === note_id) videosCache.videos = appendUniqueLivePhotos(videosCache.videos, commentVideos);\n      else videosCache = {noteId: note_id, videos: commentVideos};\n    }\n    $.setdata(JSON.stringify(videosCache), \"fmz200.xiaohongshu.comments.videos.rsp\");\n  }\n}"




IMAGE_FEED_MARKER = "// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1"

def optimize_imagefeed_single_traversal(source):
    if IMAGE_FEED_MARKER in source:
        required = (
            IMAGE_FEED_MARKER,
            "function imageEnhance(images, livePhotoCache)",
            "const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;",
            "const stack=[{value:images,index:0,keys:null,root:true}];",
            "frame.root && livePhotoTarget",
            "stack.push({value:child,index:0,keys:null,root:false});",
            "imageEnhance(images_list, livePhotoCache);",
            'JSON.stringify(livePhotoCache), "fmz200.xiaohongshu.feed.rsp"',
        )
        if any(token not in source for token in required):
            raise ValueError("Xiaohongshu imagefeed single-traversal structure drifted; refusing overwrite")
        if "for (const image of images_list)" in source:
            raise ValueError("Separate Xiaohongshu imagefeed cache traversal remains")
        return source

    old_block = '''      const images_list = obj.data[0].note_list[0].images_list;
      // 画质增强
      // Cache only the live-photo fields required by the save endpoint.
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
      obj.data[0].note_list[0].images_list = imageEnhance(images_list);'''
    new_block = '''      const images_list = obj.data[0].note_list[0].images_list;
      // Collect compact live-photo fields during the image enhancement traversal.
      const livePhotoCache = [];
      obj.data[0].note_list[0].images_list = imageEnhance(images_list, livePhotoCache);
      $.setdata(JSON.stringify(livePhotoCache), "fmz200.xiaohongshu.feed.rsp");'''
    source = once(source, old_block, new_block, "single-traversal imagefeed writer")

    start = "function imageEnhance(jsonStr) {" if source.count("function imageEnhance(jsonStr) {") == 1 else "function imageEnhance(images) {"
    if source.count(start) != 1:
        raise ValueError("Xiaohongshu imageEnhance source signature drifted; refusing optimization")
    source = between(source, start, "\nfunction replaceUrlContent(", IMAGE, "imageEnhance")
    return source


def apply_comment_optimization(src):
    src=between(src,"function replaceRedIdWithFmz200(obj) {","\n/**\n * 从流列表",COMMENT_PROCESSOR,"combined comment traversal")
    src=between(src,"// 加载评论区","// 下载评论区live图/评论区视频",COMMENT_BRANCH,"comment processing branch")
    return src


COMMENT_STACK_FRAME_MARKER = "// loon-change: Xiaohongshu comment frame stack flat encoding v1;"

def optimize_comment_stack_frame_allocation(src):
    required = (
        COMMENT_STACK_FRAME_MARKER,
        "const isCommentFrame = entry === commentFrameTag;",
        "const current = isCommentFrame ? stack.pop() : entry;",
        "const isTopLevelComment = isCommentFrame && stack.pop() === true;",
        "stack.push(true, comment, commentFrameTag);",
        "stack.push(false, subComment, commentFrameTag);",
    )
    legacy = (
        "const isCommentFrame = Array.isArray(entry) && entry[0] === commentFrameTag;",
        "stack.push([commentFrameTag, comment, true]);",
        "stack.push([commentFrameTag, subComment, false]);",
    )
    if COMMENT_STACK_FRAME_MARKER in src:
        if src.count(COMMENT_STACK_FRAME_MARKER) != 1 or any(token not in src for token in required) or any(token in src for token in legacy):
            raise ValueError("Xiaohongshu flat comment stack-frame marker is stale")
        return src
    old_setup = """  const stack = [data];
  while (stack.length) {
    const entry = stack.pop();
    const isCommentFrame = Array.isArray(entry) && entry[0] === commentFrameTag;
    const current = isCommentFrame ? entry[1] : entry;
    const isTopLevelComment = isCommentFrame && entry[2] === true;"""
    new_setup = """  // loon-change: Xiaohongshu comment frame stack flat encoding v1;
  const stack = [data];
  while (stack.length) {
    const entry = stack.pop();
    const isCommentFrame = entry === commentFrameTag;
    const current = isCommentFrame ? stack.pop() : entry;
    const isTopLevelComment = isCommentFrame && stack.pop() === true;"""
    if src.count(old_setup) != 1:
        raise ValueError("Xiaohongshu comment stack-frame setup anchor drift")
    src = src.replace(old_setup, new_setup, 1)
    if src.count("stack.push([commentFrameTag, comment, true]);") != 1 or src.count("stack.push([commentFrameTag, subComment, false]);") != 1:
        raise ValueError("Xiaohongshu comment stack-frame push anchor drift")
    src = src.replace("stack.push([commentFrameTag, comment, true]);", "stack.push(true, comment, commentFrameTag);", 1)
    src = src.replace("stack.push([commentFrameTag, subComment, false]);", "stack.push(false, subComment, commentFrameTag);", 1)
    if any(token not in src for token in required) or any(token in src for token in legacy):
        raise ValueError("Xiaohongshu flat comment stack-frame postcondition failed")
    return src


COMMENT_MEDIA_CACHE_MARKER = "// loon-change: Xiaohongshu comment media collection property cache v1;"

def optimize_comment_media_property_cache(src):
    if COMMENT_MEDIA_CACHE_MARKER in src:
        required = (
            COMMENT_MEDIA_CACHE_MARKER,
            "const pictures = current.pictures;",
            "const pictureVideoId = picture?.video_id;",
            "const pictureVideoInfo = picture.video_info;",
            "const videos = current.videos;",
            "const videoId = video?.video_id;",
            "const videoInfo = video?.video_info;",
        )
        if any(token not in src for token in required) or "if (!picture?.video_id) continue;" in src or "if (!video?.video_id || !video?.video_info) continue;" in src:
            raise ValueError("Xiaohongshu comment media property-cache marker is stale")
        return src
    old = "        if (Array.isArray(current.pictures)) {\n          for (const picture of current.pictures) {\n            if (!picture?.video_id) continue;\n            const info = parseVideoInfo(picture.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) livePhotos.push({videId: picture.video_id, videoUrl: stream.master_url});\n          }\n        }\n        if (isTopLevelComment && Array.isArray(current.videos)) {\n          for (const video of current.videos) {\n            if (!video?.video_id || !video?.video_info) continue;\n            const info = parseVideoInfo(video.video_info);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) commentVideos.push({\n              videId: video.video_id, videoUrl: stream.master_url, commentId: current.id, noteId,\n              width: stream.width, height: stream.height, bitrate: stream.video_bitrate, hdr: stream.hdr_type === 1\n            });\n          }\n        }"
    new = "        // loon-change: Xiaohongshu comment media collection property cache v1;\n        const pictures = current.pictures;\n        if (Array.isArray(pictures)) {\n          for (const picture of pictures) {\n            const pictureVideoId = picture?.video_id;\n            if (!pictureVideoId) continue;\n            const pictureVideoInfo = picture.video_info;\n            const info = parseVideoInfo(pictureVideoInfo);\n            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n            if (stream?.master_url) livePhotos.push({videId: pictureVideoId, videoUrl: stream.master_url});\n          }\n        }\n        if (isTopLevelComment) {\n          const videos = current.videos;\n          if (Array.isArray(videos)) {\n            for (const video of videos) {\n              const videoId = video?.video_id;\n              const videoInfo = video?.video_info;\n              if (!videoId || !videoInfo) continue;\n              const info = parseVideoInfo(videoInfo);\n              const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);\n              if (stream?.master_url) commentVideos.push({\n                videId: videoId, videoUrl: stream.master_url, commentId: current.id, noteId,\n                width: stream.width, height: stream.height, bitrate: stream.video_bitrate, hdr: stream.hdr_type === 1\n              });\n            }\n          }\n        }"
    return once(src, old, new, "comment media property cache")


COMMENT_CACHE_MARKER = "// loon-change: Xiaohongshu comment video-info cache single lookup v2;"

def optimize_comment_video_info_cache(src):
    if COMMENT_CACHE_MARKER in src:
        if "parsedVideoInfo.has(raw)" in src:
            raise ValueError("Xiaohongshu comment cache single-lookup marker is stale")
        return src
    old = """    if (!parsedVideoInfo.has(raw)) {
      try { parsedVideoInfo.set(raw, JSON.parse(raw)); }
      catch (_) { parsedVideoInfo.set(raw, null); }
    }
    return parsedVideoInfo.get(raw);"""
    new = """    // loon-change: Xiaohongshu comment video-info cache single lookup v2;
    let parsed = parsedVideoInfo.get(raw);
    if (parsed === undefined) {
      try { parsed = JSON.parse(raw); }
      catch (_) { parsed = null; }
      parsedVideoInfo.set(raw, parsed);
    }
    return parsed;"""
    return once(src, old, new, "comment video-info cache single lookup")

VIDEO_SAVE_LOOKUP_MARKER = "// loon-change: Xiaohongshu video-save cache reverse early-exit lookup v1;"

def optimize_video_save_cache_lookup(src):
    if VIDEO_SAVE_LOOKUP_MARKER in src:
        required = (
            VIDEO_SAVE_LOOKUP_MARKER,
            "for (let i = videoFeed.length - 1; i >= 0; i--)",
            "const item = videoFeed[i];",
            "if (item.id === noteId)",
            "obj.data.download_url = item.url;",
            "        break;",
        )
        marker_pos = src.index(VIDEO_SAVE_LOOKUP_MARKER)
        block_end = src.find("\n  }\n  // 解除下载限制", marker_pos)
        block = src[marker_pos:block_end] if block_end >= 0 else ""
        if block_end < 0 or any(token not in block for token in required) or "for (let item of videoFeed)" in block:
            raise ValueError("Xiaohongshu video-save reverse lookup marker is stale")
        return src
    old = """    for (let item of videoFeed) {
      if (item.id === obj.data.note_id) {
        obj.data.download_url = item.url;
      }
    }"""
    new = """    // loon-change: Xiaohongshu video-save cache reverse early-exit lookup v1;
    const noteId = obj.data.note_id;
    for (let i = videoFeed.length - 1; i >= 0; i--) {
      const item = videoFeed[i];
      if (item.id === noteId) {
        obj.data.download_url = item.url;
        break;
      }
    }"""
    return once(src, old, new, "video-save cache reverse early-exit lookup")


VIDEO_SAVE_LAZY_PARSE_MARKER = "// loon-change: Xiaohongshu video-save lazy cache parse v1;"

def optimize_video_save_lazy_cache_parse(src):
    """Skip the persisted video-feed read and JSON.parse when note_id is empty."""
    start = 'if (url.includes("/v10/note/video/save")) {'
    next_route = chr(10) + chr(10) + 'if (url.includes("/user/followings/followfeed")) {'
    marker = VIDEO_SAVE_LAZY_PARSE_MARKER
    if marker in src:
        block_start = src.index(start) if start in src else -1
        block_end = src.find(next_route, block_start) if block_start >= 0 else -1
        block = src[block_start:block_end] if block_end >= 0 else ""
        required = (
            marker,
            "const noteId = obj.data?.note_id;",
            'if (noteId !== "") {',
            'const videoFeed = JSON.parse($.getdata("redBookVideoFeed"));',
            "if (videoFeed?.length > 0) {",
            VIDEO_SAVE_LOOKUP_MARKER,
            "if (item.id === noteId)",
            "obj.data.download_url = item.url;",
            "        break;",
        )
        parse_at = block.find('const videoFeed = JSON.parse($.getdata("redBookVideoFeed"));')
        guard_at = block.find('if (noteId !== "") {')
        if block_end < 0 or any(token not in block for token in required) or guard_at < 0 or parse_at < guard_at:
            raise ValueError("Xiaohongshu video-save lazy-cache marker is stale")
        if 'let videoFeed = JSON.parse($.getdata("redBookVideoFeed"));' in block:
            raise ValueError("Xiaohongshu video-save eager cache parse remains")
        return src

    if start not in src or next_route not in src:
        raise ValueError("Xiaohongshu video-save route boundaries changed; refusing lazy parse")
    block_start = src.index(start)
    block_end = src.index(next_route, block_start)
    old_block = src[block_start:block_end]
    required_old = (
        'let videoFeed = JSON.parse($.getdata("redBookVideoFeed"));',
        'if (obj.data?.note_id !== "" && videoFeed?.length > 0) {',
        VIDEO_SAVE_LOOKUP_MARKER,
        "const noteId = obj.data.note_id;",
        "for (let i = videoFeed.length - 1; i >= 0; i--)",
        "// 解除下载限制",
    )
    if any(token not in old_block for token in required_old):
        raise ValueError("Xiaohongshu video-save cache block changed; refusing lazy parse")
    new_block = '''if (url.includes("/v10/note/video/save")) {
  const noteId = obj.data?.note_id;
  if (noteId !== "") {
    // loon-change: Xiaohongshu video-save lazy cache parse v1;
    const videoFeed = JSON.parse($.getdata("redBookVideoFeed"));
    if (videoFeed?.length > 0) {
      // loon-change: Xiaohongshu video-save cache reverse early-exit lookup v1;
      for (let i = videoFeed.length - 1; i >= 0; i--) {
        const item = videoFeed[i];
        if (item.id === noteId) {
          obj.data.download_url = item.url;
          break;
        }
      }
    }
  }
  // 解除下载限制
  if (obj.data?.disable) {
    delete obj.data.disable;
    delete obj.data.msg;
    obj.data.status = 2;
  }
}'''
    return src[:block_start] + new_block + src[block_end:]




STREAM_SELECTION_MARKER = "// loon-change: Xiaohongshu best-stream selection without per-call closure v1;"

def optimize_stream_selection_no_closure(src):
    if STREAM_SELECTION_MARKER in src:
        start = src.index("function selectBestStream(h265List,h264List) {")
        end = src.find("\n\n\n/**", start)
        block = src[start:end] if end >= 0 else ""
        required = (
            STREAM_SELECTION_MARKER,
            "for (let pass = 0; pass < 2; pass++)",
            "const list = pass === 0 ? h265List : h264List;",
            "if (best) return best;",
            "return null;",
        )
        if end < 0 or any(token not in block for token in required) or "const choose" in block or "=>" in block:
            raise ValueError("Xiaohongshu stream-selection no-closure marker is stale")
        return src
    return between(src, "function selectBestStream(h265List, h264List) {", "\n/**\n * 修复评论类型", "function selectBestStream(h265List,h264List) {\n  // loon-change: Xiaohongshu best-stream selection without per-call closure v1;\n  for (let pass = 0; pass < 2; pass++) {\n    const list = pass === 0 ? h265List : h264List;\n    if (!Array.isArray(list) || !list.length) continue;\n    let best = null, pixelsBest = 0, rateBest = 0;\n    for (const item of list) {\n      if (!item || !item.master_url) continue;\n      const pixels = (item.width || 0) * (item.height || 0);\n      const rate = Number(item.avg_bitrate) || 0;\n      if (best === null || pixels > pixelsBest || (pixels === pixelsBest && rate > rateBest)) {\n        best = item;\n        pixelsBest = pixels;\n        rateBest = rate;\n      }\n    }\n    if (best) return best;\n  }\n  return null;\n}", "stream selection without per-call closure")



IMAGE_LIVE_PHOTO_CACHE_MARKER = "// loon-change: Xiaohongshu imagefeed live-photo property cache v1;"

def optimize_imagefeed_live_photo_property_cache(src):
    if IMAGE_LIVE_PHOTO_CACHE_MARKER in src:
        required = (IMAGE_LIVE_PHOTO_CACHE_MARKER, "const livePhoto = child.live_photo;", "const media = livePhoto?.media;", "const masterUrl = stream?.master_url;", "live_photo_file_id: fileId", "url: masterUrl")
        if any(token not in src for token in required) or "child.live_photo?.media?.stream?.h265?.[0]" in src:
            raise ValueError("Xiaohongshu imagefeed live-photo property-cache marker is stale")
        return src
    return once(src, "      if(frame.root && livePhotoTarget && child && typeof child === \"object\") {\n        const stream = child.live_photo?.media?.stream?.h265?.[0];\n        const videoId = child.live_photo?.media?.video_id;\n        if (child.live_photo_file_id && videoId && stream?.master_url) {\n          livePhotoTarget.push({\n            live_photo_file_id: child.live_photo_file_id,\n            video_id: videoId,\n            url: stream.master_url\n          });\n        }\n      }", "      if(frame.root && livePhotoTarget && child && typeof child === \"object\") {\n        // loon-change: Xiaohongshu imagefeed live-photo property cache v1;\n        const livePhoto = child.live_photo;\n        const media = livePhoto?.media;\n        const stream = media?.stream?.h265?.[0];\n        const fileId = child.live_photo_file_id;\n        const videoId = media?.video_id;\n        const masterUrl = stream?.master_url;\n        if (fileId && videoId && masterUrl) {\n          livePhotoTarget.push({\n            live_photo_file_id: fileId,\n            video_id: videoId,\n            url: masterUrl\n          });\n        }\n      }", "imagefeed live-photo property cache")


FUNCTION_SWITCH_MARKER = "// loon-change: Xiaohongshu v4 function-switch indexed scan v1;"

def optimize_v4_function_switch_indexed_scan(src):
    if FUNCTION_SWITCH_MARKER in src:
        start = src.index(FUNCTION_SWITCH_MARKER)
        end = src.find("\n      // 添加下载按钮", start)
        block = src[start:end] if end >= 0 else ""
        required = (
            FUNCTION_SWITCH_MARKER,
            "const functionSwitch = item?.function_switch;",
            "for (let switchIndex = 0; switchIndex < functionSwitch.length; switchIndex++)",
            "const switchItem = functionSwitch[switchIndex];",
            'if (switchItem.type === "video_download")',
            "if (switchItem.reason) delete switchItem.reason;",
        )
        if not block or any(token not in block for token in required) or "for (let switchItem of item.function_switch)" in block:
            raise ValueError("Xiaohongshu v4 function-switch marker is stale")
        return src
    old_block = """      if (item?.function_switch?.length > 0) {
        for (let switchItem of item.function_switch) {
          if (switchItem.type === "video_download") {
            switchItem.enable = true;
            if (switchItem.reason) delete switchItem.reason;
          }
        }
      }"""
    if src.count(old_block) != 1:
        raise ValueError("Xiaohongshu v4 function-switch loop anchor drift")
    new_block = """      // loon-change: Xiaohongshu v4 function-switch indexed scan v1;
      const functionSwitch = item?.function_switch;
      if (functionSwitch?.length > 0) {
        for (let switchIndex = 0; switchIndex < functionSwitch.length; switchIndex++) {
          const switchItem = functionSwitch[switchIndex];
          if (switchItem.type === "video_download") {
            switchItem.enable = true;
            if (switchItem.reason) delete switchItem.reason;
          }
        }
      }"""
    src = src.replace(old_block, new_block, 1)
    if FUNCTION_SWITCH_MARKER not in src or "for (let switchItem of item.function_switch)" in src:
        raise ValueError("Xiaohongshu v4 function-switch postcondition failed")
    return src


VIDEO_ENTRY_MARKER = "// loon-change: Xiaohongshu v4 video-feed function-entry scan without callback v1;"

def optimize_v4_video_feed_function_entry_scan(src):
    if VIDEO_ENTRY_MARKER in src:
        start = src.index(VIDEO_ENTRY_MARKER)
        end = src.find("\n      // 提取最佳视频流", start)
        block = src[start:end] if end >= 0 else ""
        required = (
            VIDEO_ENTRY_MARKER,
            "const functionEntries = item?.share_info?.function_entries;",
            "for (const entry of functionEntries)",
            'if (entry.type === "video_download")',
            'functionEntries.push({type: "video_download"});',
        )
        if not block or any(token not in block for token in required) or ".some(" in block:
            raise ValueError("Xiaohongshu v4 function-entry scan marker is stale")
        return src
    if src.count("      if (item?.share_info?.function_entries?.length > 0) {\n        const hasDownload = item.share_info.function_entries.some(entry => entry.type === \"video_download\");\n        if (!hasDownload) {\n          item.share_info.function_entries.push({type: \"video_download\"});\n        }\n      }") != 1:
        raise ValueError("Xiaohongshu v4 function-entry scan anchor drift")
    src = src.replace("      if (item?.share_info?.function_entries?.length > 0) {\n        const hasDownload = item.share_info.function_entries.some(entry => entry.type === \"video_download\");\n        if (!hasDownload) {\n          item.share_info.function_entries.push({type: \"video_download\"});\n        }\n      }", "      const functionEntries = item?.share_info?.function_entries;\n      if (functionEntries?.length > 0) {\n        let hasDownload = false;\n        for (const entry of functionEntries) {\n          if (entry.type === \"video_download\") {\n            hasDownload = true;\n            break;\n          }\n        }\n        if (!hasDownload) {\n          functionEntries.push({type: \"video_download\"});\n        }\n      }", 1)
    anchor = "      const functionEntries = item?.share_info?.function_entries;"
    if src.count(anchor) != 1:
        raise ValueError("Xiaohongshu v4 function-entry marker insertion anchor drift")
    return src.replace(anchor, VIDEO_ENTRY_MARKER + "\n" + anchor, 1)


COMMENT_NODE_ARRAY_MARKER = "// loon-change: Xiaohongshu comment node array classification cache v1;"

def optimize_comment_node_array_classification(src):
    if COMMENT_NODE_ARRAY_MARKER in src:
        if src.count(COMMENT_NODE_ARRAY_MARKER) != 1:
            raise ValueError("Xiaohongshu comment node array-classification marker drift")
        start = src.find("function processCommentTree(data, livePhotos, commentVideos, noteId)")
        end = src.find("\n\n\n/**", start)
        if start < 0:
            raise ValueError("Xiaohongshu comment processor missing")
        block = src[start:end if end >= 0 else len(src)]
        if block.count("Array.isArray(current)") != 1 or block.count("if (currentIsArray) {") != 1 or "const currentIsArray = Array.isArray(current);" not in block:
            raise ValueError("Xiaohongshu comment node array-classification marker/structure drift")
        return src
    start = src.find("function processCommentTree(data, livePhotos, commentVideos, noteId)")
    if start < 0:
        raise ValueError("Xiaohongshu comment processor missing")
    end = src.find("\n\n\n/**", start)
    if end < 0:
        raise ValueError("Xiaohongshu comment processor boundary missing")
    block = src[start:end]
    first = re.search(r"(?m)^([ \t]*)if \(!Array\.isArray\(current\)\) \{$", block)
    second = re.search(r"(?m)^([ \t]*)if \(Array\.isArray\(current\)\) \{$", block)
    if not first or not second or first.group(1) != second.group(1):
        raise ValueError("Xiaohongshu comment node array-classification anchor drift")
    indent = first.group(1)
    new_first = indent + COMMENT_NODE_ARRAY_MARKER + "\n" + indent + "const currentIsArray = Array.isArray(current);\n" + indent + "if (!currentIsArray) {"
    block = block[:first.start()] + new_first + block[first.end():]
    second = re.search(r"(?m)^([ \t]*)if \(Array\.isArray\(current\)\) \{$", block)
    if not second or second.group(1) != indent:
        raise ValueError("Xiaohongshu comment node array branch anchor drift")
    block = block[:second.start()] + indent + "if (currentIsArray) {" + block[second.end():]
    if block.count(COMMENT_NODE_ARRAY_MARKER) != 1 or block.count("Array.isArray(current)") != 1 or block.count("if (currentIsArray) {") != 1:
        raise ValueError("Xiaohongshu comment node array-classification postcondition failed")
    return src[:start] + block + src[end:]





def optimize_source(src,commit="unknown"):
    if MARKER in src:
        if "Object.keys(current)" in src: raise ValueError("Xiaohongshu traversal optimization is stale")
        has_comment_processor = "function processCommentTree(data, livePhotos, commentVideos, noteId)" in src
        has_no_visited_set = "const visited = new WeakSet()" not in src and "visited.has(current)" not in src
        if has_comment_processor and has_no_visited_set and "Xiaohongshu parsed JSON comment tree without visited WeakSet v1;" in src and "Xiaohongshu comment classification stack frames v1;" in src and "const commentFrameTag = {};" in src and "processCommentTree(obj.data, livePhotos, commentVideos, note_id);" in src:
            src = optimize_imagefeed_single_traversal(src)
            src = optimize_imagefeed_live_photo_property_cache(src)
            src = optimize_comment_video_info_cache(src)
            src = optimize_comment_media_property_cache(src)
            src = optimize_comment_stack_frame_allocation(src)
            src = optimize_comment_node_array_classification(src)
            src = optimize_video_save_cache_lookup(src)
            src = optimize_video_save_lazy_cache_parse(src)
            src = optimize_v4_video_feed_function_entry_scan(src)
            src = optimize_v4_function_switch_indexed_scan(src)
            return optimize_stream_selection_no_closure(src)
        src = apply_comment_optimization(src)
        src = optimize_comment_media_property_cache(src)
        src = optimize_imagefeed_single_traversal(src)
        src = optimize_imagefeed_live_photo_property_cache(src)
        src = optimize_comment_video_info_cache(src)
        src = optimize_comment_media_property_cache(src)
        src = optimize_comment_stack_frame_allocation(src)
        src = optimize_comment_node_array_classification(src)
        src = optimize_video_save_cache_lookup(src)
        src = optimize_video_save_lazy_cache_parse(src)
        src = optimize_v4_video_feed_function_entry_scan(src)
        src = optimize_v4_function_switch_indexed_scan(src)
        return optimize_stream_selection_no_closure(src)
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
    src=optimize_imagefeed_single_traversal(src)
    src=between(src,"function replaceUrlContent(collectionA, collectionB) {","\nfunction deduplicateLivePhotos(",URLMAP,"live-photo URL lookup")
    src=between(src,"function deduplicateLivePhotos(livePhotos) {","\nfunction replaceRedIdWithFmz200(",DEDUP,"live-photo dedup")
    src=optimize_stream_selection_no_closure(src)
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
    result = apply_comment_optimization(MARKER+commit+"\n"+src)
    result = optimize_comment_media_property_cache(result)
    result = optimize_imagefeed_live_photo_property_cache(optimize_imagefeed_single_traversal(result))
    result = optimize_comment_video_info_cache(result)
    result = optimize_comment_stack_frame_allocation(result)
    result = optimize_comment_node_array_classification(result)
    result = optimize_video_save_cache_lookup(result)
    result = optimize_video_save_lazy_cache_parse(result)
    result = optimize_v4_video_feed_function_entry_scan(result)
    result = optimize_v4_function_switch_indexed_scan(result)
    result = optimize_stream_selection_no_closure(result)
    for token in ("imageEnhance(images_list, livePhotoCache)", IMAGE_FEED_MARKER, "compactInPlace(obj.data","appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)","const byFileId=new Map()", "Xiaohongshu comment classification stack frames v1;", "const commentFrameTag = {};", "stack.push(true, comment, commentFrameTag);", "stack.push(false, subComment, commentFrameTag);", FUNCTION_SWITCH_MARKER, COMMENT_STACK_FRAME_MARKER, COMMENT_CACHE_MARKER, "let parsed = parsedVideoInfo.get(raw);", VIDEO_SAVE_LOOKUP_MARKER, VIDEO_SAVE_LAZY_PARSE_MARKER, "const noteId = obj.data?.note_id;", "for (let i = videoFeed.length - 1; i >= 0; i--)", STREAM_SELECTION_MARKER, "for (let pass = 0; pass < 2; pass++)"):
        if token not in result:raise ValueError("missing optimizer invariant: "+token)
    if "imageEnhance(JSON.stringify(images_list))" in result:raise ValueError("image-feed serialization round trip remains")
    if "for (const image of images_list)" in result:raise ValueError("image-feed second cache traversal remains")
    if "parsedVideoInfo.has(raw)" in result:raise ValueError("comment cache double lookup remains")
    if "for (let item of videoFeed)" in result:raise ValueError("video-save cache full scan remains")
    return result

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
