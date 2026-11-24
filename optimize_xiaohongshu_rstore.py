#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible hot-path optimization for the R-Store Xiaohongshu response handler."""
import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-rstore.js"
MARKER = "// loon-change: R-Store Xiaohongshu hot-path optimization v1; upstream zirawell/R-Store@"
COMMENT_TREE_MARKER = "// loon-change: Xiaohongshu parsed JSON tree traversal without visited WeakSet v1;"

HELPERS = r'''
function compactInPlace(items, keep) {
  let write = 0;
  for (let read = 0, length = items.length; read < length; read++) {
    const item = items[read];
    if (keep(item, read)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  items.length = write;
  return items;
}
function appendUniqueLivePhotos(existing, incoming) {
  const seen = new Set();
  compactInPlace(existing, item => {
    if (seen.has(item.videId)) return false;
    seen.add(item.videId);
    return true;
  });
  for (const item of incoming) {
    if (!seen.has(item.videId)) {
      seen.add(item.videId);
      existing.push(item);
    }
  }
  return existing;
}
'''

IMAGE = r'''// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1
function imageEnhance(images, livePhotoCache) {
  if (!images || typeof images !== "object") return images;
  const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;
  const quality = $.getdata("xiaohongshu.imageQuality");
  const originalPattern = /\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern = /imageView2\/2\/w\/\d+\/format/g;
  const heightPattern = /imageView2\/2\/h\/\d+\/format/g;
  let originalDone = false;
  const stack = [{value: images, index: 0, keys: null, root: true}];
  while (stack.length) {
    const frame = stack[stack.length - 1];
    const value = frame.value;
    if (Array.isArray(value)) {
      if (frame.index >= value.length) {
        stack.pop();
        continue;
      }
      const key = frame.index++;
      const child = value[key];
      if (frame.root && livePhotoTarget && child && typeof child === "object" && child.live_photo_file_id) {
        const livePhoto = child.live_photo;
        livePhotoTarget.push({
          file_id: child.live_photo_file_id,
          video_id: livePhoto?.media?.video_id,
          url: livePhoto?.media?.stream?.h265?.[0]?.master_url
        });
      }
      if (typeof child === "string" && child.includes("imageView2/2")) {
        if (quality === "original") {
          if (!originalDone) {
            const changed = child.replace(originalPattern, "?imageView2/0/format/png&redImage/frame/0");
            if (changed !== child) {
              value[key] = changed;
              originalDone = true;
            }
          }
        } else {
          value[key] = child.replace(widthPattern, "imageView2/2/w/2160/format")
            .replace(heightPattern, "imageView2/2/h/2160/format");
        }
      } else if (child && typeof child === "object") {
        stack.push({value: child, index: 0, keys: null, root: false});
      }
    } else {
      if (frame.keys === null) frame.keys = Object.keys(value);
      if (frame.index >= frame.keys.length) {
        stack.pop();
        continue;
      }
      const key = frame.keys[frame.index++];
      const child = value[key];
      if (typeof child === "string" && child.includes("imageView2/2")) {
        if (quality === "original") {
          if (!originalDone) {
            const changed = child.replace(originalPattern, "?imageView2/0/format/png&redImage/frame/0");
            if (changed !== child) {
              value[key] = changed;
              originalDone = true;
            }
          }
        } else {
          value[key] = child.replace(widthPattern, "imageView2/2/w/2160/format")
            .replace(heightPattern, "imageView2/2/h/2160/format");
        }
      } else if (child && typeof child === "object") {
        stack.push({value: child, index: 0, keys: null, root: false});
      }
    }
  }
  return images;
}'''

REPLACE_URL = r'''function replaceUrlContent(collectionA, collectionB) {
  const byFileId = new Map();
  for (const item of collectionB) {
    if (item && !byFileId.has(item.file_id)) byFileId.set(item.file_id, item);
  }
  for (const item of collectionA) {
    const found = byFileId.get(item.file_id);
    if (!found) continue;
    item.url = item.url !== ""
      ? item.url.replace(/^https?:\/\/.*\.mp4(\?[^"]*)?/g, found.url.match(/(.*)\.mp4/)[1] + ".mp4")
      : found.url;
  }
}'''

