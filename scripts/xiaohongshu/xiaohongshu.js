// loon-change: Xiaohongshu response hot-path optimization v1; upstream fmz200/wool_scripts@f6bcc087e4da7ebef3c596be4a3c0fa406661564
/**
 * @author fmz200
 * @function 小红书去广告、净化、解除下载限制、画质增强等
 * @date 2026-06-05 16:00:00
 */

const $ = new Env('小红书');
const url = $request.url;
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
let rsp_body = $response.body;
if (!rsp_body) {
  $done({});
}
let obj = JSON.parse(rsp_body);

if (url.includes("/search/banner_list")) {
  obj.data = {};
} 

if (url.includes("/search/hot_list")) {
  // 热搜列表
  obj.data.items = [];
}

if (url.includes("/search/hint")) {
  // 搜索栏填充词
  obj.data.hint_words = [];
}

if (url.includes("/search/trending?")) {
  // 搜索栏
  obj.data.queries = [];
  obj.data.hint_word = {};
}

if (url.includes("/search/notes?")) {
  // 搜索结果
  if (obj.data.items?.length > 0) {
    compactInPlace(obj.data.items, item => item?.model_type === "note");
  }
}

if (url.includes("/system_service/config?")) {
  // 整体配置
  const item = ["app_theme", "loading_img", "splash", "store"];
  if (obj.data) {
    for (let i of item) {
      delete obj.data[i];
    }
  }
}

if (url.includes("/system_service/splash_config")) {
  // 开屏广告
  // loon-change: Xiaohongshu feed nested-loop property cache v1;
  const adsGroups = obj?.data?.ads_groups;
  const adsGroupLength = adsGroups?.length || 0;
  for (let groupIndex = 0; groupIndex < adsGroupLength; groupIndex++) {
    const group = adsGroups[groupIndex];
    group.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
    group.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
    const ads = group?.ads;
    const adsLength = ads?.length || 0;
    for (let adIndex = 0; adIndex < adsLength; adIndex++) {
      const ad = ads[adIndex];
      ad.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
      ad.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
    }
  }
}

if (url.includes("/note/imagefeed?") || url.includes("/note/feed?")) {
  // 信息流 图片
  // loon-change: Xiaohongshu feed nested-loop property cache v1;
  const feedData = obj?.data;
  const feedDataLength = feedData?.length || 0;
  const firstFeedPage = feedData?.[0];
  const noteList = firstFeedPage?.note_list;
  const noteListLength = noteList?.length || 0;
  if (feedDataLength > 0 && noteListLength > 0) {
    for (let noteIndex = 0; noteIndex < noteListLength; noteIndex++) {
      const item = noteList[noteIndex];
      const mediaSaveConfig = item?.media_save_config;
      if (mediaSaveConfig) {
        mediaSaveConfig.disable_save = false;
        mediaSaveConfig.disable_watermark = true;
        mediaSaveConfig.disable_weibo_cover = true;
      }
      const functionEntries = item?.share_info?.function_entries;
      const functionEntriesLength = functionEntries?.length || 0;
      if (functionEntriesLength > 0) {
        const firstFunctionEntry = functionEntries[0];
        if (firstFunctionEntry?.type !== "video_download") functionEntries.unshift({type: "video_download"});
      }
      const functionSwitch = item?.function_switch;
      if (Array.isArray(functionSwitch)) {
        const functionSwitchLength = functionSwitch.length;
        for (let switchIndex = 0; switchIndex < functionSwitchLength; switchIndex++) {
          const switchItem = functionSwitch[switchIndex];
          if (switchItem?.type === "image_download") switchItem.enable = true;
        }
      }
      const options = item?.note_text_press_options;
      if (Array.isArray(options)) {
        const optionsLength = options.length;
        let hasCopy = false;
        for (let optionIndex = 0; optionIndex < optionsLength; optionIndex++) {
          if (options[optionIndex]?.key === "copy") { hasCopy = true; break; }
        }
        if (!hasCopy) options.push({key: "copy", extra: ""});
      }
      const hashTag = item?.hash_tag;
      if (hashTag) compactInPlace(hashTag, tag => tag?.type !== "interact_vote");
    }
    const firstNote = noteList[0];
    const images_list = firstNote?.images_list;
    const livePhotoCache = [];
    firstNote.images_list = imageEnhance(images_list, livePhotoCache);
    $.setdata(JSON.stringify(livePhotoCache), "fmz200.xiaohongshu.feed.rsp");
  }
} 

