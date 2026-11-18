/**
 * @author fmz200
 * @function 小红书去广告、净化、解除下载限制、画质增强等
 * @date 2026-06-05 16:00:00
 */

const $ = new Env('小红书');
const url = $request.url;
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
    obj.data.items = obj.data.items.filter((i) => i.model_type === "note");
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
  if (obj?.data?.ads_groups?.length > 0) {
    for (let i of obj.data.ads_groups) {
      i.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
      i.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      if (i?.ads?.length > 0) {
        for (let ii of i.ads) {
          ii.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
          ii.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
        }
      }
    }
  }
}

if (url.includes("/note/imagefeed?") || url.includes("/note/feed?")) {
  // 信息流 图片
  if (obj?.data?.length > 0) {
    if (obj.data[0]?.note_list?.length > 0) {
      for (let item of obj.data[0].note_list) {
        if (item?.media_save_config) {
          // 水印开关
          item.media_save_config.disable_save = false;
          item.media_save_config.disable_watermark = true;
          item.media_save_config.disable_weibo_cover = true;
        }
        if (item?.share_info?.function_entries?.length > 0) {
          // 下载限制
          const addItem = {type: "video_download"};
          let func = item.share_info.function_entries[0];
          if (func?.type !== "video_download") {
            // 向数组开头添加对象
            item.share_info.function_entries.unshift(addItem);
          }
        }
        // 新版下载限制
        if (Array.isArray(item.function_switch)) {
          item.function_switch.forEach(item => {
            if (item?.type === 'image_download') {
              item.enable = true;
            }
          });
        }
        // 复制权限
        const options = item.note_text_press_options;
        if (Array.isArray(options)) {
          const hasCopy = options.some(item => item.key === 'copy');
          if (!hasCopy) {
            options.push({
              key: 'copy',
              extra: ''
            });
          }
        }

        // 处理帖子引用的标签
        if (item.hash_tag) {
          item.hash_tag = item.hash_tag.filter(tag => tag.type !== "interact_vote");
        }
      }

      const images_list = obj.data[0].note_list[0].images_list;
      // The later live-photo save handler only needs these three values.
      // Cache a compact projection instead of serializing every image field.
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
      // 画质增强
      obj.data[0].note_list[0].images_list = imageEnhance(images_list);
      $.setdata(JSON.stringify(livePhotoCache), "fmz200.xiaohongshu.feed.rsp");
    }
  }
} 