COMMENT_HELPER = r'''function cleanCommentsAndCollectLivePhotos(data) {
  const livePhotos = [];
  const stack = [data];
  // loon-change: Xiaohongshu parsed JSON tree traversal without visited WeakSet v1;
  // JSON.parse creates a tree: nodes cannot be cyclic or shared by reference.
  const commentNodes = new WeakSet();
  const topLevelComments = new WeakSet();
  const videoInfoCache = new Map();
  if (Array.isArray(data?.comments)) {
    for (const comment of data.comments) {
      if (comment && typeof comment === "object") {
        commentNodes.add(comment);
        topLevelComments.add(comment);
      }
    }
  }
  while (stack.length) {
    const current = stack.pop();
    if (!current || typeof current !== "object") continue;
    if (!Array.isArray(current) && "red_id" in current) delete current.red_id;
    if (commentNodes.has(current)) {
      if (current.comment_type === 3) current.comment_type = 2;
      if (current.media_source_type === 1) current.media_source_type = 0;
      if (current.pictures?.length > 0) {
        for (const picture of current.pictures) {
          if (!picture.video_id) continue;
          const rawVideoInfo = picture.video_info;
          if (!videoInfoCache.has(rawVideoInfo)) videoInfoCache.set(rawVideoInfo, JSON.parse(rawVideoInfo));
          const picObj = videoInfoCache.get(rawVideoInfo);
          const videoUrl = picObj.stream?.h265?.[0]?.master_url;
          if (videoUrl) livePhotos.push({videId: picture.video_id, videoUrl});
        }
      }
      if (topLevelComments.has(current) && Array.isArray(current.sub_comments)) {
        for (const subComment of current.sub_comments) {
          if (subComment && typeof subComment === "object") commentNodes.add(subComment);
        }
      }
    }
    if (Array.isArray(current)) {
      for (let index = current.length - 1; index >= 0; index--) {
        const child = current[index];
        if (child && typeof child === "object") stack.push(child);
      }
    } else {
      for (const key in current) {
        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;
        const child = current[key];
        if (child && typeof child === "object") stack.push(child);
      }
    }
  }
  return livePhotos;
}'''
DEDUP = r'''function deDuplicateLivePhotos(livePhotos) {
  const seen = new Set();
  return compactInPlace(livePhotos, item => {
    if (seen.has(item.videId)) return false;
    seen.add(item.videId);
    return true;
  });
}'''

def once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise ValueError("%s anchor drift: expected 1, found %d" % (label, count))
    return source.replace(old, new, 1)

def between(source, start, end, replacement, label):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("%s function boundary drift" % label)
    left = source.index(start)
    right = source.index(end, left + len(start))
    if right <= left:
        raise ValueError("%s function boundary order changed" % label)
    return source[:left] + replacement + "\n\n" + source[right:]

def apply_live_photo_cache_optimization(source):
    old = '''  livePhoto = JSON.parse(rsp);
  for (let item of livePhoto) {
    if (item.live_photo_file_id) {
      let myData = {
        file_id: item.live_photo_file_id,
        video_id: item.live_photo.media.video_id,
        url: item.live_photo.media.stream.h265[0].master_url
      };
      newDatas.push(myData);
    }
  }'''
    new = '''  livePhoto = JSON.parse(rsp);
  for (const item of livePhoto) {
    if (item?.file_id) {
      newDatas.push({
        file_id: item.file_id,
        video_id: item.video_id,
        url: item.url
      });
    }
  }'''
    if "const livePhotoCache = []" not in source:
        old_cache = '''      // Cache the original image URLs once, then mutate the parsed object in place.
      $.setdata(JSON.stringify(images_list), "redBookLivePhoto");
      imageEnhance(images_list);'''
        new_cache = '''      // Cache only fields consumed by the live-photo save endpoint.
      const livePhotoCache = [];
      if (Array.isArray(images_list)) {
        for (const image of images_list) {
          if (image?.live_photo_file_id) {
            livePhotoCache.push({
              file_id: image.live_photo_file_id,
              video_id: image.live_photo?.media?.video_id,
              url: image.live_photo?.media?.stream?.h265?.[0]?.master_url
            });
          }
        }
      }
      $.setdata(JSON.stringify(livePhotoCache), "redBookLivePhoto");
      imageEnhance(images_list);'''
        source = once(source, old_cache, new_cache, "compact live-photo cache writer")
    elif (
        'JSON.stringify(livePhotoCache), "redBookLivePhoto"' not in source
        or (
            "file_id: image.live_photo_file_id" not in source
            and "imageEnhance(images_list, livePhotoCache)" not in source
        )
    ):
        raise ValueError("compact live-photo cache writer drift")
    if "item?.file_id" not in source:
        source = once(source, old, new, "compact live-photo cache reader")
    elif "item.live_photo.media.stream.h265[0].master_url" in source:
        raise ValueError("legacy full live-photo cache reader remains")
    return source