if (url.includes("/note/live_photo/save")) {
  const rsp = $.getdata("fmz200.xiaohongshu.feed.rsp");
  if (rsp == null || rsp.length === 0) {
    $done({body: rsp_body});
  }
  const cache_body = JSON.parse(rsp);
  const new_data = [];
  for (const images of cache_body) {
    // Accept compact cache records and legacy full-image cache records.
    const fileId = images.file_id || images.live_photo_file_id;
    const videoId = images.video_id || images.live_photo?.media?.video_id;
    const videoUrl = images.url || images.live_photo?.media?.stream?.h265?.[0]?.master_url;
    if (fileId && videoId && videoUrl) {
      new_data.push({file_id: fileId, video_id: videoId, url: videoUrl});
    }
  }

  if (obj.data.datas) {
    replaceUrlContent(obj.data.datas, new_data);
  } else {
    obj = {"code": 0, "success": true, "msg": "fmz200创建响应体成功", "data": {"datas": new_data}};
  }
} 

if (url.includes("/note/widgets")) {
  const item = ["cooperate_binds", "generic", "note_next_step", "widget_list"];
  if (obj?.data) {
    for (let i of item) {
      delete obj.data[i];
    }
  }
} 

if (url.includes("/v3/note/videofeed?")) {
  // 信息流 视频
  // loon-change: Xiaohongshu feed nested-loop property cache v1;
  const videoFeed = obj?.data;
  const videoFeedLength = videoFeed?.length || 0;
  for (let videoIndex = 0; videoIndex < videoFeedLength; videoIndex++) {
    const item = videoFeed[videoIndex];
    // loon-change: Xiaohongshu v3 video-feed item reference cache v1;
    const mediaSaveConfig = item?.media_save_config;
    if (mediaSaveConfig) {
      mediaSaveConfig.disable_save = false;
      mediaSaveConfig.disable_watermark = true;
      mediaSaveConfig.disable_weibo_cover = true;
    }
    const functionEntries = item?.share_info?.function_entries;
    const functionEntriesLength = functionEntries?.length || 0;
    if (functionEntriesLength > 0) {
      const firstFunctionEntry = functionEntries[0];
      if (firstFunctionEntry?.type !== "video_download") {
        functionEntries.unshift({type: "video_download"});
      }
    }
  }
}

// 信息流 视频
if (url.includes("/v4/note/videofeed")) {
  // loon-change: Xiaohongshu v4 feed array length snapshot v1;
  const videoData = [];
  const videoDataSource = obj.data;
  const videoDataLength = videoDataSource?.length || 0;
  if (videoDataLength > 0) {
    for (let videoIndex = 0; videoIndex < videoDataLength; videoIndex++) {
      const item = videoDataSource[videoIndex];
      // 强制开启权限
      // loon-change: Xiaohongshu v4 video-feed nested reference cache v1;
      const mediaSaveConfig = item?.media_save_config;
      if (mediaSaveConfig) {
        mediaSaveConfig.disable_save = false;
        mediaSaveConfig.disable_watermark = true;
        mediaSaveConfig.disable_weibo_cover = true;
      }

      // 处理 function_switch (修复按钮置灰)
      // loon-change: Xiaohongshu v4 function-switch indexed scan v1;
      const functionSwitch = item?.function_switch;
      const functionSwitchLength = functionSwitch?.length || 0;
      if (functionSwitchLength > 0) {
        for (let switchIndex = 0; switchIndex < functionSwitchLength; switchIndex++) {
          const switchItem = functionSwitch[switchIndex];
          if (switchItem.type === "video_download") {
            switchItem.enable = true;
            if (switchItem.reason) delete switchItem.reason;
          }
        }
      }

      // 添加下载按钮（如果未存在）
// loon-change: Xiaohongshu v4 video-feed function-entry scan without callback v1;
      const functionEntries = item?.share_info?.function_entries;
      if (functionEntries?.length > 0) {
        let hasDownload = false;
        for (const entry of functionEntries) {
          if (entry.type === "video_download") {
            hasDownload = true;
            break;
          }
        }
        if (!hasDownload) {
          functionEntries.push({type: "video_download"});
        }
      }

      // 提取最佳视频流 (修复逻辑：分辨率相同优先选码率高的)
      const videoInfo = item?.video_info_v2;
      const videoMedia = videoInfo?.media;
      const videoStream = videoMedia?.stream;
      const h265List = videoStream?.h265 || [];
      const h264List = videoStream?.h264 || [];

      const selectedStream = selectBestStream(h265List, h264List);
      // 存入缓存数组
      const itemId = item?.id;
      const selectedMasterUrl = selectedStream?.master_url;
      if (itemId && selectedMasterUrl) {
        videoData.push({
          id: itemId,
          url: selectedMasterUrl
        });
      }
    }
    // 写入本地持久化缓存
    $.setdata(JSON.stringify(videoData), "redBookVideoFeed");
  }
}

