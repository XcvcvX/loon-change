// loon-change: R-Store Xiaohongshu hot-path optimization v1; upstream zirawell/R-Store@1e08bab55bcffc396be39f914f48151443344493
/********************************
XiaoHongShu Remove Ads - Version 2.0
Checkout Source: 
- https://raw.githubusercontent.com/RuCu6/QuanX/main/Rewrites/Cube/xiaohongshu.snippet
- https://raw.githubusercontent.com/fmz200/wool_scripts/refs/heads/main/Scripts/xiaohongshu/xiaohongshu.js


Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/X/小红书/rewrite/xiaohongshu.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/X/小红书/xiaohongshu.sgmodule
********************************/

const $ = new Env('小红书');
const url = $request.url;
if (!$response.body) { $done({}); } else {
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
let rsp_body = $response.body;
let obj = JSON.parse(rsp_body);
// 信息流 图片
if (url.includes("/note/imagefeed") || url.includes("/note/feed")) {
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
        // 处理帖子引用的标签
        if (item.hash_tag) {
          compactInPlace(item.hash_tag, tag => tag?.type !== "interact_vote");
        }
      }

      const images_list = obj.data[0].note_list[0].images_list;
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
      imageEnhance(images_list);
    }
  }
// 实况照片保存请求
} else if (url.includes("/note/live_photo/save")) {
  let livePhoto;
  let newDatas = [];
  let rsp = $.getdata("redBookLivePhoto");
  if (rsp == null || rsp.length === 0) {
    $done({body: rsp_body});
  }
  livePhoto = JSON.parse(rsp);
  for (const item of livePhoto) {
    if (item?.file_id) {
      newDatas.push({
        file_id: item.file_id,
        video_id: item.video_id,
        url: item.url
      });
    }
  }
  if (obj?.data?.datas?.length > 0) {
    replaceUrlContent(obj.data.datas, newDatas);
  } else {
    // 原始数据有问题 强制返回成功响应
    obj = {"code": 0, "success": true, "msg": "成功", "data": {"datas": newDatas}};
  }
} else if (url.includes("/search/banner_list")) {
  if (obj?.data) {
    obj.data = {};
  }
// 热搜列表
} else if (url.includes("/search/hot_list")) {
  if (obj?.data?.items?.length > 0) {
    obj.data.items = [];
  }
// 整体配置
} else if (url.includes("/system_service/config")) {
  const item = ["app_theme", "loading_img", "splash", "store"];
  if (obj?.data) {
    for (let i of item) {
      delete obj.data[i];
    }
  }
// 详情页小部件
} else if (url.includes("/note/widgets")) {
  const item = ["cooperate_binds", "generic", "note_next_step", "widget_list"];
  if (obj?.data) {
    for (let i of item) {
      delete obj.data[i];
    }
  }
// 关注页信息流 可能感兴趣的人
} else if (url.includes("/user/followings/followfeed")) {
  if (obj?.data?.items?.length > 0) {
    // 白名单
    compactInPlace(obj.data.items, item => item?.recommend_reason === "friend_post");
  }
// 信息流 视频
} else if (url.includes("/note/videofeed")) {
  if (url.includes("/v3/")) {
    if (obj?.data?.length > 0) {
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
    }
  } else if (url.includes("/v4/")) {
    let videoData = [];
    if (obj.data?.length > 0) {
        for (let item of obj.data) {
          // 添加下载按钮（如果未存在）
          if (item?.share_info?.function_entries?.length > 0) {
            const hasDownload = item.share_info.function_entries.some(entry => entry.type === "video_download");
            if (!hasDownload) {
              item.share_info.function_entries.push({type: "video_download"});
            }
          }
    
          // 提取 H.265 视频流
          const h265List = item?.video_info_v2?.media?.stream?.h265 || [];
          if (!Array.isArray(h265List) || h265List.length === 0) {
            continue;
          }
    
          // Select the highest-resolution stream in one pass; preserve first item on ties.
          let selectedStream = null;
          for (const stream of h265List) {
            if (!stream || !stream.master_url || !stream.height) continue;
            if (!selectedStream || Number(stream.height) > Number(selectedStream.height)) {
              selectedStream = stream;
            }
          }
    
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
    }
  }
// 视频保存请求
} else if (url.includes("/note/video/save")) {
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
  }
// 关注列表
} else if (url.includes("/followfeed") && !url.includes("/user/followings")) {
  if (obj?.data?.items?.length > 0) {
    // recommend_user可能感兴趣的人
    compactInPlace(obj.data.items, item => item?.recommend_reason !== "recommend_user");
  }
// 搜索栏填充词
} else if (url.includes("/search/hint")) {
  if (obj?.data?.hint_words?.length > 0) {
    obj.data.hint_words = [];
  }
// 搜索栏
} else if (url.includes("/search/trending")) {
  if (obj?.data?.queries?.length > 0) {
    obj.data.queries = [];
  }
  if (obj?.data?.hint_word) {
    obj.data.hint_word = {};
  }
// 用户详情页 你可能感兴趣的人
} else if (url.includes("/recommend/user/follow_recommend")) {
  if (obj?.data?.title === "你可能感兴趣的人" && obj?.data?.rec_users?.length > 0) {
    obj.data = {};
  }
// 信息流广告
} else if (url.includes("/homefeed")) {
  if (obj?.data?.length > 0) {
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
// 搜索结果
} else if (url.includes("/search/notes")) {
  if (obj?.data?.items?.length > 0) {
    compactInPlace(obj.data.items, item => item?.model_type === "note");
  }
// 加载评论区
} else if (url.includes("/note/comment")) {
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


} else if (url.includes("/interaction/comment/video/download")) {
  const commitsCache = $.getdata("xiaohongshu.comments.rsp");
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
  }
}

