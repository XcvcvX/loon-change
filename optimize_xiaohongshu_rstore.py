#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible hot-path optimization for the R-Store Xiaohongshu response handler."""
import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xiaohongshu.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xiaohongshu/xiaohongshu-rstore.js"
MARKER = "// loon-change: R-Store Xiaohongshu hot-path optimization v1; upstream zirawell/R-Store@"

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

IMAGE = r'''function imageEnhance(images) {
  if (!images || typeof images !== "object") return images;
  const quality = $.getdata("xiaohongshu.imageQuality");
  const originalPattern = /\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern = /imageView2\/2\/w\/\d+\/format/g;
  const heightPattern = /imageView2\/2\/h\/\d+\/format/g;
  let originalDone = false;
  const stack = [{value: images, index: 0, keys: null}];
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
        stack.push({value: child, index: 0, keys: null});
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
        stack.push({value: child, index: 0, keys: null});
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

REMOVE_RED_ID = r'''function removeRedId(obj) {
  const stack = [obj];
  while (stack.length) {
    const current = stack.pop();
    if (Array.isArray(current)) {
      for (let index = current.length - 1; index >= 0; index--) {
        const child = current[index];
        if (child && typeof child === "object") stack.push(child);
      }
    } else if (current && typeof current === "object") {
      if ("red_id" in current) delete current.red_id;
      for (const key in current) {
        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;
        const child = current[key];
        if (child && typeof child === "object") stack.push(child);
      }
    }
  }
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

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        required = ("imageEnhance(images)", "compactInPlace(obj.data", "appendUniqueLivePhotos",
                    "const byFileId = new Map()", "const stack = [obj]")
        if any(token not in source for token in required):
            raise ValueError("marked R-Store Xiaohongshu source is incomplete")
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

    image_block = '''      const images_list = obj.data[0].note_list[0].images_list;
      // 画质增强
      obj.data[0].note_list[0].images_list = imageEnhance(JSON.stringify(images_list));
      // 保存无水印信息
      $.setdata(JSON.stringify(images_list), "redBookLivePhoto");'''
    image_replacement = '''      const images_list = obj.data[0].note_list[0].images_list;
      // Cache the original image URLs once, then mutate the parsed object in place.
      $.setdata(JSON.stringify(images_list), "redBookLivePhoto");
      imageEnhance(images_list);'''
    source = once(source, image_block, image_replacement, "image-feed JSON round trip")

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
                     "\n\nfunction Env(", REMOVE_RED_ID, "comment tree traversal")

    source = once(
        source,
        "commitsRsp.livePhotos = deDuplicateLivePhotos(commitsRsp.livePhotos.concat(livePhotos));",
        "commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);",
        "live-photo cache merge")

    source = once(source, "const url = $request.url;",
                  "const url = $request.url;\nif (!$response.body) { $done({}); } else {",
                  "terminal empty-body guard")
    source = once(source, "\n\n// 小红书画质增强：加载2K分辨率的图片",
                  "\n}\n\n// 小红书画质增强：加载2K分辨率的图片",
                  "terminal empty-body guard close")

    result = MARKER + commit + "\n" + source
    invariants = (
        "imageEnhance(images_list)", "compactInPlace(obj.data",
        "appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos)",
        "const byFileId = new Map()", "const stack = [obj]",
        "selectedStream = null",
    )
    for token in invariants:
        if token not in result:
            raise ValueError("missing optimization invariant: " + token)
    if "imageEnhance(JSON.stringify(images_list))" in result:
        raise ValueError("image-feed JSON round trip remains")
    if ".filter(v => !!v.master_url && !!v.height).sort(" in result:
        raise ValueError("video filter/sort allocation remains")
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