// 视频保存请求
if (url.includes("/v10/note/video/save")) {
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
}

if (url.includes("/user/followings/followfeed")) {
  // 关注页信息流 可能感兴趣的人
  if (obj?.data?.items?.length > 0) {
    // 白名单
    compactInPlace(obj.data.items, item => item?.recommend_reason === "friend_post");
  }
} 

if (url.includes("/v4/followfeed")) {
  // 关注列表
  if (obj?.data?.items?.length > 0) {
    // recommend_user 可能感兴趣的人
    compactInPlace(obj.data.items, item => item?.recommend_reason !== "recommend_user");
  }
}  

if (url.includes("/recommend/user/follow_recommend")) {
  // 用户详情页 你可能感兴趣的人
  if (obj?.data?.title === "你可能感兴趣的人" && obj?.data?.rec_users?.length > 0) {
    obj.data = {};
  }
} 

if (url.includes("/v6/homefeed")) {
  if (obj?.data?.length > 0) {
    // 信息流广告
    compactInPlace(obj.data, item => {
      if (!item) return true;
      if (item.model_type === "live_v2" ||
          Object.prototype.hasOwnProperty.call(item, "ads_info") ||
          Object.prototype.hasOwnProperty.call(item, "card_icon") ||
          item.note_attributes?.includes("goods")) return false;
      if (item.related_ques) delete item.related_ques;
      return true;
    });
  }
}

// 加载评论区
if (url.includes("/api/sns/v5/note/comment/list?") || url.includes("/api/sns/v3/note/comment/sub_comments?")) {
  const livePhotos = [];
  const commentVideos = [];
  const note_id = obj.data?.comments?.[0]?.note_id || "";
  processCommentTree(obj.data, livePhotos, commentVideos, note_id);
  if (livePhotos.length > 0) {
    let commitsRsp;
    const commitsCache = $.getdata("fmz200.xiaohongshu.comments.rsp");
    if (!commitsCache) commitsRsp = {noteId: note_id, livePhotos};
    else {
      commitsRsp = JSON.parse(commitsCache);
      if (commitsRsp.noteId === note_id) commitsRsp.livePhotos = appendUniqueLivePhotos(commitsRsp.livePhotos, livePhotos);
      else commitsRsp = {noteId: note_id, livePhotos};
    }
    $.setdata(JSON.stringify(commitsRsp), "fmz200.xiaohongshu.comments.rsp");
  }
  if (commentVideos.length > 0) {
    let videosCache;
    const commitsCache = $.getdata("fmz200.xiaohongshu.comments.videos.rsp");
    if (!commitsCache) videosCache = {noteId: note_id, videos: commentVideos};
    else {
      videosCache = JSON.parse(commitsCache);
      if (videosCache.noteId === note_id) videosCache.videos = appendUniqueLivePhotos(videosCache.videos, commentVideos);
      else videosCache = {noteId: note_id, videos: commentVideos};
    }
    $.setdata(JSON.stringify(videosCache), "fmz200.xiaohongshu.comments.videos.rsp");
  }
}