$done({body: JSON.stringify(obj)});

}

// 小红书画质增强：加载2K分辨率的图片
function imageEnhance(images) {
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
}


function replaceUrlContent(collectionA, collectionB) {
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
}


function deDuplicateLivePhotos(livePhotos) {
  const seen = new Set();
  return compactInPlace(livePhotos, item => {
    if (seen.has(item.videId)) return false;
    seen.add(item.videId);
    return true;
  });
}


function cleanCommentsAndCollectLivePhotos(data) {
  const livePhotos = [];
  const stack = [data];
  const visited = new WeakSet();
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
    if (!current || typeof current !== "object" || visited.has(current)) continue;
    visited.add(current);
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
}

function Env(t,e){class s{constructor(t){this.env=t}send(t,e="GET"){t="string"==typeof t?{url:t}:t;let s=this.get;"POST"===e&&(s=this.post);const i=new Promise(((e,i)=>{s.call(this,t,((t,s,o)=>{t?i(t):e(s)}))}));return t.timeout?((t,e=1e3)=>Promise.race([t,new Promise(((t,s)=>{setTimeout((()=>{s(new Error("请求超时"))}),e)}))]))(i,t.timeout):i}get(t){return this.send.call(this.env,t)}post(t){return this.send.call(this.env,t,"POST")}}return new class{constructor(t,e){this.logLevels={debug:0,info:1,warn:2,error:3},this.logLevelPrefixs={debug:"[DEBUG] ",info:"[INFO] ",warn:"[WARN] ",error:"[ERROR] "},this.logLevel="info",this.name=t,this.http=new s(this),this.data=null,this.dataFile="box.dat",this.logs=[],this.isMute=!1,this.isNeedRewrite=!1,this.logSeparator="\n",this.encoding="utf-8",this.startTime=(new Date).getTime(),Object.assign(this,e)}getEnv(){return"undefined"!=typeof $environment&&$environment["surge-version"]?"Surge":"undefined"!=typeof $environment&&$environment["stash-version"]?"Stash":"undefined"!=typeof module&&module.exports?"Node.js":"undefined"!=typeof $task?"Quantumult X":"undefined"!=typeof $loon?"Loon":"undefined"!=typeof $rocket?"Shadowrocket":void 0}isNode(){return"Node.js"===this.getEnv()}isQuanX(){return"Quantumult X"===this.getEnv()}isSurge(){return"Surge"===this.getEnv()}isLoon(){return"Loon"===this.getEnv()}isShadowrocket(){return"Shadowrocket"===this.getEnv()}isStash(){return"Stash"===this.getEnv()}toObj(t,e=null){try{return JSON.parse(t)}catch{return e}}toStr(t,e=null,...s){try{return JSON.stringify(t,...s)}catch{return e}}getjson(t,e){let s=e;if(this.getdata(t))try{s=JSON.parse(this.getdata(t))}catch{}return s}setjson(t,e){try{return this.setdata(JSON.stringify(t),e)}catch{return!1}}getScript(t){return new Promise((e=>{this.get({url:t},((t,s,i)=>e(i)))}))}runScript(t,e){return new Promise((s=>{let i=this.getdata("@chavy_boxjs_userCfgs.httpapi");i=i?i.replace(/\n/g,"").trim():i;let o=this.getdata("@chavy_boxjs_userCfgs.httpapi_timeout");o=o?1*o:20,o=e&&e.timeout?e.timeout:o;const[r,a]=i.split("@"),n={url:`http://${a}/v1/scripting/evaluate`,body:{script_text:t,mock_type:"cron",timeout:o},headers:{"X-Key":r,Accept:"*/*"},policy:"DIRECT",timeout:o};this.post(n,((t,e,i)=>s(i)))})).catch((t=>this.logErr(t)))}loaddata(){if(!this.isNode())return{};{this.fs=this.fs?this.fs:require("fs"),this.path=this.path?this.path:require("path");const t=this.path.resolve(this.dataFile),e=this.path.resolve(process.cwd(),this.dataFile),s=this.fs.existsSync(t),i=!s&&this.fs.existsSync(e);if(!s&&!i)return{};{const i=s?t:e;try{return JSON.parse(this.fs.readFileSync(i))}catch(t){return{}}}}}writedata(){if(this.isNode()){this.fs=this.fs?this.fs:require("fs"),this.path=this.path?this.path:require("path");const t=this.path.resolve(this.dataFile),e=this.path.resolve(process.cwd(),this.dataFile),s=this.fs.existsSync(t),i=!s&&this.fs.existsSync(e),o=JSON.stringify(this.data);s?this.fs.writeFileSync(t,o):i?this.fs.writeFileSync(e,o):this.fs.writeFileSync(t,o)}}lodash_get(t,e,s){const i=e.replace(/\[(\d+)\]/g,".$1").split(".");let o=t;for(const t of i)if(o=Object(o)[t],void 0===o)return s;return o}lodash_set(t,e,s){return Object(t)!==t||(Array.isArray(e)||(e=e.toString().match(/[^.[\]]+/g)||[]),e.slice(0,-1).reduce(((t,s,i)=>Object(t[s])===t[s]?t[s]:t[s]=Math.abs(e[i+1])>>0==+e[i+1]?[]:{}),t)[e[e.length-1]]=s),t}getdata(t){let e=this.getval(t);if(/^@/.test(t)){const[,s,i]=/^@(.*?)\.(.*?)$/.exec(t),o=s?this.getval(s):"";if(o)try{const t=JSON.parse(o);e=t?this.lodash_get(t,i,""):e}catch(t){e=""}}return e}setdata(t,e){let s=!1;if(/^@/.test(e)){const[,i,o]=/^@(.*?)\.(.*?)$/.exec(e),r=this.getval(i),a=i?"null"===r?null:r||"{}":"{}";try{const e=JSON.parse(a);this.lodash_set(e,o,t),s=this.setval(JSON.stringify(e),i)}catch(e){const r={};this.lodash_set(r,o,t),s=this.setval(JSON.stringify(r),i)}}else s=this.setval(t,e);return s}getval(t){switch(this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":return $persistentStore.read(t);case"Quantumult X":return $prefs.valueForKey(t);case"Node.js":return this.data=this.loaddata(),this.data[t];default:return this.data&&this.data[t]||null}}setval(t,e){switch(this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":return $persistentStore.write(t,e);case"Quantumult X":return $prefs.setValueForKey(t,e);case"Node.js":return this.data=this.loaddata(),this.data[e]=t,this.writedata(),!0;default:return this.data&&this.data[e]||null}}initGotEnv(t){this.got=this.got?this.got:require("got"),this.cktough=this.cktough?this.cktough:require("tough-cookie"),this.ckjar=this.ckjar?this.ckjar:new this.cktough.CookieJar,t&&(t.headers=t.headers?t.headers:{},t&&(t.headers=t.headers?t.headers:{},void 0===t.headers.cookie&&void 0===t.headers.Cookie&&void 0===t.cookieJar&&(t.cookieJar=this.ckjar)))}get(t,e=(()=>{})){switch(t.headers&&(delete t.headers["Content-Type"],delete t.headers["Content-Length"],delete t.headers["content-type"],delete t.headers["content-length"]),t.params&&(t.url+="?"+this.queryStr(t.params)),void 0===t.followRedirect||t.followRedirect||((this.isSurge()||this.isLoon())&&(t["auto-redirect"]=!1),this.isQuanX()&&(t.opts?t.opts.redirection=!1:t.opts={redirection:!1})),this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":default:this.isSurge()&&this.isNeedRewrite&&(t.headers=t.headers||{},Object.assign(t.headers,{"X-Surge-Skip-Scripting":!1})),$httpClient.get(t,((t,s,i)=>{!t&&s&&(s.body=i,s.statusCode=s.status?s.status:s.statusCode,s.status=s.statusCode),e(t,s,i)}));break;case"Quantumult X":this.isNeedRewrite&&(t.opts=t.opts||{},Object.assign(t.opts,{hints:!1})),$task.fetch(t).then((t=>{const{statusCode:s,statusCode:i,headers:o,body:r,bodyBytes:a}=t;e(null,{status:s,statusCode:i,headers:o,body:r,bodyBytes:a},r,a)}),(t=>e(t&&t.error||"UndefinedError")));break;case"Node.js":let s=require("iconv-lite");this.initGotEnv(t),this.got(t).on("redirect",((t,e)=>{try{if(t.headers["set-cookie"]){const s=t.headers["set-cookie"].map(this.cktough.Cookie.parse).toString();s&&this.ckjar.setCookieSync(s,null),e.cookieJar=this.ckjar}}catch(t){this.logErr(t)}})).then((t=>{const{statusCode:i,statusCode:o,headers:r,rawBody:a}=t,n=s.decode(a,this.encoding);e(null,{status:i,statusCode:o,headers:r,rawBody:a,body:n},n)}),(t=>{const{message:i,response:o}=t;e(i,o,o&&s.decode(o.rawBody,this.encoding))}));break}}post(t,e=(()=>{})){const s=t.method?t.method.toLocaleLowerCase():"post";switch(t.body&&t.headers&&!t.headers["Content-Type"]&&!t.headers["content-type"]&&(t.headers["content-type"]="application/x-www-form-urlencoded"),t.headers&&(delete t.headers["Content-Length"],delete t.headers["content-length"]),void 0===t.followRedirect||t.followRedirect||((this.isSurge()||this.isLoon())&&(t["auto-redirect"]=!1),this.isQuanX()&&(t.opts?t.opts.redirection=!1:t.opts={redirection:!1})),this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":default:this.isSurge()&&this.isNeedRewrite&&(t.headers=t.headers||{},Object.assign(t.headers,{"X-Surge-Skip-Scripting":!1})),$httpClient[s](t,((t,s,i)=>{!t&&s&&(s.body=i,s.statusCode=s.status?s.status:s.statusCode,s.status=s.statusCode),e(t,s,i)}));break;case"Quantumult X":t.method=s,this.isNeedRewrite&&(t.opts=t.opts||{},Object.assign(t.opts,{hints:!1})),$task.fetch(t).then((t=>{const{statusCode:s,statusCode:i,headers:o,body:r,bodyBytes:a}=t;e(null,{status:s,statusCode:i,headers:o,body:r,bodyBytes:a},r,a)}),(t=>e(t&&t.error||"UndefinedError")));break;case"Node.js":let i=require("iconv-lite");this.initGotEnv(t);const{url:o,...r}=t;this.got[s](o,r).then((t=>{const{statusCode:s,statusCode:o,headers:r,rawBody:a}=t,n=i.decode(a,this.encoding);e(null,{status:s,statusCode:o,headers:r,rawBody:a,body:n},n)}),(t=>{const{message:s,response:o}=t;e(s,o,o&&i.decode(o.rawBody,this.encoding))}));break}}time(t,e=null){const s=e?new Date(e):new Date;let i={"M+":s.getMonth()+1,"d+":s.getDate(),"H+":s.getHours(),"m+":s.getMinutes(),"s+":s.getSeconds(),"q+":Math.floor((s.getMonth()+3)/3),S:s.getMilliseconds()};/(y+)/.test(t)&&(t=t.replace(RegExp.$1,(s.getFullYear()+"").substr(4-RegExp.$1.length)));for(let e in i)new RegExp("("+e+")").test(t)&&(t=t.replace(RegExp.$1,1==RegExp.$1.length?i[e]:("00"+i[e]).substr((""+i[e]).length)));return t}queryStr(t){let e="";for(const s in t){let i=t[s];null!=i&&""!==i&&("object"==typeof i&&(i=JSON.stringify(i)),e+=`${s}=${i}&`)}return e=e.substring(0,e.length-1),e}msg(e=t,s="",i="",o={}){const r=t=>{const{$open:e,$copy:s,$media:i,$mediaMime:o}=t;switch(typeof t){case void 0:return t;case"string":switch(this.getEnv()){case"Surge":case"Stash":default:return{url:t};case"Loon":case"Shadowrocket":return t;case"Quantumult X":return{"open-url":t};case"Node.js":return}case"object":switch(this.getEnv()){case"Surge":case"Stash":case"Shadowrocket":default:{const r={};let a=t.openUrl||t.url||t["open-url"]||e;a&&Object.assign(r,{action:"open-url",url:a});let n=t["update-pasteboard"]||t.updatePasteboard||s;if(n&&Object.assign(r,{action:"clipboard",text:n}),i){let t,e,s;if(i.startsWith("http"))t=i;else if(i.startsWith("data:")){const[t]=i.split(";"),[,o]=i.split(",");e=o,s=t.replace("data:","")}else{e=i,s=(t=>{const e={JVBERi0:"application/pdf",R0lGODdh:"image/gif",R0lGODlh:"image/gif",iVBORw0KGgo:"image/png","/9j/":"image/jpg"};for(var s in e)if(0===t.indexOf(s))return e[s];return null})(i)}Object.assign(r,{"media-url":t,"media-base64":e,"media-base64-mime":o??s})}return Object.assign(r,{"auto-dismiss":t["auto-dismiss"],sound:t.sound}),r}case"Loon":{const s={};let o=t.openUrl||t.url||t["open-url"]||e;o&&Object.assign(s,{openUrl:o});let r=t.mediaUrl||t["media-url"];return i?.startsWith("http")&&(r=i),r&&Object.assign(s,{mediaUrl:r}),console.log(JSON.stringify(s)),s}case"Quantumult X":{const o={};let r=t["open-url"]||t.url||t.openUrl||e;r&&Object.assign(o,{"open-url":r});let a=t["media-url"]||t.mediaUrl;i?.startsWith("http")&&(a=i),a&&Object.assign(o,{"media-url":a});let n=t["update-pasteboard"]||t.updatePasteboard||s;return n&&Object.assign(o,{"update-pasteboard":n}),console.log(JSON.stringify(o)),o}case"Node.js":return}default:return}};if(!this.isMute)switch(this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":default:$notification.post(e,s,i,r(o));break;case"Quantumult X":$notify(e,s,i,r(o));break;case"Node.js":break}if(!this.isMuteLog){let t=["","==============📣系统通知📣=============="];t.push(e),s&&t.push(s),i&&t.push(i),console.log(t.join("\n")),this.logs=this.logs.concat(t)}}debug(...t){this.logLevels[this.logLevel]<=this.logLevels.debug&&(t.length>0&&(this.logs=[...this.logs,...t]),console.log(`${this.logLevelPrefixs.debug}${t.map((t=>t??String(t))).join(this.logSeparator)}`))}info(...t){this.logLevels[this.logLevel]<=this.logLevels.info&&(t.length>0&&(this.logs=[...this.logs,...t]),console.log(`${this.logLevelPrefixs.info}${t.map((t=>t??String(t))).join(this.logSeparator)}`))}warn(...t){this.logLevels[this.logLevel]<=this.logLevels.warn&&(t.length>0&&(this.logs=[...this.logs,...t]),console.log(`${this.logLevelPrefixs.warn}${t.map((t=>t??String(t))).join(this.logSeparator)}`))}error(...t){this.logLevels[this.logLevel]<=this.logLevels.error&&(t.length>0&&(this.logs=[...this.logs,...t]),console.log(`${this.logLevelPrefixs.error}${t.map((t=>t??String(t))).join(this.logSeparator)}`))}log(...t){t.length>0&&(this.logs=[...this.logs,...t]),console.log(t.map((t=>t??String(t))).join(this.logSeparator))}logErr(t,e){switch(this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":case"Quantumult X":default:this.log("",`❗️${this.name}, 错误!`,e,t);break;case"Node.js":this.log("",`❗️${this.name}, 错误!`,e,void 0!==t.message?t.message:t,t.stack);break}}wait(t){return new Promise((e=>setTimeout(e,t)))}done(t={}){const e=((new Date).getTime()-this.startTime)/1e3;switch(this.log("",`🔔${this.name}, 结束! 🕛 ${e} 秒`),this.log(),this.getEnv()){case"Surge":case"Loon":case"Stash":case"Shadowrocket":case"Quantumult X":default:$done(t);break;case"Node.js":process.exit(1)}}}(t,e)}