IMAGE_FEED_MARKER = "// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1"

def optimize_imagefeed_single_traversal(source):
    if IMAGE_FEED_MARKER in source:
        required = (
            IMAGE_FEED_MARKER,
            "function imageEnhance(images, livePhotoCache)",
            "const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;",
            "frame.root && livePhotoTarget",
            "stack.push({value: child, index: 0, keys: null, root: false});",
            "imageEnhance(images_list, livePhotoCache);",
            'JSON.stringify(livePhotoCache), "redBookLivePhoto"',
        )
        if any(token not in source for token in required):
            raise ValueError("Xiaohongshu single-traversal image helper drifted; refusing overwrite")
        if "for (const image of images_list)" in source:
            raise ValueError("Separate Xiaohongshu live-photo image traversal remains")
        return source

    source = between(source, "function imageEnhance(images) {",
                     "function replaceUrlContent(", IMAGE, "single-traversal imageEnhance")
    old = '''      const images_list = obj.data[0].note_list[0].images_list;
      // Cache only fields consumed by the live-photo save endpoint.
      const livePhotoCache = [];
      for (const image of images_list) {
        if (image?.live_photo_file_id) {
          livePhotoCache.push({
            file_id: image.live_photo_file_id,
            video_id: image.live_photo?.media?.video_id,
            url: image.live_photo?.media?.stream?.h265?.[0]?.master_url
          });
        }
      }
      $.setdata(JSON.stringify(livePhotoCache), "redBookLivePhoto");
      imageEnhance(images_list);'''
    new = '''      const images_list = obj.data[0].note_list[0].images_list;
      // Collect live-photo save fields during the image-enhancement traversal.
      const livePhotoCache = [];
      imageEnhance(images_list, livePhotoCache);
      $.setdata(JSON.stringify(livePhotoCache), "redBookLivePhoto");'''
    return once(source, old, new, "single-traversal imagefeed live-photo extraction")

def optimize_video_save_lookup(source):
    """Stop scanning the cached feed as soon as the requested note is found."""
    old = """      if (item.id === obj.data.note_id) {
        obj.data.download_url = item.url;
      }"""
    new = """      if (item.id === obj.data.note_id) {
        obj.data.download_url = item.url;
        break;
      }"""
    if old in source:
        return once(source, old, new, "video-save cache lookup")
    if new not in source:
        raise ValueError("R-Store video-save lookup anchor drift; refusing optimization")
    return source