// 下载评论区live图/评论区视频
if (url.includes("/api/sns/v1/interaction/comment/video/download?")) {
  const commitsCache = $.getdata("fmz200.xiaohongshu.comments.rsp");
  const commitsVideoCache = $.getdata("fmz200.xiaohongshu.comments.videos.rsp");
  if (commitsCache) {
    let commitsRsp = JSON.parse(commitsCache);
    if (commitsRsp.livePhotos.length > 0 && obj.data?.video) {
      for (const item of commitsRsp.livePhotos) {
        if (item.videId === obj.data.video.video_id) {
          obj.data.video.video_url = item.videoUrl;
          break;
        }
      }
    }
  } else if (commitsVideoCache){
    let commitsVideoRsp = JSON.parse(commitsVideoCache);
    if (commitsVideoRsp.videos.length > 0 && obj.data?.video) {
      for (const item of commitsVideoRsp.videos) {
        if (item.videId === obj.data.video.video_id) {
          obj.data.video.video_url = item.videoUrl;
          break;
        }
      }
    }
  } else {
  }
}

$done({body: JSON.stringify(obj)});

// 小红书画质增强：加载2K分辨率的图片
// loon-change: Xiaohongshu imagefeed single traversal live-photo extraction v1
function imageEnhance(images, livePhotoCache) {
  // loon-change: Xiaohongshu image traversal array-frame length cache v1;
  if (!images || typeof images !== "object") return [];
  const livePhotoTarget = Array.isArray(livePhotoCache) ? livePhotoCache : null;
  const quality=$.getdata("fmz200.xiaohongshu.imageQuality");
  const originalPattern=/\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern=/imageView2\/2\/w\/\d+\/format/g, heightPattern=/imageView2\/2\/h\/\d+\/format/g;
  let originalDone=false;
  const stack=[{value:images,index:0,keys:null,length:Array.isArray(images)?images.length:0,root:true}];
  while(stack.length) {
    const frame=stack[stack.length-1], value=frame.value;
    if(Array.isArray(value)) {
      if(frame.index>=frame.length){stack.pop();continue;}
      const key=frame.index++, child=value[key];
      if(frame.root && livePhotoTarget && child && typeof child === "object") {
        // loon-change: Xiaohongshu imagefeed live-photo property cache v1;
        const livePhoto = child.live_photo;
        const media = livePhoto?.media;
        const stream = media?.stream?.h265?.[0];
        const fileId = child.live_photo_file_id;
        const videoId = media?.video_id;
        const masterUrl = stream?.master_url;
        if (fileId && videoId && masterUrl) {
          livePhotoTarget.push({
            live_photo_file_id: fileId,
            video_id: videoId,
            url: masterUrl
          });
        }
      }
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null,length:Array.isArray(child)?child.length:0,root:false});
    } else {
      if(frame.keys===null) frame.keys=Object.keys(value);
      if(frame.index>=frame.keys.length){stack.pop();continue;}
      const key=frame.keys[frame.index++], child=value[key];
      if(typeof child==="string" && child.includes("imageView2/2")) {
        if(quality==="original") {
          if(!originalDone){const changed=child.replace(originalPattern,"?imageView2/0/format/png&redImage/frame/0");if(changed!==child){value[key]=changed;originalDone=true;}}
        } else value[key]=child.replace(widthPattern,"imageView2/2/w/2160/format").replace(heightPattern,"imageView2/2/h/2160/format");
      } else if(child && typeof child==="object") stack.push({value:child,index:0,keys:null,length:Array.isArray(child)?child.length:0,root:false});
    }
  }
  return images;
}


function replaceUrlContent(collectionA, collectionB) {
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
}


function deduplicateLivePhotos(items) {
  const seen=new Set();let write=0;
  for(let read=0;read<items.length;read++){const item=items[read];if(seen.has(item.videId))continue;seen.add(item.videId);if(write!==read)items[write]=item;write++;}
  items.length=write;return items;
}