if (url.includes("/note/live_photo/save")) {
  const rsp = $.getdata("fmz200.xiaohongshu.feed.rsp");
  // console.log("读取缓存val：" + rsp);
  if (rsp == null || rsp.length === 0) {
    console.log('缓存无内容，返回原body');
    $done({body: rsp_body});
  }
  const cache_body = JSON.parse(rsp);
  let new_data = [];
  for (const images of cache_body) {
    if (images.live_photo_file_id) {
      new_data.push({
        file_id: images.live_photo_file_id,
        video_id: images.video_id,
        url: images.url
      });
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
  if (obj?.data?.length > 0) {
    for (let item of obj.data) {
      if (item?.media_save_config) {
        // 水印
        item.media_save_config.disable_save = false;
        item.media_save_config.disable_watermark = true;
        item.media_save_config.disable_weibo_cover = true;
      }
      if (item?.share_info?.function_entries?.length > 0) {
        // 下载限制
        const addItem = {type: "video_download"};
        let func = item.share_info.function_entries[0];
        if (func?.type !== "video_download") {
          // 向数组开头添加对象
          item.share_info.function_entries.unshift(addItem);
        }
      }
    }
  }
}

// 信息流 视频
if (url.includes("/v4/note/videofeed")) {
  // Preserve the former native v4 ad filter in this single response-body pass.
  if (Array.isArray(obj.data)) {
    obj.data = obj.data.filter((item) =>
      item && typeof item === "object" &&
      item.model_type === "note" &&
      !Object.prototype.hasOwnProperty.call(item, "ad")
    );
  }
  let videoData = [];
  if (obj.data?.length > 0) {
    for (let item of obj.data) {
      // 强制开启权限
      if (item?.media_save_config) {
        item.media_save_config.disable_save = false;
        item.media_save_config.disable_watermark = true;
        item.media_save_config.disable_weibo_cover = true;
      }

      // 处理 function_switch (修复按钮置灰)
      if (item?.function_switch?.length > 0) {
        for (let switchItem of item.function_switch) {
          if (switchItem.type === "video_download") {
            switchItem.enable = true;
            if (switchItem.reason) delete switchItem.reason;
          }
        }
      }

      // 添加下载按钮（如果未存在）
      if (item?.share_info?.function_entries?.length > 0) {
        const hasDownload = item.share_info.function_entries.some(entry => entry.type === "video_download");
        if (!hasDownload) {
          item.share_info.function_entries.push({type: "video_download"});
        }
      }

      // 提取最佳视频流 (修复逻辑：分辨率相同优先选码率高的)
      const h265List = item?.video_info_v2?.media?.stream?.h265 || [];
      const h264List = item?.video_info_v2?.media?.stream?.h264 || [];

      const selectedStream = selectBestStream(h265List, h264List);
      // 存入缓存数组
      if (item?.id && selectedStream?.master_url) {
        const data = {
          id: item.id,
          url: selectedStream.master_url
        };
        videoData.push(data);
      }
    }
    // 写入本地持久化缓存
    $.setdata(JSON.stringify(videoData), "redBookVideoFeed");
  } else if (Array.isArray(obj.data)) {
    // Clear stale IDs when the filtered response contains no playable notes.
    $.setdata("[]", "redBookVideoFeed");
  }
}

// 视频保存请求
if (url.includes("/v10/note/video/save")) {
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
  }
}

if (url.includes("/user/followings/followfeed")) {
  // 关注页信息流 可能感兴趣的人
  if (obj?.data?.items?.length > 0) {
    // 白名单
    obj.data.items = obj.data.items.filter((i) => i?.recommend_reason === "friend_post");
  }
} 

if (url.includes("/v4/followfeed")) {
  // 关注列表
  if (obj?.data?.items?.length > 0) {
    // recommend_user 可能感兴趣的人
    obj.data.items = obj.data.items.filter((i) => !["recommend_user"].includes(i.recommend_reason));
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
    let newItems = [];
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
    obj.data = newItems;
  }
}

// 加载评论区
if (url.includes("/api/sns/v5/note/comment/list?") || url.includes("/api/sns/v3/note/comment/sub_comments?")) {
  replaceRedIdWithFmz200(obj.data);
  let livePhotos = [];
  let commentVideos = [];
  let note_id = "";
  if (obj.data?.comments?.length > 0) {
    note_id = obj.data.comments[0].note_id;
    for (const comment of obj.data.comments) {
      // comment_type: 0-文字，2-图片/live，3-表情包，5-视频
      fixCommentType(comment);
      extractLivePhotos(comment.pictures, livePhotos, comment.id);

      // 子评论处理
      if (comment.sub_comments?.length > 0) {
        for (const sub_comment of comment.sub_comments) {
          fixCommentType(sub_comment);
          extractLivePhotos(sub_comment.pictures, livePhotos, comment.id, "_sub");
        }
      }

      // 评论视频处理 
      if (comment?.videos?.length > 0) {
        for (const video of comment.videos) {
          if (video?.video_id && video?.video_info) {
            try {
              const videoObj = JSON.parse(video.video_info);
              // 选择最佳画质
              const streams = selectBestStream(videoObj?.stream?.h265, videoObj?.stream?.h264);
              if (streams?.master_url) {
                commentVideos.push({
                  videId: video.video_id,
                  videoUrl: streams.master_url,
                  commentId: comment.id,
                  noteId: note_id,
                  width: streams.width,
                  height: streams.height,
                  bitrate: streams.video_bitrate,
                  hdr: streams.hdr_type === 1
                });
              }
            } catch (e) {
              console.log("评论视频处理出错", e);
            }
          }
        }
      }
      
    }
  }
  // 存储评论实况照片
  if (livePhotos.length > 0) {
    let commitsRsp;
    const commitsCache = $.getdata("fmz200.xiaohongshu.comments.rsp");
    if (!commitsCache) {
      commitsRsp = {noteId: note_id, livePhotos: livePhotos};
    } else {
      commitsRsp = JSON.parse(commitsCache);
      if (commitsRsp.noteId === note_id) {
        commitsRsp.livePhotos = deduplicateLivePhotos(commitsRsp.livePhotos.concat(livePhotos));
      } else {
        commitsRsp = {noteId: note_id, livePhotos: livePhotos};
      }
    }
    $.setdata(JSON.stringify(commitsRsp), "fmz200.xiaohongshu.comments.rsp");
  }

  // 存储评论视频信息
  if (commentVideos.length > 0) {
    let videosCache;
    const commitsCache = $.getdata("fmz200.xiaohongshu.comments.videos.rsp");
    if (!commitsCache) {
      videosCache = {noteId: note_id, videos: commentVideos};
    } else {
      videosCache = JSON.parse(commitsCache);
      if (videosCache.noteId === note_id) {
        videosCache.videos = deduplicateLivePhotos(videosCache.videos.concat(commentVideos));
      } else {
        videosCache = {noteId: note_id, videos: commentVideos};
      }
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
        // console.log("缓存video_id：" + item.videId);
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
        // console.log("缓存video_id：" + item.videId);
        if (item.videId === obj.data.video.video_id) {
          obj.data.video.video_url = item.videoUrl;
          break;
        }
      }
    }
  }
}

$done({body: JSON.stringify(obj)});

