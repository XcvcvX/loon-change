// loon-change: CNTV response compaction optimization v6; upstream zirawell/R-Store@cfd273d27fdb73dd9dd3f21264e0ba01e8ffbadd
/********************************
CNTV Remove Ads - Version 1.0
Checkout Source - https://raw.githubusercontent.com/RuCu6/QuanX/main/Scripts/cnftp.js
Please note that you may need to reinstall app for script to work.

QuantumultX rewrite link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/A/爱奇艺/rewrite/iqiyi.conf
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/M/芒果TV/rewrite/mgtv.conf
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/QuanX/Adblock/App/Y/优酷视频/rewrite/youku.conf

Surge module link:
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/A/爱奇艺/iqiyi.sgmodule
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/M/芒果TV/mgtv.sgmodule
https://raw.githubusercontent.com/zirawell/R-Store/main/Rule/Surge/Adblock/App/Y/优酷视频/youku.sgmodule
********************************/

// loon-change: CNTV hoisted static membership lists v1
const CNTV_STATIC_FILTER_01 = ["29", "31", "34"];
const CNTV_STATIC_FILTER_02 = ["wd_liebiao_2", "wd_liebiao_3", "wd_liebiao_4"];
const CNTV_STATIC_FILTER_03 = ["1017", "8196", "4525518866820370"];
const CNTV_STATIC_FILTER_04 = ["block_321", "block_415", "block_416"];
const CNTV_STATIC_FILTER_05 = ["comment_resource_card", "comment_resource_convention_card"];
const CNTV_STATIC_FILTER_07 = [
          "ad_mobile_flow", "hot_query_bottom", "hot_query_search_top_ad",
          "search_com_related_query", "search_intent_detail_onesearch",
          "search_mid_text_ad", "search_onebox_v2", "search_small_card_ad",
          "search_topbanner_text", "search_vip_banner"
        ];
const CNTV_STATIC_FILTER_08 = [861, 959];
const CNTV_STATIC_FILTER_09 = ["热门", "推荐"];
const CNTV_STATIC_FILTER_10 = ["842", "2237", "5418"];
const CNTV_STATIC_FILTER_11 = ["1", "2"];
const CNTV_STATIC_FILTER_12 = [202, 203, 301, 601, 701, 702];
const CNTV_STATIC_FILTER_13 = [3, 5, 6, 8];
const CNTV_STATIC_FILTER_14 = ["领取芒果卡权益", "签到赢积分"];
const CNTV_STATIC_FILTER_15 = ["功能实验室", "芒果壁纸", "我的音乐"];
const CNTV_STATIC_FILTER_16 = [2, 8, 9, 14, 17];
const CNTV_STATIC_FILTER_17 = ["detail", "planet"];
const CNTV_STATIC_FILTER_18 = [683367, 683368, 683372, 683502];
const CNTV_STATIC_FILTER_19 = ["HOME", "NEW_UCENTER", "VIP_MEMBER"];
const url = $request.url;
if (!$response.body) {
  $done({});
} else {
// loon-change: CNTV Youku home.query callback-free nested compaction v1
function compactCntvYoukuHomeQuery(items, mode, knownLength) {
  const length = knownLength === undefined ? items.length : knownLength;
  let write = 0;

  if (mode === "root") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const itemData = item?.data;
      const nodeKey = itemData?.nodeKey;
      if (nodeKey === "CHILD" || nodeKey === "COMIC2" || nodeKey === "20230929GREATWORKMFK") continue;

      const indexPositionResult = itemData?.indexPositionResult;
      if (indexPositionResult?.length > 0) itemData.indexPositionResult = [];
      if (itemData?.refreshImg) delete itemData.refreshImg;

      const childNodes = item?.nodes;
      const childLength = childNodes?.length || 0;
      if (childLength > 0) compactCntvYoukuHomeQuery(childNodes, "level2", childLength);

      if (write !== read) items[write] = item;
      write++;
    }
  } else if (mode === "level2") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const itemData = item?.data;
      if (itemData?.crmSale) delete itemData.crmSale;

      const itemTypeName = item?.typeName;
      if (itemTypeName === "UC广告抽屉" || itemTypeName === "橱窗广告") continue;

      const itemId = item?.id;
      if (itemId === 31476) {
        const keywords = itemData?.keywords;
        if (keywords?.length > 0) delete itemData.keywords;
      } else {
        if (itemId === 35505 || itemId === 37335) continue;
        const childNodes = item?.nodes;
        const childLength = childNodes?.length || 0;
        if (childLength > 0) compactCntvYoukuHomeQuery(childNodes, "level3", childLength);
      }

      if (write !== read) items[write] = item;
      write++;
    }
  } else if (mode === "level3") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const itemTypeName = item?.typeName;
      if (itemTypeName === "PHONE_FEED_CARD_B_AD" ||
          itemTypeName === "PHONE_FEED_CARD_S_AD" ||
          itemTypeName === "PHONE_H_UC_AD" ||
          itemTypeName === "PHONE_IMG_A" ||
          itemTypeName === "PHONE_YK_AD_BANNER") continue;

      const childNodes = item?.nodes;
      const childLength = childNodes?.length || 0;
      if (childLength > 0) compactCntvYoukuHomeQuery(childNodes, "level4", childLength);

      if (write !== read) items[write] = item;
      write++;
    }
  } else if (mode === "level4") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const itemTypeName = item?.typeName;
      const itemData = item?.data;
      if (itemTypeName === "PHONE_FEED_CARD_S_AD" || itemData?.hasOwnProperty("ad")) continue;
      if (write !== read) items[write] = item;
      write++;
    }
  } else {
    return items;
  }

  if (write !== length) items.length = write;
  return items;
}