def optimize_source(source, commit="unknown"):
    COMMENT_BRANCH = r"""} else if (url.includes("/note/comment")) {
  const commentData = obj.data;
  const livePhotos = cleanCommentsAndCollectLivePhotos(commentData);
  const note_id = commentData?.comments?.[0]?.note_id || "";
  if (livePhotos.length > 0) {
    let commitsRsp;
    const commitsCache = $.getdata("xiaohongshu.comments.rsp");
    if (!commitsCache) {
      commitsRsp = {noteId: note_id, livePhotos: livePhotos};
    } else {
      commitsRsp = JSON.parse(commitsCache);
      if (commitsRsp.noteId === note_id) {
        commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);
      } else {
        commitsRsp = {noteId: note_id, livePhotos: livePhotos};
      }
    }
    $.setdata(JSON.stringify(commitsRsp), "xiaohongshu.comments.rsp");
  }
"""
    if MARKER in source:
        source = optimize_video_save_lookup(source)
        required = ("imageEnhance(images)", "compactInPlace(obj.data", "appendUniqueLivePhotos",
                    "const byFileId = new Map()", "function cleanCommentsAndCollectLivePhotos(data)",
                    "const videoInfoCache = new Map()")
        if any(token not in source for token in required):
            raise ValueError("marked R-Store Xiaohongshu source is incomplete")
        if "function removeRedId(obj) {" in source:
            source = between(source, "function removeRedId(obj) {", "function Env(", COMMENT_HELPER, "comment helper")
        elif "function cleanCommentsAndCollectLivePhotos(data) {" in source:
            source = between(source, "function cleanCommentsAndCollectLivePhotos(data) {",
                             "function Env(", COMMENT_HELPER, "comment helper refresh")
        else:
            raise ValueError("R-Store comment traversal helper anchor missing; refusing upgrade")
        source = between(source, '} else if (url.includes("/note/comment")) {',
                         '} else if (url.includes("/interaction/comment/video/download")) {',
                         COMMENT_BRANCH, "comment branch")
        source = apply_live_photo_cache_optimization(source)
        source = optimize_imagefeed_single_traversal(source)
        if (COMMENT_TREE_MARKER not in source or "visited.has(current)" in source or "const visited = new WeakSet()" in source):
            raise ValueError("comment traversal still allocates/checks a visited WeakSet")
        source = source.replace("if (!$response.body) $done({});" + chr(10), "")
        guard = "if (!$response.body) { $done({}); } else {"
        if guard not in source:
            source = once(source, "const url = $request.url;", "const url = $request.url;\n" + guard,
                          "terminal empty-body guard")
            source = once(source, "\n\n// 小红书画质增强：加载2K分辨率的图片",
                          "\n}\n\n// 小红书画质增强：加载2K分辨率的图片",
                          "terminal empty-body guard close")
        return source
    source = once(source, "const url = $request.url;",
                  "const url = $request.url;\n" + HELPERS.strip(), "array helpers")
    source = optimize_video_save_lookup(source)

    image_block = '''      const images_list = obj.data[0].note_list[0].images_list;
      // 画质增强
      obj.data[0].note_list[0].images_list = imageEnhance(JSON.stringify(images_list));
      // 保存无水印信息
      $.setdata(JSON.stringify(images_list), "redBookLivePhoto");'''
    image_replacement = '''      const images_list = obj.data[0].note_list[0].images_list;
      // Collect live-photo save fields during the image-enhancement traversal.
      const livePhotoCache = [];
      imageEnhance(images_list, livePhotoCache);
      $.setdata(JSON.stringify(livePhotoCache), "redBookLivePhoto");'''
    source = once(source, image_block, image_replacement, "image-feed JSON round trip")
    source = apply_live_photo_cache_optimization(source)

    source = once(
        source,
        'obj.data.items = obj.data.items.filter((i) => i?.recommend_reason === "friend_post");',
        'compactInPlace(obj.data.items, item => item?.recommend_reason === "friend_post");',
        "follow feed filter")
    source = once(
        source,
        'obj.data.items = obj.data.items.filter((i) => !["recommend_user"]?.includes(i.recommend_reason));',
        'compactInPlace(obj.data.items, item => item?.recommend_reason !== "recommend_user");',
        "follow list filter")
    source = once(
        source,
        'obj.data.items = obj.data.items.filter((i) => i.model_type === "note");',
        'compactInPlace(obj.data.items, item => item?.model_type === "note");',
        "search result filter")
    source = once(
        source,
        'item.hash_tag = item.hash_tag.filter(tag => tag.type !== "interact_vote");',
        'compactInPlace(item.hash_tag, tag => tag?.type !== "interact_vote");',
        "hashtag filter")

    home_old = '''    let newItems = [];
    for (let item of obj.data) {
      // 信息流-直播
      if (item?.model_type === "live_v2") {
        continue;
        // 信息流-赞助
      } else if (item?.hasOwnProperty("ads_info")) {
        continue;
        // 信息流-带货
      } else if (item?.hasOwnProperty("card_icon")) {
        continue;
        // 信息流-商品
      } else if (item?.note_attributes?.includes("goods")) {
        continue;
      } else {
        if (item?.related_ques) {
          delete item.related_ques;
        }
        newItems.push(item);
      }
    }
    obj.data = newItems;'''
    home_new = '''    compactInPlace(obj.data, item => {
      if (!item) return true;
      if (item.model_type === "live_v2" ||
          Object.prototype.hasOwnProperty.call(item, "ads_info") ||
          Object.prototype.hasOwnProperty.call(item, "card_icon") ||
          item.note_attributes?.includes("goods")) return false;
      if (item.related_ques) delete item.related_ques;
      return true;
    });'''
    source = once(source, home_old, home_new, "homefeed allocation")

    sort_old = '''          // 分辨率从高到低排序
          const sortedList = h265List.filter(v => !!v.master_url && !!v.height).sort((a, b) => b.height - a.height);
          // 选择分辨率最高的
          let selectedStream = sortedList[0];'''
    sort_new = '''          // Select the highest-resolution stream in one pass; preserve first item on ties.
          let selectedStream = null;
          for (const stream of h265List) {
            if (!stream || !stream.master_url || !stream.height) continue;
            if (!selectedStream || Number(stream.height) > Number(selectedStream.height)) {
              selectedStream = stream;
            }
          }'''
    source = once(source, sort_old, sort_new, "video stream sort")

    source = between(source, "function imageEnhance(jsonStr) {",
                     "\nfunction replaceUrlContent(", IMAGE, "imageEnhance")
    source = between(source, "function replaceUrlContent(collectionA, collectionB) {",
                     "\nfunction deDuplicateLivePhotos(", REPLACE_URL, "live-photo lookup")
    source = between(source, "function deDuplicateLivePhotos(livePhotos) {",
                     "\nfunction removeRedId(", DEDUP, "live-photo deduplication")
    source = between(source, "function removeRedId(obj) {",
                     "function Env(", COMMENT_HELPER, "comment helper")
    source = between(source, '} else if (url.includes("/note/comment")) {',
                     '} else if (url.includes("/interaction/comment/video/download")) {',
                     COMMENT_BRANCH, "comment branch")
    source = source.replace("if (!$response.body) $done({});" + chr(10), "")
    guard = "if (!$response.body) { $done({}); } else {"
    if guard not in source:
        source = once(source, "const url = $request.url;", "const url = $request.url;\n" + guard,
                      "terminal empty-body guard")
        source = once(source, "\n\n// 小红书画质增强：加载2K分辨率的图片",
                      "\n}\n\n// 小红书画质增强：加载2K分辨率的图片",
                      "terminal empty-body guard close")

    result = MARKER + commit + "\n" + source
    invariants = (
        "imageEnhance(images_list, livePhotoCache)", "compactInPlace(obj.data",
        "appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)",
        "const byFileId = new Map()", "const stack = [data]",
        COMMENT_TREE_MARKER, "selectedStream = null",
    )
    for token in invariants:
        if token not in result:
            raise ValueError("missing optimization invariant: " + token)
    if "imageEnhance(JSON.stringify(images_list))" in result:
        raise ValueError("image-feed JSON round trip remains")
    if ".filter(v => !!v.master_url && !!v.height).sort(" in result:
        raise ValueError("video filter/sort allocation remains")
    if "const visited = new WeakSet()" in result or "visited.has(current)" in result:
        raise ValueError("comment traversal visited WeakSet overhead remains")
    return result

