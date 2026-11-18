// loon-change: Zhihu response hot-path optimization v1; upstream zirawell/R-Store@d0f4dd305bade7cc6a38e3445a768d72aaea0e5b
/********************************
Zhihu Remove Ads - Version 1.0
Checkout Source - https://raw.githubusercontent.com/RuCu6/QuanX/main/Scripts/zhihu.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/Z/知乎/rewrite/zhihu.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/Z/知乎/zhihu.sgmodule
********************************/

if (!$response.body) {
  $done({});
} else {
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
let obj = JSON.parse($response.body);

if (url.includes("/answers/v2/") || url.includes("/articles/v2/")) {
  // 2024-04-29 新版知乎 回答列表下的相关提问
  if (obj?.third_business?.related_queries?.queries?.length > 0) {
    obj.third_business.related_queries.queries = [];
  }
} else if (url.includes("/api/cloud/config/all")) {
  if (obj?.data?.configs) {
    obj.data.configs.forEach((i) => {
      if (i.configKey === "feed_gray_theme") {
        if (i.configValue) {
          i.configValue.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
          i.configValue.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
          i.status = false;
        }
      } else if (i.configKey === "feed_top_res") {
        if (i.configValue) {
          i.configValue.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
          i.configValue.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
          i.status = false;
        }
      }
    });
  }
} else if (url.includes("/api/v4/answers")) {
  if (obj?.data) {
    delete obj.data;
  }
  if (obj?.paging) {
    delete obj.paging;
  }
} else if (url.includes("/api/v4/articles")) {
  const item = ["ad_info", "paging", "recommend_info"];
  item.forEach((i) => {
    delete obj[i];
  });
} else if (url.includes("/appcloud2.zhihu.com/v3/config")) {
  if (obj?.config) {
    if (obj.config?.homepage_feed_tab) {
      compactInPlace(obj.config.homepage_feed_tab.tab_infos, (i) => {
        if (i.tab_type === "activity_tab") {
          i.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
          i.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
          return true;
        } else {
          return false;
        }
      });
    }
    if (obj.config?.hp_channel_tab) {
      delete obj.config.hp_channel_tab;
    }
    if (obj.config?.zombie_conf) {
      obj.config.zombie_conf.zombieEnable = false;
    }
    if (obj.config?.gray_mode) {
      obj.config.gray_modeenable = false;
      obj.config.gray_mode.start_time = "3818332800"; // Unix 时间戳 2090-12-31 00:00:00
      obj.config.gray_mode.end_time = "3818419199"; // Unix 时间戳 2090-12-31 23:59:59
    }
    if (obj.config?.zhcnh_thread_sync) {
      obj.config.zhcnh_thread_sync.LocalDNSSetHostWhiteList = [];
      obj.config.zhcnh_thread_sync.isOpenLocalDNS = "0";
      obj.config.zhcnh_thread_sync.ZHBackUpIP_Switch_Open = "0";
      obj.config.zhcnh_thread_sync.dns_ip_detector_operation_lock = "1";
      obj.config.zhcnh_thread_sync.ZHHTTPSessionManager_setupZHHTTPHeaderField = "1";
    }
    obj.config.zvideo_max_number = 1;
    obj.config.is_show_followguide_alert = false;
  }
} else if (url.includes("/bazaar/vip_tab/header")) {
  if (obj?.activity_banner) {
    // 一元领会员
    delete obj.activity_banner;
  }
  if (obj?.activity_window) {
    // 会员弹窗
    delete obj.activity_window;
  }
  if (obj?.vip_tip) {
    // 开通会员提示信息
    delete obj.vip_tip;
  }
} else if (url.includes("/commercial_api/app_float_layer")) {
  // 悬浮图标
  if ("feed_egg" in obj) {
    delete obj;
  }
} else if (url.includes("/feed/render/tab/config")) {
  if (obj?.selected_sections?.length > 0) {
    // 首页顶部tab
    compactInPlace(obj.selected_sections, (i) => (i?.tab_type !== "activity" && i?.tab_type !== "live"));
  }
} else if (url.includes("/moments_v3")) {
  if (obj?.data?.length > 0) {
    compactInPlace(obj.data, (i) => !i?.title?.includes("为您推荐"));
  }
} else if (url.includes("/next-bff")) {
  if (obj?.data?.length > 0) {
    compactInPlace(obj.data, 
        (i) =>
            !(
                i?.origin_data?.type?.includes("ad") ||
                i?.origin_data?.resource_type?.includes("ad") ||
                i?.origin_data?.next_guide?.title?.includes("推荐")
            )
    );
  }
} else if (url.includes("/next-data")) {
  if (obj?.data?.data?.length > 0) {
    compactInPlace(obj.data.data, (i) => !(i?.type?.includes("ad") || i?.data?.answer_type?.includes("PAID")));
  }
} else if (url.includes("/next-render")) {
  if (obj?.data?.length > 0) {
    compactInPlace(obj.data, 
        (i) =>
            !(
                i?.adjson ||
                i?.biz_type_list?.includes("article") ||
                i?.biz_type_list?.includes("content") ||
                i?.business_type?.includes("paid") ||
                i?.section_info ||
                i?.tips ||
                i?.type?.includes("ad")
            )
    );
  }
} else if (url.includes("/questions/")) {
  // 问题回答列表
  if (obj?.data?.length > 0) {
    compactInPlace(obj.data, (i) => !i?.target?.answer_type?.includes("paid"));
  }
  if (obj?.data?.ad_info) {
    delete obj.data.ad_info;
  }
  if (obj?.ad_info) {
    delete obj.ad_info;
  }
  if (obj?.query_info) {
    delete obj.query_info;
  }
} else if (url.includes("/root/tab")) {
  // 首页顶部标签页
  if (obj?.tab_list?.length > 0) {
    compactInPlace(obj.tab_list, (i) => (i?.tab_name !== "故事" && i?.tab_name !== "活动" && i?.tab_name !== "想法"));
  }
} else if (url.includes("/topstory/hot-lists/everyone-seeing")) {
  // 热榜信息流
  if (obj?.data?.data?.length > 0) {
    // 合作推广
    compactInPlace(obj.data.data, (i) => !i.target?.metrics_area?.text?.includes("合作推广"));
  }
} else if (url.includes("/topstory/hot-lists/total")) {
  // 热榜排行榜
  if (obj?.data?.length > 0) {
    // 品牌甄选
    compactInPlace(obj.data, (i) => !i.hasOwnProperty("ad"));
  }
} else if (url.includes("/topstory/recommend")) {
  const fallbackSearch = '"feed_content":{"video":{"id":';
  const fallbackIndex = $response.body.indexOf(fallbackSearch);
  const fallbackVideoID = fallbackIndex >= 0
    ? $response.body.slice(fallbackIndex + fallbackSearch.length).split(",", 1)[0].replace(/}+$/, "")
    : undefined;
  // 推荐信息流
  if (obj?.data?.length > 0) {
    compactInPlace(obj.data, (i) => {
      if (i.type === "market_card" && i.fields?.header?.url && i.fields.body?.video?.id) {
        let videoID = getUrlParamValue(i.fields.header.url, "videoID");
        if (videoID) {
          i.fields.body.video.id = videoID;
        }
      } else if (i.type === "common_card") {
        if (i.extra?.type === "drama") {
          // 直播内容
          return false;
        } else if (i.extra?.type === "zvideo") {
          // 推广视频
          let videoUrl = i.common_card.feed_content.video.customized_page_url;
          let videoID = getUrlParamValue(videoUrl, "videoID");
          if (videoID) {
            i.common_card.feed_content.video.id = videoID;
          }
        } else if (i.common_card?.feed_content?.video?.id) {
          if (fallbackVideoID !== undefined) {
            i.common_card.feed_content.video.id = fallbackVideoID;
          }
        } else if (i.common_card?.footline?.elements?.[0]?.text?.panel_text?.includes("广告")) {
          return false;
        } else if (i.common_card?.feed_content?.source_line?.elements?.[1]?.text?.panel_text?.includes("盐选")) {
          return false;
        } else if (i?.promotion_extra) {
          // 营销信息
          return false;
        }
        return true;
      } else if (i.type?.includes("aggregation_card")) {
        // 横排卡片 知乎热榜
        return false;
      } else if (i.type === "feed_advert") {
        // 伪装成正常内容的卡片
        return false;
      }
      return true;
    });
    fixPos(obj.data);
  }
}

$done({body: JSON.stringify(obj)});

// 修复offset
function fixPos(arr) {
  for (let i = 0; i < arr.length; i++) {
    arr[i].offset = i + 1;
  }
}

function getUrlParamValue(url, queryName) {
  if (typeof url !== "string") return undefined;
  const question = url.indexOf("?");
  if (question < 0) return undefined;
  const query = url.slice(question + 1).split("#", 1)[0];
  let value;
  for (const part of query.split("&")) {
    const equal = part.indexOf("=");
    const key = equal < 0 ? part : part.slice(0, equal);
    if (key === queryName) value = equal < 0 ? undefined : part.slice(equal + 1);
  }
  return value;
}
}