// loon-change: CNTV iQIYI home-feed callback-free compaction v1
function compactCntvIqiyiHomeCards(cards, knownLength) {
  const length = knownLength === undefined ? cards.length : knownLength;
  let write = 0;

  for (let read = 0; read < length; read++) {
    const card = cards[read];
    const aliasName = card?.alias_name;
    if (aliasName === "ad_mobile_flow" ||
        aliasName === "ad_trueview" ||
        aliasName === "focus" ||
        aliasName === "qy_home_vip_opr_banner") continue;

    const topBanner = card?.top_banner;
    const blocks = topBanner?.l_blocks;
    const blocksLength = blocks?.length || 0;
    for (let blockIndex = 0; blockIndex < blocksLength; blockIndex++) {
      const block = blocks[blockIndex];
      const buttons = block?.buttons;
      if (buttons?.length > 0) delete block.buttons;
    }

    if (write !== read) cards[write] = card;
    write++;
  }

  if (write !== length) cards.length = write;
  return cards;
}

const isIQY = url.includes("iqiyi.com/");
const isMG = url.includes("mgtv.com/");
const isYK = url.includes("youku.com/");
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

// loon-change: CNTV pre-parse supported-route guard v1
const shouldProcess =
  (isIQY && (
    url.includes("/bottom_theme?") ||
    url.includes("/common_switch?") ||
    url.includes("/control/") ||
    url.includes("/getMyMenus?") ||
    url.includes("/home_top_menu?") ||
    url.includes("/mixer?") ||
    url.includes("/search.video.iqiyi.com/") ||
    url.includes("/views_category/") ||
    url.includes("/views_comment/") ||
    url.includes("/views_home/") ||
    url.includes("/views_plt/") ||
    url.includes("/views_search/") ||
    url.includes("/waterfall/")
  )) ||
  (isMG && (
    (url.includes("/dynamic/v") && url.includes("/channel/index/")) ||
    url.includes("/channel/vrsList/") ||
    url.includes("/mobile/config?") ||
    url.includes("/mobile/recommend/v") ||
    (url.includes("/channel/index?") && url.includes("/odin/c")) ||
    url.includes("/vod/info?") ||
    url.includes("/module/list?") ||
    url.includes("/video/info?")
  )) ||
  (isYK && (
    url.includes("/collect-api/get_push_interval_config_wx?") ||
    url.includes("columbus.gateway.new.execute") ||
    url.includes("columbus.home.feed/") ||
    url.includes("columbus.home.query/") ||
    url.includes("columbus.uc.query/") ||
    url.includes("columbus.ycp.query/") ||
    url.includes("haidai.lantern.appconfig.get/") ||
    url.includes("huluwa.dispatcher.youthmode.config2/") ||
    url.includes("play.ups.appinfo.get/") ||
    url.includes("soku.yksearch/")
  ));