def rewrite_plugin(plugin):
    if LOCAL in plugin:
        if REMOTE in plugin:
            raise ValueError("mixed local and upstream Xiaohongshu script URLs")
        return plugin
    section = None
    count = 0
    output = []
    for line in plugin.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip().lower()
        if section == "script" and REMOTE in line:
            count += line.count(REMOTE)
            line = line.replace(REMOTE, LOCAL)
        output.append(line)
    if count != 10:
        raise ValueError("R-Store Xiaohongshu trigger inventory changed: expected 10, got %d" % count)
    result = "\n".join(output)
    if REMOTE in result:
        raise ValueError("R-Store Xiaohongshu URL remains after local routing")
    return result + ("\n" if plugin.endswith("\n") else "")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source")
    parser.add_argument("--output")
    parser.add_argument("--upstream-commit", default="unknown")
    parser.add_argument("--plugin")
    args = parser.parse_args()
    if args.source or args.output:
        if not args.source or not args.output:
            parser.error("--source and --output must be supplied together")
        result = optimize_source(Path(args.source).read_text(encoding="utf-8-sig"), args.upstream_commit)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized R-Store Xiaohongshu source", len(result))
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Routed 10 R-Store Xiaohongshu response triggers to the local optimized script")
    if not (args.source or args.output or args.plugin):
        parser.error("provide --source/--output and/or --plugin")

if __name__ == "__main__":
    main()