function processCommentTree(data, livePhotos, commentVideos, noteId) {
  // loon-change: Xiaohongshu comment classification stack frames v1;
  const commentFrameTag = {};
  const parsedVideoInfo = new Map();
  const parseVideoInfo = raw => {
    if (typeof raw !== "string" || raw.length === 0) return null;
    // loon-change: Xiaohongshu comment video-info cache single lookup v2;
    let parsed = parsedVideoInfo.get(raw);
    if (parsed === undefined) {
      try { parsed = JSON.parse(raw); }
      catch (_) { parsed = null; }
      parsedVideoInfo.set(raw, parsed);
    }
    return parsed;
  };
  // loon-change: Xiaohongshu parsed JSON comment tree without visited WeakSet v1;
  // JSON.parse creates a tree with no cycles or shared object references.
  // Comment classification travels with only comment stack entries; other nodes
  // remain plain references and require no WeakSet membership structure.
  // loon-change: Xiaohongshu comment frame stack flat encoding v1;
  const stack = [data];
  while (stack.length) {
    const entry = stack.pop();
    const isCommentFrame = entry === commentFrameTag;
    const current = isCommentFrame ? stack.pop() : entry;
    const isTopLevelComment = isCommentFrame && stack.pop() === true;
    if (!current || typeof current !== "object") continue;
    // loon-change: Xiaohongshu comment node array classification cache v1;
    const currentIsArray = Array.isArray(current);
    if (!currentIsArray) {
      if ("red_id" in current) { current.fmz200 = current.red_id; delete current.red_id; }
      if (isCommentFrame) {
        fixCommentType(current);
        // loon-change: Xiaohongshu comment media collection property cache v1;
        const pictures = current.pictures;
        if (Array.isArray(pictures)) {
          for (const picture of pictures) {
            const pictureVideoId = picture?.video_id;
            if (!pictureVideoId) continue;
            const pictureVideoInfo = picture.video_info;
            const info = parseVideoInfo(pictureVideoInfo);
            const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);
            if (stream?.master_url) livePhotos.push({videId: pictureVideoId, videoUrl: stream.master_url});
          }
        }
        if (isTopLevelComment) {
          const videos = current.videos;
          if (Array.isArray(videos)) {
            for (const video of videos) {
              const videoId = video?.video_id;
              const videoInfo = video?.video_info;
              if (!videoId || !videoInfo) continue;
              const info = parseVideoInfo(videoInfo);
              const stream = selectBestStream(info?.stream?.h265, info?.stream?.h264);
              if (stream?.master_url) commentVideos.push({
                videId: videoId, videoUrl: stream.master_url, commentId: current.id, noteId,
                width: stream.width, height: stream.height, bitrate: stream.video_bitrate, hdr: stream.hdr_type === 1
              });
            }
          }
        }
      }
    }
    if (currentIsArray) {
      // loon-change: Xiaohongshu comment traversal array length cache v1;
      const currentLength = current.length;
      for (let i = currentLength - 1; i >= 0; i--) {
        const child = current[i];
        if (child && typeof child === "object") stack.push(child);
      }
    } else {
      for (const key in current) {
        if (!Object.prototype.hasOwnProperty.call(current, key)) continue;
        const child = current[key];
        if (!child || typeof child !== "object") continue;
        if (current === data && key === "comments" && Array.isArray(child)) {
          const commentsLength = child.length;
          for (let i = commentsLength - 1; i >= 0; i--) {
            const comment = child[i];
            if (comment && typeof comment === "object") stack.push(true, comment, commentFrameTag);
          }
        } else if (isCommentFrame && isTopLevelComment && key === "sub_comments" && Array.isArray(child)) {
          const subCommentsLength = child.length;
          for (let i = subCommentsLength - 1; i >= 0; i--) {
            const subComment = child[i];
            if (subComment && typeof subComment === "object") stack.push(false, subComment, commentFrameTag);
          }
        } else stack.push(child);
      }
    }
  }
}


/**
 * 从流列表中选择最佳流（优先 H265，降级 H264）
 * @param {Array} h265List - H265 流列表
 * @param {Array} h264List - H264 流列表
 * @returns {Object|null} - 选中的流对象或 null
 */
function selectBestStream(h265List,h264List) {
  // loon-change: Xiaohongshu best-stream selection without per-call closure v1;
  for (let pass = 0; pass < 2; pass++) {
    const list = pass === 0 ? h265List : h264List;
    if (!Array.isArray(list) || !list.length) continue;
    let best = null, pixelsBest = 0, rateBest = 0;
    for (const item of list) {
      if (!item || !item.master_url) continue;
      const pixels = (item.width || 0) * (item.height || 0);
      const rate = Number(item.avg_bitrate) || 0;
      if (best === null || pixels > pixelsBest || (pixels === pixelsBest && rate > rateBest)) {
        best = item;
        pixelsBest = pixels;
        rateBest = rate;
      }
    }
    if (best) return best;
  }
  return null;
}