if (!shouldProcess) {
  $done({});
} else {
let obj = JSON.parse($response.body);

if (isIQY) {
  if (url.includes("/bottom_theme?")) {
    // 爱奇艺 底部tab
    if (obj?.cards?.length > 0) {
      let card = obj.cards[0];
      if (card?.items?.length > 0) {
        // 29首页 31会员中心 34我的 35发现 184随刻视频
        compactInPlace(card.items, (i) => CNTV_STATIC_FILTER_01.includes(i?._id));
        // 修复位置
        for (let i = 0; i < card.items.length; i++) {
          card.items[i].show_order = i + 1;
        }
      }
    }
  } else if (url.includes("/common_switch?")) {
    // 爱奇艺 通用配置
    if (obj?.content?.resource) {
      const items = [
        "activities",
        "ai_guide", // ai指引
        "cast_device_ad",
        "flow_promotion", // 播放器 右上角免流按钮
        "growth_award", // 播放器 会员成长积分
        "ip_restriction_ad",
        "member",
        "ppc_feed_insert",
        "second_floor_guide",
        "speed_ad",
        "vip_tips",
        "vipgrowth_value", // 播放器 会员成长体系
        "vr"
      ];
      for (let i of items) {
        delete obj.content.resource[i];
      }
    }
  } else if (url.includes("/control/")) {
    // 爱奇艺 首页左上角天气图标
    if (obj?.content?.weather) {
      delete obj.content.weather;
    }
  } else if (url.includes("/getMyMenus?")) {
    // loon-change: CNTV getMyMenus in-place compaction v1
    // 爱奇艺 我的页面
    if (obj?.data?.length > 0) {
      compactInPlace(obj.data, item => {
        if (CNTV_STATIC_FILTER_02.includes(item?.statistic?.block)) {
          // 精简列表
          return false;
        }
        if (item?.menuList?.length > 0) {
          // 121有奖限时问卷
          compactInPlace(item.menuList, menu => menu?.menuType !== 121);
        }
        return true;
      });
    }
  } else if (url.includes("/home_top_menu?")) {
    // 爱奇艺 顶部tab
    if (obj?.cards?.length > 0) {
      let card = obj.cards[0];
      if (card?.items?.length > 0) {
        // 1017直播 8196热点 4525518866820370中国梦
        compactInPlace(card.items, (i) => !CNTV_STATIC_FILTER_03.includes(i?._id));
        for (let i = 0; i < card.items.length; i++) {
          card.items[i].show_order = i + 1;
        }
      }
    }
  } else if (url.includes("/mixer?")) {
    // 爱奇艺 开屏广告 播放广告
    if (obj?.errorCode === 0) {
      const items = ["adSlots", "splashLottieFile", "splashUiConfig"];
      for (let i of items) {
        delete obj[i];
      }
    }
  } else if (url.includes("/search.video.iqiyi.com/")) {
    // 爱奇艺 搜索框填充
    if (obj?.cache_expired_sec) {
      obj.cache_expired_sec = 1;
    }
    if (obj?.data) {
      obj.data = [{query: "搜索内容"}];
    }
    if (obj?.show_style?.roll_period) {
      obj.show_style.roll_period = 1000;
    }
  } else if (url.includes("/views_category/")) {
    // loon-change: CNTV iQIYI feed array compaction v1 
    // 爱奇艺各菜单列表：原地压缩 cards/blocks，避免双层临时数组。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, card => {
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, item =>
            !CNTV_STATIC_FILTER_04.includes(item?.block_name) &&
            item?.buttons?.[0]?.id !== "ad"
          );
        }
        return true;
      });
    }
  } else if (url.includes("/views_comment/")) {
    // 爱奇艺 播放页评论区
    if (obj?.cards?.length > 0) {
      // 评论资源位 无alias_name字段的为广告
      compactInPlace(obj.cards, 
          (i) =>
              i.hasOwnProperty("alias_name") &&
              !CNTV_STATIC_FILTER_05.includes(i?.alias_name)
      );
    }
  } else if (url.includes("/views_home/")) { 
    // 爱奇艺首页信息流：回调-free 稳定原地压缩广告卡片。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    const homeCards = obj?.cards;
    const homeCardsLength = homeCards?.length || 0;
    if (homeCardsLength > 0) {
      compactCntvIqiyiHomeCards(homeCards, homeCardsLength);
    }
    // loon-change: CNTV iQIYI home-feed callback-free route v1
  } else if (url.includes("/views_plt/")) {
    // 爱奇艺 播放详情页组件
    if (obj?.kv_pair) {
      // activity_tab活动标签页 cloud_cinema云影院卡片 vip_fixed_card会员优惠购买卡片
      const items = ["activity_tab", "cloud_cinema", "vip_fixed_card"];
      for (let i of items) {
        delete obj.kv_pair[i];
      }
    }
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, 
          (i) =>
              ![
                "bi_playlist", // 必播单 当下最热电影推荐
                // "cloud_cinema_detail_character", // 云影院演员列表
                // "cloud_cinema_detail_synopsis", // 云影院详情简介
                // "cloud_cinema_play_detail_tag", // 云影院详情标签
                "cloud_cinema_play_privilege", // 云影院底部文字
                "cloud_cinema_playlist", // 云影院播单
                "cloud_cinema_playlist_1", // 云影院播单2
                "cloud_cinema_playlist_2", // 云影院播单3
                // "cloud_cinema_preview_collection", // 云影院预告片选集
                "cloud_cinema_privilege_icon", // 云影院内容权益
                "cloud_cinema_star_activities", // 云影院推广横幅
                "play_ad_no_vip", // 视频关联广告
                "play_around", // 周边视频 短视频
                // "play_collection", // 选集
                "play_custom_card", // 偶像练习生定制卡片
                // "play_detail_tag", // 详情标签
                // "play_rap_custom", // 综艺 svip舞台纯享
                // "play_series_collection", // 综艺 选集 看点
                "play_splendid_collection", // 综艺 合集 正片没有的都在这里
                "play_type_topical_card_3", // 综艺 幕后花絮
                "play_type_topical_card_4", // 综艺 精彩二创
                "play_variety_custom_2", // 综艺 精彩看点
                "play_vertical", // 综艺 竖屏内容
                "play_vip_promotion", // 会员推广
                "play_water_fall_like", // 猜你喜欢
                "play_water_fall_like_title", // 猜你喜欢标题
                "plt_cloud_cinema_photo", // 云影院剧照 清晰度低
                // "plt_cloud_cinema_short1", // 云影院官方短视频
                "plt_cloud_cinema_short2", // 云影院短视频剪辑
                "plt_playlist", // 播单
                "plt_playlist_1", // 播单2
                "plt_playlist_2", // 播单3
                "funny_short_video" // 精彩短视频
              ]?.includes(i?.alias_name)
      );
    }
  } else if (url.includes("/views_search/")) { 
    // 爱奇艺搜索结果：卡片与 blocks 均原地压缩。
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, card => {
        if (CNTV_STATIC_FILTER_07.includes(card?.strategy_com_id)) return false;
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, item =>
            item.hasOwnProperty("block_name") ||
            (item.hasOwnProperty("block_type") && !CNTV_STATIC_FILTER_08.includes(item?.block_type))
          );
        }
        return true;
      });
    }
  } else if (url.includes("/waterfall/")) { 
    // 爱奇艺瀑布流：外层卡片和内层 blocks 原地压缩。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, card => {
        if (card.hasOwnProperty("block_class")) return false;
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, item => !item.hasOwnProperty("block_class"));
        }
        return true;
      });
    }
  }
} else if (isMG) {
  if (url.includes("/dynamic/v") && url.includes("/channel/index/")) {
    // loon-change: CNTV MangoTV response array compaction v1
    // 芒果 首页信息流
    if (obj?.adInfo) {
      delete obj.adInfo;
    }
    if (obj?.data?.length > 0) {
      compactInPlace(obj.data, item => {
        // 908热剧轮播
        if (item?.moduleEntityId === "91" && item?.DSLList?.length > 0) {
          compactInPlace(item.DSLList, entry => {
            if (entry?.data?.items?.length > 0) {
              compactInPlace(entry.data.items, video =>
                video?.id !== 0 && !CNTV_STATIC_FILTER_09.includes(video?.cornerTitle)
              );
            }
            return true;
          });
        }
        // 842会员首月特惠 2237横版购物tab 5418横版推广图片
        return !CNTV_STATIC_FILTER_10.includes(item?.moduleEntityId);
      });
    }
    if (obj?.moduleIDS?.length > 0) {
      compactInPlace(obj.moduleIDS, (i) => !CNTV_STATIC_FILTER_10.includes(i?.moduleEntityId));
    }
  } else if (url.includes("/channel/vrsList/")) {
    // 芒果 顶部tab
    if (obj?.data?.length > 0) {
      // 100033热门 100043短剧 100160会员频道精选 100308短视频
      compactInPlace(obj.data, item => !(item?.vclassId > 100033 && item?.vclassId !== 100160));
    }
  } else if (url.includes("/mobile/config?")) {
    // 芒果 底部tab
    const items = [
      "XmVideoB",
      "XmsellSwitch",
      "damang_duanju_tab",
      "damang_tab",
      "dc_adConfig",
      "relative_ads",
      "second_floor_guide_switch"
    ];
    for (let i of items) {
      if (obj?.data?.[i]) {
        obj.data[i] = "0";
      }
    }
    if (obj?.data?.XmFsLvlCatAddr) {
      obj.data.XmFsLvlCatAddr = "";
    }
  } else if (url.includes("/mobile/recommend/v")) {
    // 芒果 搜索框填充词
    if (obj?.data?.default) {
      obj.data.default = {0: ["搜索内容"]};
    }
    if (obj?.data?.recommend) {
      obj.data.recommend = [];
    }
    if (obj?.data?.interval) {
      obj.data.interval = 1000;
    }
  } else if (url.includes("/channel/index?") && url.includes("/odin/c")) {
    // 芒果 首页信息流
    if (obj?.data?.length > 0) {
      // 横版按钮
      compactInPlace(obj.data, item => item?.moduleType !== "childslideicon");
    }
  } else if (url.includes("/vod/info?")) {
    // 芒果 播放页详情页组件
    if (obj?.data?.config?.ad) {
      // 播放广告
      obj.data.config.ad.wmShowTime = 0;
    }
    if (obj?.data?.config?.videoRcMod) {
      // 播放弹窗
      obj.data.config.videoRcMod.toastStatus = 0;
      obj.data.config.videoRcMod.toastTime = 0;
    }
    if (obj?.data?.tabs?.length > 0) {
      // 播放标签页 1视频 2讨论
      compactInPlace(obj.data.tabs, (i) => CNTV_STATIC_FILTER_11.includes(i?.type));
    }
    if (obj?.data?.template?.modules?.length > 0) {
      // 播放页组件
      // 101简介 102点赞评论收藏 201正片列表 205会员衍生模块 206音频有声剧
      // 202精彩短片 203精选特辑 301热门内容 601周边大放送 701通栏广告 702大风车浮层广告
      compactInPlace(obj.data.template.modules, item => {
        if (CNTV_STATIC_FILTER_12.includes(item?.dataType)) return false;
        if (item?.clipInfo?.rcInfo) {
          // 播放界面推荐语
          delete item.clipInfo.rcInfo;
        }
        return true;
      });
    }
    if (obj?.data?.template?.theme) {
      // 播放页主题皮肤
      delete obj.data.template.theme;
    }
  } else if (url.includes("/module/list?")) {
    // 芒果 我的页面组件
    if (obj?.data?.list?.length > 0) {
      compactInPlace(obj.data.list, item => {
        // 3推荐位模块 5大芒计划/我的小芒 6banner图模块 8运营商/兴趣/推荐功能
        if (CNTV_STATIC_FILTER_13.includes(item?.moduleType)) return false;
        if (item?.moduleType === 2 && item?.title === "用户信息模块" && item?.data?.length > 0) {
          compactInPlace(item.data, entry => !CNTV_STATIC_FILTER_14.includes(entry?.title));
        } else if (item?.moduleType === 7 && item?.title === "我的服务" && item?.data?.length > 0) {
          compactInPlace(item.data, entry => !CNTV_STATIC_FILTER_15.includes(entry?.title));
        }
        return true;
      });
    }
  } else if (url.includes("/video/info?")) {
    // 芒果 播放详情页组件
    if (obj?.data?.categoryList?.length > 0) {
      // 1正片 2花絮片段 6设备信息 7未知 8看了还会看 9精华打包 10未知 14vip
      // 15未知 17周边大放送 18未知 20出品人 22未知 30未知 31系列推荐
      // 35音乐fm入口 36为你推荐 37音乐fm入口
      compactInPlace(obj.data.categoryList, (i) => !CNTV_STATIC_FILTER_16.includes(i?.dataType));
    }
  }
} else if (isYK) {
  if (url.includes("/collect-api/get_push_interval_config_wx?")) {
    // 优酷 热剧弹窗
    if (obj?.data) {
      const items = ["tipContent", "tipContentNew"];
      for (let i of items) {
        delete obj.data[i];
      }
    }
  } else if (url.includes("columbus.gateway.new.execute")) {
    // 优酷 播放详情页组件
    if (obj?.data?.["2019030100"]?.data) {
      let objData = obj.data["2019030100"].data;
      if (objData?.data?.global) {
        let config = objData.data.global;
        if (config?.PHONE_DETAIL_TOP_TAB?.pageTabs?.length > 0) {
          // detail视频 list热门 planet讨论
          compactInPlace(config.PHONE_DETAIL_TOP_TAB.pageTabs, (i) =>
              CNTV_STATIC_FILTER_17.includes(i?.code)
          );
        }
      }
      if (objData?.nodes?.length > 0) {
        if (objData?.nodes?.length === 1) {
          let node0 = objData.nodes[0];
          if (node0?.nodes?.length > 0) {
            if (node0?.typeName === "NORMAL") {
              compactInPlace(node0.nodes, 
                  (i) =>
                      ![
                        "PHONE_CHD_AGE_DETAIL_2",
                        "PHONE_CHILD_SERIES_A",
                        "PHONE_CHILD_STAR_A",
                        "PHONE_DEFALT_SCROLL_C",
                        "Phone运营banner",
                        "播放页触达组件", // 新版
                        "播放页广告组件",
                        "播放页会员引导组件",
                        "播放页活动组件",
                        "播放页全屏播后推荐组件",
                        "播放页少儿品牌专区组件",
                        "播放页推荐组件",
                        "播放页用户触达组件", // 旧版
                        "播放页有料不能停组件",
                        "球区自动化组件",
                        "优酷购"
                      ]?.includes(i?.typeName)
              );
            } else if (node0?.typeName === "FEED_CHILD_DRAWER_PAGINATION") {
              // 播放页推荐信息流
              if (node0?.nodes) {
                node0.nodes = [];
              }
            } else if (node0?.typeName === "FEED_DRAWER_PAGINATION") {
              // 播放页推荐信息流
              if (node0?.nodes) {
                node0.nodes = [];
              }
            }
          }
        } else {
          objData.nodes = [];
        }
      }
    }
  } else if (url.includes("columbus.home.feed/")) {
    // loon-change: CNTV Youku home.feed in-place compaction v1
    // 首页信息流：原地压缩广告卡片组内节点，避免创建临时数组。
    if (obj?.data?.["2019061000"]?.data) {
      const nodes = obj.data["2019061000"].data.nodes;
      if (nodes?.length > 0) {
        for (let i = 0, length = nodes.length; i < length; i++) {
          const item = nodes[i];
          if (item?.typeName !== "PHONE_FEED_CARD_GROUP" || item?.nodes?.length <= 0) continue;
          const items = item.nodes;
          let write = 0;
          for (let read = 0, itemLength = items.length; read < itemLength; read++) {
            const card = items[read];
            if (card?.typeName !== "PHONE_FEED_CARD_S_AD" && card?.typeName !== "PHONE_H_UC_AD") {
              if (write !== read) items[write] = card;
              write++;
            }
          }
          items.length = write;
        }
      }
    }
  } else if (url.includes("columbus.home.query/")) {
    // 优酷首页菜单与信息流：四层节点直接遍历，不创建逐项回调。
    if (obj?.data?.["2019061000"]?.data) {
      const objData = obj.data["2019061000"].data;
      const homeData = objData?.data;
      const indexPositionResult = homeData?.indexPositionResult;
      if (indexPositionResult?.length > 0) homeData.indexPositionResult = [];

      const rootNodes = objData?.nodes;
      const rootNodesLength = rootNodes?.length || 0;
      if (rootNodesLength > 0) {
        compactCntvYoukuHomeQuery(rootNodes, "root", rootNodesLength);
      }
    }
  // loon-change: CNTV Youku home.query callback-free route v1
  // loon-change: CNTV Youku home.query nested in-place compaction v1
  } else if (url.includes("columbus.uc.query/")) {
    // loon-change: CNTV Youku user-center nested in-place compaction v1
    // 保留原有 allowlist 和顺序，直接压缩个人中心节点及两层子节点。
    if (obj?.data?.["2019061000"]?.data) {
      const objNodes = obj.data["2019061000"].data.nodes?.[0];
      const userCenterNodes = objNodes?.nodes;
      const userCenterLength = userCenterNodes?.length || 0;
      if (userCenterLength > 0) {
        let userCenterWrite = 0;
        for (let userCenterRead = 0; userCenterRead < userCenterLength; userCenterRead++) {
          const item = userCenterNodes[userCenterRead];
          const itemId = item?.id;
          if (itemId === 32133 || itemId === 32775 || itemId === 22570 ||
              itemId === 35942 || itemId === 36014 || itemId === 38466) {
            continue;
          }
          if (itemId === 28912) {
            // 我的下载 收藏 购买 场景
            const downloadNodes = item?.nodes;
            const downloadLength = downloadNodes?.length || 0;
            if (downloadLength > 0) {
              let downloadWrite = 0;
              for (let downloadRead = 0; downloadRead < downloadLength; downloadRead++) {
                const downloadItem = downloadNodes[downloadRead];
                if (downloadItem?.id === 110429) continue;
                if (downloadWrite !== downloadRead) downloadNodes[downloadWrite] = downloadItem;
                downloadWrite++;
              }
              downloadNodes.length = downloadWrite;
            }
          } else if (itemId === 36015) {
            // 功能区 卡卷包 商城 设置
            const itemNodes = item?.nodes;
            if (itemNodes?.length > 0) {
              const firstNode = itemNodes[0];
              const settingNodes = firstNode?.nodes;
              const settingLength = settingNodes?.length || 0;
              if (settingLength > 0) {
                let settingWrite = 0;
                for (let settingRead = 0; settingRead < settingLength; settingRead++) {
                  const settingItem = settingNodes[settingRead];
                  if (!CNTV_STATIC_FILTER_18.includes(settingItem?.id)) continue;
                  if (settingWrite !== settingRead) settingNodes[settingWrite] = settingItem;
                  settingWrite++;
                }
                settingNodes.length = settingWrite;
              }
            }
          }
          if (userCenterWrite !== userCenterRead) userCenterNodes[userCenterWrite] = item;
          userCenterWrite++;
        }
        userCenterNodes.length = userCenterWrite;
      }
    }
  } else if (url.includes("columbus.ycp.query/")) {
    // loon-change: CNTV Youku comment-list nested in-place compaction v1
    // 评论区节点及其子节点原地压缩，保持父子顺序和原有过滤条件。
    if (obj?.data?.["2019061000"]?.data) {
      const objNodes = obj.data["2019061000"].data.nodes?.[0];
      const commentNodes = objNodes?.nodes;
      const commentLength = commentNodes?.length || 0;
      if (commentLength > 0) {
        let commentWrite = 0;
        for (let commentRead = 0; commentRead < commentLength; commentRead++) {
          const item = commentNodes[commentRead];
          const itemId = item?.id;
          if (itemId === 23242 || itemId === 23243) {
            const childNodes = item?.nodes;
            const childLength = childNodes?.length || 0;
            if (childLength > 0) {
              let childWrite = 0;
              for (let childRead = 0; childRead < childLength; childRead++) {
                const child = childNodes[childRead];
                const removeNotice = itemId === 23242 &&
                  (child?.typeName === "COMPONENT_YCP_NOTICE" || child?.id === 113941);
                const removeAd = itemId === 23243 && child?.id === -1000;
                if (removeNotice || removeAd) continue;
                if (childWrite !== childRead) childNodes[childWrite] = child;
                childWrite++;
              }
              childNodes.length = childWrite;
            }
          }
          if (commentWrite !== commentRead) commentNodes[commentWrite] = item;
          commentWrite++;
        }
        commentNodes.length = commentWrite;
      }
    }
  } else if (url.includes("haidai.lantern.appconfig.get/")) {
    // 优酷 底部tab
    if (obj?.data?.model?.configInfo?.bottomNavigate) {
      let bottom = obj.data.model.configInfo.bottomNavigate;
      if (bottom?.data?.bottomTabList?.length > 0) {
        // HOME首页 DONGTAI短视频 SEARCH淘好片 VIP_MEMBER会员 NEW_UCENTER我的
        compactInPlace(bottom.data.bottomTabList, (i) =>
            CNTV_STATIC_FILTER_19.includes(i?.type)
        );
        // 修复位置
        for (let i = 0; i < bottom.data.bottomTabList.length; i++) {
          bottom.data.bottomTabList[i].menuIndex = i + 1;
        }
      }
    }
  } else if (url.includes("huluwa.dispatcher.youthmode.config2/")) {
    // 优酷 青少年模式弹窗
    if (obj?.data?.result) {
      obj.data.result = {};
    }
  } else if (url.includes("play.ups.appinfo.get/")) {
    // 优酷 开屏广告 播放广告
    if (obj?.data?.data) {
      const items = ["ad", "watermark", "ykad"];
      for (let i of items) {
        delete obj.data.data[i];
      }
    }
  } else if (url.includes("soku.yksearch/")) {
    // 优酷 搜索页面组件
    if (obj?.data?.nodes?.length > 0) {
      // 仅保留搜索tab
      compactInPlace(obj.data.nodes, (i) => i.hasOwnProperty("data"));
    }
  }
}

$done({body: JSON.stringify(obj)});
}
}
