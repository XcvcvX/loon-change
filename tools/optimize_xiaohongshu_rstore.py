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
// loon-change: Xiaohongshu image traversal array-frame length cache v1
function imageEnhance(images, livePhotoCache) {
  if (!images || typeof images !== "object") return images;
  const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;
  const quality = $.getdata("xiaohongshu.imageQuality");
  const originalPattern = /\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern = /imageView2\/2\/w\/\d+\/format/g;
  const heightPattern = /imageView2\/2\/h\/\d+\/format/g;
  let originalDone = false;
  const stack = [{value: images, index: 0, keys: null, length: Array.isArray(images) ? images.length : 0, root: true}];
  while (stack.length) {
    const frame = stack[stack.length - 1];
    const value = frame.value;
    if (Array.isArray(value)) {
      if (frame.index >= frame.length) {
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
        stack.push({value: child, index: 0, keys: null, length: Array.isArray(child) ? child.length : 0, root: false});
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
        stack.push({value: child, index: 0, keys: null, length: Array.isArray(child) ? child.length : 0, root: false});
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

COMMENT_ARRAY_LENGTH_MARKER = "// loon-change: Xiaohongshu comment traversal cached array lengths v1"

COMMENT_HELPER = r'''function cleanCommentsAndCollectLivePhotos(data) {
  const livePhotos = [];
  const commentFrameTag = {};
  const videoInfoCache = new Map();
  // loon-change: Xiaohongshu parsed JSON tree traversal without visited WeakSet v1;
  // loon-change: Xiaohongshu flat comment stack frames v2;
  // JSON.parse creates a tree: nodes cannot be cyclic or shared by reference.
  // Only top-level comments and their direct sub-comments receive comment frames.
  const stack = [data];
  while (stack.length) {
    const entry = stack.pop();
    // Flat metadata slots avoid allocating a three-element tuple per comment.
    const isCommentFrame = (entry === true || entry === false) &&
      stack[stack.length - 1] === commentFrameTag;
    const isTopLevelComment = isCommentFrame && entry === true;
    let current = entry;
    let commentPictures = null;
    if (isCommentFrame) {
      stack.pop(); // commentFrameTag
      current = stack.pop();
    }
    if (!current || typeof current !== "object") continue;
    if (!Array.isArray(current) && "red_id" in current) delete current.red_id;
    if (isCommentFrame) {
      if (current.comment_type === 3) current.comment_type = 2;
      if (current.media_source_type === 1) current.media_source_type = 0;
      // loon-change: Xiaohongshu comment pictures reference cache v1
      commentPictures = current.pictures;
      // loon-change: Xiaohongshu comment traversal cached array lengths v1
      const commentPictureCount = commentPictures?.length || 0;
      if (commentPictureCount > 0) {
        for (let pictureIndex = 0; pictureIndex < commentPictureCount; pictureIndex++) {
          const picture = commentPictures[pictureIndex];
          if (picture && typeof picture === "object" && "red_id" in picture) delete picture.red_id;
          const videoId = picture.video_id;
          if (!videoId) continue;
          // loon-change: Xiaohongshu comment video-info cache single lookup v1
          const rawVideoInfo = picture.video_info;
          let picObj = videoInfoCache.get(rawVideoInfo);
          if (picObj === undefined) {
            picObj = JSON.parse(rawVideoInfo);
            videoInfoCache.set(rawVideoInfo, picObj);
          }
          const videoUrl = picObj.stream?.h265?.[0]?.master_url;
          if (videoUrl) livePhotos.push({videId: videoId, videoUrl});
        }
      }
    }
    if (Array.isArray(current)) {
      const currentLength = current.length;
      for (let index = currentLength - 1; index >= 0; index--) {
        const child = current[index];
        if (child && typeof child === "object") stack.push(child);
      }
    } else {
      for (const key in current) {
        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;
        // Comment pictures were already traversed in the cached-length video pass.
        // Clean their direct red_id fields there and do not schedule the same array again.
        if (isCommentFrame && key === "pictures") continue;
        const child = current[key];
        if (!child || typeof child !== "object") continue;
        if (current === data && key === "comments" && Array.isArray(child)) {
          const commentCount = child.length;
          for (let index = commentCount - 1; index >= 0; index--) {
            const comment = child[index];
            if (comment && typeof comment === "object") stack.push(comment, commentFrameTag, true);
          }
        } else if (isCommentFrame && isTopLevelComment && key === "sub_comments" && Array.isArray(child)) {
          const subCommentCount = child.length;
          for (let index = subCommentCount - 1; index >= 0; index--) {
            const subComment = child[index];
            if (subComment && typeof subComment === "object") stack.push(subComment, commentFrameTag, false);
          }
        } else stack.push(child);
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
IMAGE_ARRAY_LENGTH_MARKER = "// loon-change: Xiaohongshu image traversal array-frame length cache v1"

def optimize_imagefeed_single_traversal(source):
    if IMAGE_FEED_MARKER in source:
        if IMAGE_ARRAY_LENGTH_MARKER not in source:
            source = between(source, "function imageEnhance(images, livePhotoCache) {",
                             "function replaceUrlContent(", IMAGE, "image traversal array-length cache")
        required = (
            IMAGE_FEED_MARKER,
            IMAGE_ARRAY_LENGTH_MARKER,
            "function imageEnhance(images, livePhotoCache)",
            "const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;",
            "length: Array.isArray(images) ? images.length : 0",
            "if (frame.index >= frame.length)",
            "length: Array.isArray(child) ? child.length : 0",
            "frame.root && livePhotoTarget",
            "imageEnhance(images_list, livePhotoCache);",
            'JSON.stringify(livePhotoCache), "redBookLivePhoto"',
        )
        if any(token not in source for token in required):
            raise ValueError("Xiaohongshu single-traversal image helper drifted; refusing overwrite")
        if "if (frame.index >= value.length)" in source or "for (const image of images_list)" in source:
            raise ValueError("Repeated image-array traversal or live-photo image traversal remains")
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


VIDEO_SAVE_LOOKUP_MARKER = "// loon-change: Xiaohongshu video-save cached response and note ID v1"
VIDEO_SAVE_LOOKUP_OLD_WITH_BREAK = """} else if (url.includes("/note/video/save")) {
  let videoFeed = JSON.parse($.getdata("redBookVideoFeed")); // 读取持久化存储
  if (obj.data?.note_id !== "" && videoFeed?.length > 0) {
    for (let item of videoFeed) {
      if (item.id === obj.data.note_id) {
        obj.data.download_url = item.url;
        break;
      }
    }
  }
  // 解除下载限制
  if (obj.data?.disable) {
    delete obj.data.disable;
    delete obj.data.msg;
    obj.data.status = 2;
  }"""
VIDEO_SAVE_LOOKUP_OLD_WITHOUT_BREAK = """} else if (url.includes("/note/video/save")) {
  let videoFeed = JSON.parse($.getdata("redBookVideoFeed")); // 读取持久化存储
  if (obj.data?.note_id !== "" && videoFeed?.length > 0) {
    for (let item of videoFeed) {
      if (item.id === obj.data.note_id) {
        obj.data.download_url = item.url;
      }
    }
  }
  // 解除下载限制
  if (obj.data?.disable) {
    delete obj.data.disable;
    delete obj.data.msg;
    obj.data.status = 2;
  }"""
VIDEO_SAVE_LOOKUP_NEW = """} else if (url.includes("/note/video/save")) {
  // loon-change: Xiaohongshu video-save cached response and note ID v1
  const saveData = obj.data;
  const noteId = saveData?.note_id;
  const videoFeed = JSON.parse($.getdata("redBookVideoFeed"));
  const videoFeedLength = videoFeed?.length || 0;
  if (noteId !== "" && videoFeedLength > 0) {
    for (let read = 0; read < videoFeedLength; read++) {
      const item = videoFeed[read];
      if (item.id === noteId) {
        saveData.download_url = item.url;
        break;
      }
    }
  }
  // 解除下载限制
  if (saveData?.disable) {
    delete saveData.disable;
    delete saveData.msg;
    saveData.status = 2;
  }"""

def optimize_video_save_lookup(source):
    """Cache the response data, note ID and feed length before an indexed early-exit search."""
    required = (
        VIDEO_SAVE_LOOKUP_MARKER,
        "const saveData = obj.data;",
        "const noteId = saveData?.note_id;",
        "const videoFeedLength = videoFeed?.length || 0;",
        "for (let read = 0; read < videoFeedLength; read++)",
        "const item = videoFeed[read];",
        "if (item.id === noteId)",
        "saveData.download_url = item.url;",
        "if (saveData?.disable)",
    )
    if VIDEO_SAVE_LOOKUP_MARKER in source:
        if source.count(VIDEO_SAVE_LOOKUP_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Xiaohongshu video-save lookup structure drift")
        if "obj.data.note_id" in source or "obj.data.download_url" in source or "for (let item of videoFeed)" in source:
            raise ValueError("Xiaohongshu repeated video-save response reads remain")
        return source
    if source.count(VIDEO_SAVE_LOOKUP_OLD_WITH_BREAK) == 1:
        old = VIDEO_SAVE_LOOKUP_OLD_WITH_BREAK
    elif source.count(VIDEO_SAVE_LOOKUP_OLD_WITHOUT_BREAK) == 1:
        old = VIDEO_SAVE_LOOKUP_OLD_WITHOUT_BREAK
    else:
        raise ValueError("R-Store video-save lookup anchor drift; refusing optimization")
    source = source.replace(old, VIDEO_SAVE_LOOKUP_NEW, 1)
    if source.count(VIDEO_SAVE_LOOKUP_MARKER) != 1 or any(token not in source for token in required):
        raise ValueError("Xiaohongshu video-save lookup postcondition failed")
    return source

XIAOHONGSHU_V4_FUNCTION_ENTRY_MARKER = "// loon-change: Xiaohongshu v4 function-entry indexed scan v1"
OLD_V4_FUNCTION_ENTRY_BLOCK = """          if (item?.share_info?.function_entries?.length > 0) {
            const hasDownload = item.share_info.function_entries.some(entry => entry.type === "video_download");
            if (!hasDownload) {
              item.share_info.function_entries.push({type: "video_download"});
            }
          }"""
NEW_V4_FUNCTION_ENTRY_BLOCK = """          // loon-change: Xiaohongshu v4 function-entry indexed scan v1
          const shareInfo = item?.share_info;
          const functionEntries = shareInfo?.function_entries;
          const functionEntryCount = functionEntries?.length || 0;
          if (functionEntryCount > 0) {
            let hasDownload = false;
            for (let entryIndex = 0; entryIndex < functionEntryCount; entryIndex++) {
              const entry = functionEntries[entryIndex];
              if (entry.type === "video_download") {
                hasDownload = true;
                break;
              }
            }
            if (!hasDownload) {
              functionEntries.push({type: "video_download"});
            }
          }"""

def optimize_v4_function_entry_scan(source):
    """Cache V4 share-info/entries references and replace per-item some callbacks with an indexed scan."""
    marker = XIAOHONGSHU_V4_FUNCTION_ENTRY_MARKER
    required = (
        marker,
        "const shareInfo = item?.share_info;",
        "const functionEntries = shareInfo?.function_entries;",
        "const functionEntryCount = functionEntries?.length || 0;",
        "for (let entryIndex = 0; entryIndex < functionEntryCount; entryIndex++)",
        "const entry = functionEntries[entryIndex];",
        'if (entry.type === "video_download")',
        'functionEntries.push({type: "video_download"});',
    )
    if marker in source:
        if source.count(marker) != 1 or any(token not in source for token in required):
            raise ValueError("Xiaohongshu V4 function-entry scan structure drift")
        if "functionEntries.some(" in source or "item.share_info.function_entries.some(" in source:
            raise ValueError("Xiaohongshu V4 some callback remains")
        return source
    if source.count(OLD_V4_FUNCTION_ENTRY_BLOCK) != 1:
        if '.some(entry => entry.type === "video_download")' in source:
            raise ValueError("Xiaohongshu V4 function-entry anchor drift")
        return source
    source = source.replace(OLD_V4_FUNCTION_ENTRY_BLOCK, NEW_V4_FUNCTION_ENTRY_BLOCK, 1)
    if source.count(marker) != 1 or any(token not in source for token in required):
        raise ValueError("Xiaohongshu V4 function-entry scan postcondition failed")
    if "functionEntries.some(" in source or "item.share_info.function_entries.some(" in source:
        raise ValueError("Xiaohongshu V4 some callback remains")
    return source


VIDEO_FEED_HOTPATH_MARKER = "// loon-change: Xiaohongshu V3/V4 video-feed hot-path reference cache v1"

def optimize_videofeed_hotpath_references(source):
    """Cache V3/V4 video-feed arrays, per-item nested references, and H.265 stream fields."""
    start = '} else if (url.includes("/note/videofeed")) {'
    end = '// 视频保存请求\n} else if (url.includes("/note/video/save")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Xiaohongshu video-feed route boundary drift")
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    required = (
        VIDEO_FEED_HOTPATH_MARKER,
        "const videoFeedItemsV3 = obj?.data;",
        "const videoFeedItemsV3Length = videoFeedItemsV3?.length || 0;",
        "const mediaSaveConfig = item?.media_save_config;",
        "const shareInfo = item?.share_info;",
        "const functionEntries = shareInfo?.function_entries;",
        "const functionEntryCount = functionEntries?.length || 0;",
        "if (functionEntryCount > 0)",
        "const videoFeedItemsV4 = obj?.data;",
        "const videoFeedItemsV4Length = videoFeedItemsV4?.length || 0;",
        "const videoInfoV2 = item?.video_info_v2;",
        "const h265ListLength = Array.isArray(h265List) ? h265List.length : 0;",
        "const streamUrl = stream.master_url;",
        "const rawHeight = stream.height;",
        "const noteId = item?.id;",
    )
    if VIDEO_FEED_HOTPATH_MARKER in block:
        if block.count(VIDEO_FEED_HOTPATH_MARKER) != 1 or any(token not in block for token in required):
            raise ValueError("Xiaohongshu video-feed cache structure drift")
        forbidden = (
            "for (let item of obj.data)",
            "if (obj?.data?.length > 0)",
            "if (obj.data?.length > 0)",
            "item?.share_info?.function_entries",
            "item.media_save_config.",
            "item.share_info.function_entries",
            "item?.video_info_v2?.media?.stream?.h265",
            "stream.master_url || !stream.height",
            "Number(stream.height)",
            "selectedStream?.master_url",
        )
        if any(token in block for token in forbidden):
            raise ValueError("Xiaohongshu repeated video-feed response reads remain")
        return source
    oldV3 = '''    if (obj?.data?.length > 0) {
      for (let item of obj.data) {
        if (item?.media_save_config) {
          // 水印开关
          item.media_save_config.disable_save = false;
          item.media_save_config.disable_watermark = true;
          item.media_save_config.disable_weibo_cover = true;
        }
        if (item?.share_info?.function_entries?.length > 0) {
          // 下载限制
          const additem = {type: "video_download"};
          let func = item.share_info.function_entries[0];
          if (func?.type !== "video_download") {
            // 向数组开头添加对象
            item.share_info.function_entries.unshift(additem);
          }
        }
      }
    }'''
    newV3 = '''    // loon-change: Xiaohongshu V3 video-feed cached item references v1
    const videoFeedItemsV3 = obj?.data;
    const videoFeedItemsV3Length = videoFeedItemsV3?.length || 0;
    if (videoFeedItemsV3Length > 0) {
      for (let itemIndex = 0; itemIndex < videoFeedItemsV3Length; itemIndex++) {
        const item = videoFeedItemsV3[itemIndex];
        const mediaSaveConfig = item?.media_save_config;
        if (mediaSaveConfig) {
          // 水印开关
          mediaSaveConfig.disable_save = false;
          mediaSaveConfig.disable_watermark = true;
          mediaSaveConfig.disable_weibo_cover = true;
        }
        const shareInfo = item?.share_info;
        const functionEntries = shareInfo?.function_entries;
        const functionEntriesLength = functionEntries?.length || 0;
        if (functionEntriesLength > 0) {
          // 下载限制
          const additem = {type: "video_download"};
          const func = functionEntries[0];
          if (func?.type !== "video_download") {
            // 向数组开头添加对象
            functionEntries.unshift(additem);
          }
        }
      }
    }'''
    oldV4Start = '    let videoData = [];\n    if (obj.data?.length > 0) {'
    oldV4End = '        $.setdata(JSON.stringify(videoData), "redBookVideoFeed");\n    }'
    newV4 = '''    let videoData = [];
    // loon-change: Xiaohongshu V4 video-feed cached item references v1
    const videoFeedItemsV4 = obj?.data;
    const videoFeedItemsV4Length = videoFeedItemsV4?.length || 0;
    if (videoFeedItemsV4Length > 0) {
        for (let itemIndex = 0; itemIndex < videoFeedItemsV4Length; itemIndex++) {
          const item = videoFeedItemsV4[itemIndex];
          // 添加下载按钮（如果未存在）
          // loon-change: Xiaohongshu v4 function-entry indexed scan v1
          const shareInfo = item?.share_info;
          const functionEntries = shareInfo?.function_entries;
          const functionEntryCount = functionEntries?.length || 0;
          if (functionEntryCount > 0) {
            let hasDownload = false;
            for (let entryIndex = 0; entryIndex < functionEntryCount; entryIndex++) {
              const entry = functionEntries[entryIndex];
              if (entry.type === "video_download") {
                hasDownload = true;
                break;
              }
            }
            if (!hasDownload) {
              functionEntries.push({type: "video_download"});
            }
          }
    
          // 提取 H.265 视频流
          const videoInfoV2 = item?.video_info_v2;
          const mediaInfo = videoInfoV2?.media;
          const streamInfo = mediaInfo?.stream;
          const h265List = streamInfo?.h265 || [];
          const h265ListLength = Array.isArray(h265List) ? h265List.length : 0;
          if (h265ListLength === 0) {
            continue;
          }
    
          // Select the highest-resolution stream in one pass; preserve first item on ties.
          let selectedStreamUrl = "";
          let selectedHeight = -Infinity;
          for (let streamIndex = 0; streamIndex < h265ListLength; streamIndex++) {
            const stream = h265List[streamIndex];
            if (!stream) continue;
            const streamUrl = stream.master_url;
            const rawHeight = stream.height;
            if (!streamUrl || !rawHeight) continue;
            const streamHeight = Number(rawHeight);
            if (streamHeight > selectedHeight) {
              selectedStreamUrl = streamUrl;
              selectedHeight = streamHeight;
            }
          }
    
          // 存入缓存数组
          const noteId = item?.id;
          if (noteId && selectedStreamUrl) {
            videoData.push({id: noteId, url: selectedStreamUrl});
          }
        }
        // 写入本地持久化缓存
        $.setdata(JSON.stringify(videoData), "redBookVideoFeed");
    }'''
    if source.count(oldV3) != 1:
        raise ValueError("Xiaohongshu V3 video-feed cache anchor drift")
    source = source.replace(oldV3, newV3, 1)
    if source.count(oldV4Start) != 1 or source.count(oldV4End) != 1:
        raise ValueError("Xiaohongshu V4 video-feed cache anchor drift")
    leftV4 = source.index(oldV4Start)
    rightV4 = source.index(oldV4End, leftV4) + len(oldV4End)
    source = source[:leftV4] + newV4 + source[rightV4:]
    left = source.index(start)
    right = source.index(end, left + len(start))
    block = source[left:right]
    block = block.replace(start, start + "\n  " + VIDEO_FEED_HOTPATH_MARKER, 1)
    if any(token not in block for token in required):
        raise ValueError("Xiaohongshu video-feed cache postcondition failed")
    return source[:left] + block + source[right:]


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
        source = optimize_v4_function_entry_scan(source)
        source = optimize_videofeed_hotpath_references(source)
        required = ("function imageEnhance(images, livePhotoCache)", "compactInPlace(obj.data", "appendUniqueLivePhotos",
                    "const byFileId = new Map()", "function cleanCommentsAndCollectLivePhotos(data)",
                    "const videoInfoCache = new Map()", "let commentPictures = null;", "commentPictures = current.pictures;", COMMENT_ARRAY_LENGTH_MARKER, "const commentPictureCount = commentPictures?.length || 0;", "if (isCommentFrame && key === \"pictures\") continue;", "const currentLength = current.length;", "const commentCount = child.length;", "const subCommentCount = child.length")
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
        if (COMMENT_TREE_MARKER not in source or "Xiaohongshu flat comment stack frames v2;" not in source or "const commentFrameTag = {};" not in source or "new WeakSet()" in source or "visited.has(current)" in source or "const visited = new WeakSet()" in source):
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
    source = optimize_v4_function_entry_scan(source)
    source = optimize_videofeed_hotpath_references(source)

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

    # H.265 single-pass selection is applied by optimize_videofeed_hotpath_references.

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
        "const byFileId = new Map()", "const stack = [data]", "Xiaohongshu flat comment stack frames v2;", "const commentFrameTag = {}", "stack.push(comment, commentFrameTag, true)", "stack.push(subComment, commentFrameTag, false)",
        COMMENT_TREE_MARKER, "let selectedStreamUrl = \"\";",
        "// loon-change: Xiaohongshu comment video-info cache single lookup v1",
        "let picObj = videoInfoCache.get(rawVideoInfo);",
      COMMENT_ARRAY_LENGTH_MARKER,
      "const commentPictureCount = commentPictures?.length || 0;",
      "const currentLength = current.length;",
      "const commentCount = child.length;",
      "const subCommentCount = child.length",
    )
    for token in invariants:
        if token not in result:
            raise ValueError("missing optimization invariant: " + token)
    if "imageEnhance(JSON.stringify(images_list))" in result:
        raise ValueError("image-feed JSON round trip remains")
    if ".filter(v => !!v.master_url && !!v.height).sort(" in result:
        raise ValueError("video filter/sort allocation remains")
    if "new WeakSet()" in result or "const visited = new WeakSet()" in result or "visited.has(current)" in result:
        raise ValueError("comment traversal visited WeakSet overhead remains")
    if "stack.push([commentFrameTag" in result or "Array.isArray(entry) && entry[0] === commentFrameTag" in result:
        raise ValueError("comment traversal tuple-frame allocation remains")
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