/**
 * 修复评论类型（3->2, 1->0）
 * @param {Object} comment - 评论对象
 */
function fixCommentType(comment) {
  if (comment.comment_type === 3) {
    comment.comment_type = 2;
  }
  if (comment.media_source_type === 1) {
    comment.media_source_type = 0;
  }
}

/**
 * 从图片列表中提取live照片
 * @param {Array} pictures - 图片列表
 * @param {Array} livePhotos - live照片数组（会被修改）
 * @param {string} commentId - 评论ID（用于日志）
 * @param {string} prefix - 日志前缀
 */
function extractLivePhotos(pictures, livePhotos, commentId, prefix = "") {
  if (!pictures?.length > 0) return;
  for (const picture of pictures) {
    if (picture.video_id) {
      const picObj = JSON.parse(picture.video_info);
      const bestStream = selectBestStream(picObj.stream?.h265, picObj.stream?.h264);
      if (bestStream?.master_url) {
        livePhotos.push({
          videId: picture.video_id,
          videoUrl: bestStream.master_url
        });
      }
    }
  }
}

function Env(t, e) { class s { constructor(t) { this.env = t } send(t, e = "GET") { t = "string" == typeof t ? { url: t } : t; let s = this.get; return "POST" === e && (s = this.post), new Promise((e, i) => { s.call(this, t, (t, s, r) => { t ? i(t) : e(s) }) }) } get(t) { return this.send.call(this.env, t) } post(t) { return this.send.call(this.env, t, "POST") } } return new class { constructor(t, e) { this.name = t, this.http = new s(this), this.data = null, this.dataFile = "box.dat", this.logs = [], this.isMute = !1, this.isNeedRewrite = !1, this.logSeparator = "\n", this.encoding = "utf-8", this.startTime = (new Date).getTime(), Object.assign(this, e), this.log("", `\ud83d\udd14${this.name}, \u5f00\u59cb!`) } isNode() { return "undefined" != typeof module && !!module.exports } isQuanX() { return "undefined" != typeof $task } isSurge() { return "undefined" != typeof $httpClient && "undefined" == typeof $loon } isLoon() { return "undefined" != typeof $loon } isShadowrocket() { return "undefined" != typeof $rocket } isStash() { return "undefined" != typeof $environment && $environment["stash-version"] } toObj(t, e = null) { try { return JSON.parse(t) } catch { return e } } toStr(t, e = null) { try { return JSON.stringify(t) } catch { return e } } getjson(t, e) { let s = e; const i = this.getdata(t); if (i) try { s = JSON.parse(this.getdata(t)) } catch { } return s } setjson(t, e) { try { return this.setdata(JSON.stringify(t), e) } catch { return !1 } } getScript(t) { return new Promise(e => { this.get({ url: t }, (t, s, i) => e(i)) }) } runScript(t, e) { return new Promise(s => { let i = this.getdata("@chavy_boxjs_userCfgs.httpapi"); i = i ? i.replace(/\n/g, "").trim() : i; let r = this.getdata("@chavy_boxjs_userCfgs.httpapi_timeout"); r = r ? 1 * r : 20, r = e && e.timeout ? e.timeout : r; const [o, a] = i.split("@"), n = { url: `http://${a}/v1/scripting/evaluate`, body: { script_text: t, mock_type: "cron", timeout: r }, headers: { "X-Key": o, Accept: "*/*" } }; this.post(n, (t, e, i) => s(i)) }).catch(t => this.logErr(t)) } loaddata() { if (!this.isNode()) return {}; { this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path"); const t = this.path.resolve(this.dataFile), e = this.path.resolve(process.cwd(), this.dataFile), s = this.fs.existsSync(t), i = !s && this.fs.existsSync(e); if (!s && !i) return {}; { const i = s ? t : e; try { return JSON.parse(this.fs.readFileSync(i)) } catch (t) { return {} } } } } writedata() { if (this.isNode()) { this.fs = this.fs ? this.fs : require("fs"), this.path = this.path ? this.path : require("path"); const t = this.path.resolve(this.dataFile), e = this.path.resolve(process.cwd(), this.dataFile), s = this.fs.existsSync(t), i = !s && this.fs.existsSync(e), r = JSON.stringify(this.data); s ? this.fs.writeFileSync(t, r) : i ? this.fs.writeFileSync(e, r) : this.fs.writeFileSync(t, r) } } lodash_get(t, e, s) { const i = e.replace(/\[(\d+)\]/g, ".$1").split("."); let r = t; for (const t of i) if (r = Object(r)[t], void 0 === r) return s; return r } lodash_set(t, e, s) { return Object(t) !== t ? t : (Array.isArray(e) || (e = e.toString().match(/[^.[\]]+/g) || []), e.slice(0, -1).reduce((t, s, i) => Object(t[s]) === t[s] ? t[s] : t[s] = Math.abs(e[i + 1]) >> 0 == +e[i + 1] ? [] : {}, t)[e[e.length - 1]] = s, t) } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.lodash_get(t, i, "") : e } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), a = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(a); this.lodash_set(e, r, t), s = this.setval(JSON.stringify(e), i) } catch (e) { const o = {}; this.lodash_set(o, r, t), s = this.setval(JSON.stringify(o), i) } } else s = this.setval(t, e); return s } getval(t) { return this.isSurge() || this.isLoon() ? $persistentStore.read(t) : this.isQuanX() ? $prefs.valueForKey(t) : this.isNode() ? (this.data = this.loaddata(), this.data[t]) : this.data && this.data[t] || null } setval(t, e) { return this.isSurge() || this.isLoon() ? $persistentStore.write(t, e) : this.isQuanX() ? $prefs.setValueForKey(t, e) : this.isNode() ? (this.data = this.loaddata(), this.data[e] = t, this.writedata(), !0) : this.data && this.data[e] || null } initGotEnv(t) { this.got = this.got ? this.got : require("got"), this.cktough = this.cktough ? this.cktough : require("tough-cookie"), this.ckjar = this.ckjar ? this.ckjar : new this.cktough.CookieJar, t && (t.headers = t.headers ? t.headers : {}, void 0 === t.headers.Cookie && void 0 === t.cookieJar && (t.cookieJar = this.ckjar)) } get(t, e = (() => { })) { if (t.headers && (delete t.headers["Content-Type"], delete t.headers["Content-Length"]), this.isSurge() || this.isLoon()) this.isSurge() && this.isNeedRewrite && (t.headers = t.headers || {}, Object.assign(t.headers, { "X-Surge-Skip-Scripting": !1 })), $httpClient.get(t, (t, s, i) => { !t && s && (s.body = i, s.statusCode = s.status ? s.status : s.statusCode, s.status = s.statusCode), e(t, s, i) }); else if (this.isQuanX()) this.isNeedRewrite && (t.opts = t.opts || {}, Object.assign(t.opts, { hints: !1 })), $task.fetch(t).then(t => { const { statusCode: s, statusCode: i, headers: r, body: o } = t; e(null, { status: s, statusCode: i, headers: r, body: o }, o) }, t => e(t && t.error || "UndefinedError")); else if (this.isNode()) { let s = require("iconv-lite"); this.initGotEnv(t), this.got(t).on("redirect", (t, e) => { try { if (t.headers["set-cookie"]) { const s = t.headers["set-cookie"].map(this.cktough.Cookie.parse).toString(); s && this.ckjar.setCookieSync(s, null), e.cookieJar = this.ckjar } } catch (t) { this.logErr(t) } }).then(t => { const { statusCode: i, statusCode: r, headers: o, rawBody: a } = t, n = s.decode(a, this.encoding); e(null, { status: i, statusCode: r, headers: o, rawBody: a, body: n }, n) }, t => { const { message: i, response: r } = t; e(i, r, r && s.decode(r.rawBody, this.encoding)) }) } } post(t, e = (() => { })) { const s = t.method ? t.method.toLocaleLowerCase() : "post"; if (t.body && t.headers && !t.headers["Content-Type"] && (t.headers["Content-Type"] = "application/x-www-form-urlencoded"), t.headers && delete t.headers["Content-Length"], this.isSurge() || this.isLoon()) this.isSurge() && this.isNeedRewrite && (t.headers = t.headers || {}, Object.assign(t.headers, { "X-Surge-Skip-Scripting": !1 })), $httpClient[s](t, (t, s, i) => { !t && s && (s.body = i, s.statusCode = s.status ? s.status : s.statusCode, s.status = s.statusCode), e(t, s, i) }); else if (this.isQuanX()) t.method = s, this.isNeedRewrite && (t.opts = t.opts || {}, Object.assign(t.opts, { hints: !1 })), $task.fetch(t).then(t => { const { statusCode: s, statusCode: i, headers: r, body: o } = t; e(null, { status: s, statusCode: i, headers: r, body: o }, o) }, t => e(t && t.error || "UndefinedError")); else if (this.isNode()) { let i = require("iconv-lite"); this.initGotEnv(t); const { url: r, ...o } = t; this.got[s](r, o).then(t => { const { statusCode: s, statusCode: r, headers: o, rawBody: a } = t, n = i.decode(a, this.encoding); e(null, { status: s, statusCode: r, headers: o, rawBody: a, body: n }, n) }, t => { const { message: s, response: r } = t; e(s, r, r && i.decode(r.rawBody, this.encoding)) }) } } time(t, e = null) { const s = e ? new Date(e) : new Date; let i = { "M+": s.getMonth() + 1, "d+": s.getDate(), "H+": s.getHours(), "m+": s.getMinutes(), "s+": s.getSeconds(), "q+": Math.floor((s.getMonth() + 3) / 3), S: s.getMilliseconds() }; /(y+)/.test(t) && (t = t.replace(RegExp.$1, (s.getFullYear() + "").substr(4 - RegExp.$1.length))); for (let e in i) new RegExp("(" + e + ")").test(t) && (t = t.replace(RegExp.$1, 1 == RegExp.$1.length ? i[e] : ("00" + i[e]).substr(("" + i[e]).length))); return t } msg(e = t, s = "", i = "", r) { const o = t => { if (!t) return t; if ("string" == typeof t) return this.isLoon() ? t : this.isQuanX() ? { "open-url": t } : this.isSurge() ? { url: t } : void 0; if ("object" == typeof t) { if (this.isLoon()) { let e = t.openUrl || t.url || t["open-url"], s = t.mediaUrl || t["media-url"]; return { openUrl: e, mediaUrl: s } } if (this.isQuanX()) { let e = t["open-url"] || t.url || t.openUrl, s = t["media-url"] || t.mediaUrl, i = t["update-pasteboard"] || t.updatePasteboard; return { "open-url": e, "media-url": s, "update-pasteboard": i } } if (this.isSurge()) { let e = t.url || t.openUrl || t["open-url"]; return { url: e } } } }; if (this.isMute || (this.isSurge() || this.isLoon() ? $notification.post(e, s, i, o(r)) : this.isQuanX() && $notify(e, s, i, o(r))), !this.isMuteLog) { let t = ["", "==============\ud83d\udce3\u7cfb\u7edf\u901a\u77e5\ud83d\udce3=============="]; t.push(e), s && t.push(s), i && t.push(i), console.log(t.join("\n")), this.logs = this.logs.concat(t) } } log(...t) { t.length > 0 && (this.logs = [...this.logs, ...t]), console.log(t.join(this.logSeparator)) } logErr(t, e) { const s = !this.isSurge() && !this.isQuanX() && !this.isLoon(); s ? this.log("", `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t.stack) : this.log("", `\u2757\ufe0f${this.name}, \u9519\u8bef!`, t) } wait(t) { return new Promise(e => setTimeout(e, t)) } done(t = {}) { const e = (new Date).getTime(), s = (e - this.startTime) / 1e3; this.log("", `\ud83d\udd14${this.name}, \u7ed3\u675f! \ud83d\udd5b ${s} \u79d2`), this.log(), this.isSurge() || this.isQuanX() || this.isLoon() ? $done(t) : this.isNode() && process.exit(1) } }(t, e) }