// 小红书画质增强：加载2K分辨率的图片
function imageEnhance(images) {
  if (!images || typeof images !== "object") return [];

  const imageQuality = $.getdata("fmz200.xiaohongshu.imageQuality");
  const originalPattern = /\?imageView2\/2[^&]*(?:&redImage\/frame\/0)/;
  const widthPattern = /imageView2\/2\/w\/\d+\/format/g;
  const heightPattern = /imageView2\/2\/h\/\d+\/format/g;
  let originalReplaced = false;

  function enhanceString(value) {
    // Avoid running regular expressions against titles, IDs and descriptions.
    if (!value.includes("imageView2/2")) return value;
    if (imageQuality === "original") {
      if (originalReplaced) return value;
      const enhanced = value.replace(originalPattern, "?imageView2/0/format/png&redImage/frame/0");
      if (enhanced !== value) originalReplaced = true;
      return enhanced;
    }
    return value
      .replace(widthPattern, "imageView2/2/w/2160/format")
      .replace(heightPattern, "imageView2/2/h/2160/format");
  }

  // Iterative depth-first walk preserves property/array order without recursion.
  const stack = [{ value: images, index: 0, keys: null }];
  while (stack.length > 0) {
    const frame = stack[stack.length - 1];
    const value = frame.value;
    if (Array.isArray(value)) {
      if (frame.index >= value.length) {
        stack.pop();
        continue;
      }
      const index = frame.index++;
      const child = value[index];
      if (typeof child === "string") {
        value[index] = enhanceString(child);
      } else if (child && typeof child === "object") {
        stack.push({ value: child, index: 0, keys: null });
      }
    } else {
      if (frame.keys === null) frame.keys = Object.keys(value);
      if (frame.index >= frame.keys.length) {
        stack.pop();
        continue;
      }
      const key = frame.keys[frame.index++];
      const child = value[key];
      if (typeof child === "string") {
        value[key] = enhanceString(child);
      } else if (child && typeof child === "object") {
        stack.push({ value: child, index: 0, keys: null });
      }
    }
  }
  return images;
}

function replaceUrlContent(collectionA, collectionB) {
  // Index once: repeated Array.find() made large save lists O(A × B).
  // Keep the first entry for duplicate file_id values, matching Array.find().
  const byFileId = new Map();
  for (const itemB of collectionB) {
    if (itemB && !byFileId.has(itemB.file_id)) byFileId.set(itemB.file_id, itemB);
  }

  const videoBaseRegex = /(.*\.(mp4|mov|webm|m3u8|ts|avi|mkv|flv))/i;
  for (const itemA of collectionA) {
    if (!itemA) continue;
    const itemB = byFileId.get(itemA.file_id);
    if (!itemB) continue;
    if (itemA.url !== "") {
      const match = itemB.url.match(videoBaseRegex);
      itemA.url = match ? match[1] : itemB.url;
    } else {
      itemA.url = itemB.url;
    }
    itemA.author = "@fmz200";
  }
}

function deduplicateLivePhotos(livePhotos) {
  const seen = new Map();
  livePhotos = livePhotos.filter(item => {
    if (seen.has(item.videId)) {
      return false;
    }
    seen.set(item.videId, true);
    return true;
  });
  return livePhotos;
}

function replaceRedIdWithFmz200(obj) {
  // Parsed API payloads can be deeply nested; use an explicit stack to avoid
  // recursive call overhead and call-stack limits.
  const stack = [obj];
  while (stack.length > 0) {
    const current = stack.pop();
    if (Array.isArray(current)) {
      for (let i = current.length - 1; i >= 0; i--) {
        const child = current[i];
        if (child && typeof child === "object") stack.push(child);
      }
    } else if (current && typeof current === "object") {
      if ("red_id" in current) {
        current.fmz200 = current.red_id;
        delete current.red_id;
      }
      const keys = Object.keys(current);
      for (let i = keys.length - 1; i >= 0; i--) {
        const child = current[keys[i]];
        if (child && typeof child === "object") stack.push(child);
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
function selectBestStream(h265List, h264List) {
  // A full filter + sort only needs the maximum item. Scan once instead:
  // O(n) time, O(1) auxiliary memory, with the same resolution/bitrate order.
  const selectFromList = (list) => {
    if (!Array.isArray(list) || list.length === 0) return null;
    let best = null;
    let bestResolution = 0;
    let bestBitrate = 0;
    for (const item of list) {
      if (!item || !item.master_url) continue;
      const resolution = (item.width || 0) * (item.height || 0);
      const bitrate = Number(item.avg_bitrate) || 0;
      if (
        best === null ||
        resolution > bestResolution ||
        (resolution === bestResolution && bitrate > bestBitrate)
      ) {
        best = item;
        bestResolution = resolution;
        bestBitrate = bitrate;
      }
    }
    return best;
  };

  return selectFromList(h265List) || selectFromList(h264List);
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
