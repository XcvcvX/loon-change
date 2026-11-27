// loon-change: CNFTP response filter in-place compaction v1
// loon-change: Youku home.query in-place compaction v1; upstream fmz200/wool_scripts@f6bcc087e4da7ebef3c596be4a3c0fa406661564
// loon-change: Youku home.feed in-place compaction v1
// 2025-03-08 22:15

const url = $request.url;

let modified = false;

function compactInPlace(items, keep) {
  let write = 0;
  const length = items.length;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  if (write !== length) {
    items.length = write;
    modified = true;
  }
  return items;
}

// loon-change: Youku home.feed callback-free nested compaction v1
function compactYoukuHomeFeed(rootNodes, knownLength) {
  const rootLength = knownLength === undefined ? rootNodes.length : knownLength;
  for (let read = 0; read < rootLength; read++) {
    const node = rootNodes[read];
    if (node?.typeName !== "PHONE_FEED_CARD_GROUP") continue;

    const groupNodes = node?.nodes;
    const groupNodesLength = groupNodes?.length || 0;
    if (groupNodesLength === 0) continue;

    let write = 0;
    for (let groupRead = 0; groupRead < groupNodesLength; groupRead++) {
      const child = groupNodes[groupRead];
      const childTypeName = child?.typeName;
      if (childTypeName === "PHONE_FEED_CARD_S_AD" || childTypeName === "PHONE_H_UC_AD") continue;
      if (write !== groupRead) groupNodes[write] = child;
      write++;
    }

    if (write !== groupNodesLength) {
      groupNodes.length = write;
      modified = true;
    }
  }
  return rootNodes;
}

// loon-change: Youku home.query callback-free nested compaction v1
function compactYoukuHomeQuery(items, mode, knownLength) {
  const length = knownLength === undefined ? items.length : knownLength;
  let write = 0;

  if (mode === "root") {
    for (let read = 0; read < length; read++) {
      const node1 = items[read];
      const node1Data = node1?.data;
      const nodeKey = node1Data?.nodeKey;
      if (nodeKey === "CHILD" || nodeKey === "COMIC2" || nodeKey === "20230929GREATWORKMFK") continue;

      const indexPositionResult = node1Data?.indexPositionResult;
      if (indexPositionResult?.length > 0) {
        // 剧集 电影 二楼
        setIfDifferent(node1Data, "indexPositionResult", []);
      }
      const refreshImg = node1Data?.refreshImg;
      if (refreshImg) {
        // 电影 综艺 纪录片 下拉刷新的背景图片
        deleteIfPresent(node1Data, "refreshImg");
      }

      const node1Nodes = node1?.nodes;
      const node1NodesLength = node1Nodes?.length || 0;
      if (node1NodesLength > 0) {
        compactYoukuHomeQuery(node1Nodes, "level2", node1NodesLength);
      }
      if (write !== read) items[write] = node1;
      write++;
    }
  } else if (mode === "level2") {
    for (let read = 0; read < length; read++) {
      const node2 = items[read];
      const node2Data = node2?.data;
      const crmSale = node2Data?.crmSale;
      if (crmSale) {
        // 季卡会员横幅
        deleteIfPresent(node2Data, "crmSale");
      }
      const node2TypeName = node2?.typeName;
      if (node2TypeName === "UC广告抽屉" || node2TypeName === "橱窗广告") continue;

      const node2Id = node2?.id;
      const keywords = node2Data?.keywords;
      if (node2Id === 31476 && keywords?.length > 0) {
        // 正在热播滚动热词
        deleteIfPresent(node2Data, "keywords");
      }
      if (node2Id === 35505 || node2Id === 37335) continue;

      const node2Nodes = node2?.nodes;
      const node2NodesLength = node2Nodes?.length || 0;
      if (node2NodesLength > 0) {
        compactYoukuHomeQuery(node2Nodes, "level3", node2NodesLength);
      }
      if (write !== read) items[write] = node2;
      write++;
    }
  } else if (mode === "level3") {
    for (let read = 0; read < length; read++) {
      const node3 = items[read];
      const node3TypeName = node3?.typeName;
      if (node3TypeName === "PHONE_FEED_CARD_B_AD" ||
          node3TypeName === "PHONE_FEED_CARD_S_AD" ||
          node3TypeName === "PHONE_H_UC_AD" ||
          node3TypeName === "PHONE_IMG_A" ||
          node3TypeName === "PHONE_YK_AD_BANNER") continue;
      const node3Id = node3?.id;
      // 首页轮播广告
      if (node3Id === 272768) continue;

      const node3Nodes = node3?.nodes;
      const node3NodesLength = node3Nodes?.length || 0;
      if (node3NodesLength > 0) {
        compactYoukuHomeQuery(node3Nodes, "level4", node3NodesLength);
      }
      if (write !== read) items[write] = node3;
      write++;
    }
  } else if (mode === "level4") {
    for (let read = 0; read < length; read++) {
      const node4 = items[read];
      const node4TypeName = node4?.typeName;
      const node4Data = node4?.data;
      if (node4TypeName === "PHONE_FEED_CARD_S_AD" || node4Data?.hasOwnProperty("ad")) continue;
      if (write !== read) items[write] = node4;
      write++;
    }
  } else {
    return items;
  }

  if (write !== length) {
    items.length = write;
    modified = true;
  }
  return items;
}


// loon-change: CNFTP lazy response serialization v1
function sameValue(current, value) {
  if (current === value) return true;
  if (Array.isArray(value)) {
    if (!Array.isArray(current) || current.length !== value.length) return false;
    for (let i = 0; i < value.length; i++) {
      if (!sameValue(current[i], value[i])) return false;
    }
    return true;
  }
  if (value && typeof value === "object") {
    if (!current || typeof current !== "object" || Array.isArray(current)) return false;
    let valueCount = 0;
    for (const key in value) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) continue;
      valueCount++;
      if (!Object.prototype.hasOwnProperty.call(current, key) ||
          !sameValue(current[key], value[key])) return false;
    }
    let currentCount = 0;
    for (const key in current) {
      if (Object.prototype.hasOwnProperty.call(current, key)) currentCount++;
    }
    return valueCount === currentCount;
  }
  return false;
}

function setIfDifferent(target, key, value) {
  if (!sameValue(target[key], value)) {
    target[key] = value;
    modified = true;
  }
}

function deleteIfPresent(target, key) {
  if (Object.prototype.hasOwnProperty.call(target, key)) {
    delete target[key];
    modified = true;
  }
}


// loon-change: CNFTP terminal empty-body guard v1
if (!$response.body) {
  $done({});
} else {
const isIQY = url.includes("iqiyi.com/");
const isMG = url.includes("mgtv.com/");
const isYK = url.includes("youku.com/");
// loon-change: CNFTP pre-parse supported-route guard v1
const shouldProcess =
  (url.includes("iqiyi.com/") && (
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
  (url.includes("mgtv.com/") && (
    url.includes("/dynamic/v1/channel/index/") ||
    url.includes("/dynamic/v1/channel/vrsList/") ||
    url.includes("/mobile/config?") ||
    url.includes("/mobile/recommend/v2?") ||
    url.includes("/odin/c1/channel/index?") ||
    url.includes("/v1/vod/info?") ||
    url.includes("/v3/module/list?") ||
    url.includes("/v10/video/info?")
  )) ||
  (url.includes("youku.com/") && (
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
        compactInPlace(card.items, (i) => ["29", "31", "34"]?.includes(i?._id));
        // 修复位置
        for (let i = 0; i < card.items.length; i++) {
          setIfDifferent(card.items[i], "show_order", i + 1);
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
        deleteIfPresent(obj.content.resource, i);
      }
    }
  } else if (url.includes("/control/")) {
    // 爱奇艺 首页左上角天气图标
    if (obj?.content?.weather) {
      deleteIfPresent(obj.content, "weather");
    }
  } else if (url.includes("/getMyMenus?")) {
    // 爱奇艺 我的页面
    if (obj?.data?.length > 0) {
      // loon-change: iQIYI personal menus nested stable in-place compaction v1
      compactInPlace(obj.data, (item) => {
        if (["wd_liebiao_2", "wd_liebiao_3", "wd_liebiao_4"]?.includes(item?.statistic?.block)) return false;
        if (item?.menuList?.length > 0) {
          compactInPlace(item.menuList, (entry) => entry?.menuType !== 121);
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
        compactInPlace(card.items, (i) => !["1017", "8196", "4525518866820370"]?.includes(i?._id));
        for (let i = 0; i < card.items.length; i++) {
          setIfDifferent(card.items[i], "show_order", i + 1);
        }
      }
    }
  } else if (url.includes("/mixer?")) {
    // 爱奇艺 开屏广告 播放广告
    if (obj?.errorCode === 0) {
      const items = ["adSlots", "splashLottieFile", "splashUiConfig"];
      for (let i of items) {
        deleteIfPresent(obj, i);
      }
    }
  } else if (url.includes("/search.video.iqiyi.com/")) {
    // 爱奇艺 搜索框填充
    if (obj?.cache_expired_sec) {
      setIfDifferent(obj, "cache_expired_sec", 1);
    }
    if (obj?.data) {
      setIfDifferent(obj, "data", [{query: "搜索内容"}]);
    }
    if (obj?.show_style?.roll_period) {
      setIfDifferent(obj.show_style, "roll_period", 1000);
    }
  } else if (url.includes("/views_category/")) {
    // 爱奇艺 各菜单列表 剧集 电影 综艺 信息流
    if (obj?.base?.statistics?.ad_str) {
      deleteIfPresent(obj.base.statistics, "ad_str");
    }
    if (obj?.cards?.length > 0) {
      // loon-change: iQIYI category nested stable in-place compaction v1
      compactInPlace(obj.cards, (card) => {
        if (card?.blocks?.length > 0) compactInPlace(card.blocks, (item) =>
          !["block_321", "block_415", "block_416"]?.includes(item?.block_name) &&
          item?.buttons?.[0]?.id !== "ad"
        );
        return true;
      });
    }
  } else if (url.includes("/views_comment/")) {
    // 爱奇艺 播放页评论区
    if (obj?.cards?.length > 0) {
      // 评论资源位 无alias_name字段的为广告
      compactInPlace(obj.cards, 
        (i) => i.hasOwnProperty("alias_name") && !["comment_resource_card", "comment_resource_convention_card"]?.includes(i?.alias_name)
      );
    }
  } else if (url.includes("/views_home/")) {
    // 爱奇艺 信息流样式1
    if (obj?.base?.statistics?.ad_str) {
      deleteIfPresent(obj.base.statistics, "ad_str");
    }
    if (obj?.cards?.length > 0) {
      // loon-change: iQIYI home cards allocation-free traversal v1
      compactInPlace(obj.cards, (card) => {
        // ad_mobile_flow信息流广告 ad_trueview信息流广告 focus顶部横版广告 qy_home_vip_opr_banner会员营销banner
        if (["ad_mobile_flow", "ad_trueview", "focus", "qy_home_vip_opr_banner"]?.includes(card?.alias_name)) return false;
        if (card?.top_banner?.l_blocks?.length > 0) {
          // 模块右边文字按钮
          for (let item of card.top_banner.l_blocks) {
            if (item?.buttons?.length > 0) {
              // 移除按钮 娱乐资源
              deleteIfPresent(item, "buttons");
            }
          }
        }
        return true;
      });
    }
  } else if (url.includes("/views_plt/")) {
    // 爱奇艺 播放详情页组件
    if (obj?.kv_pair) {
      // activity_tab活动标签页 cloud_cinema云影院卡片 vip_fixed_card会员优惠购买卡片
      const items = ["activity_tab", "cloud_cinema", "vip_fixed_card"];
      for (let i of items) {
        deleteIfPresent(obj.kv_pair, i);
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
    // 爱奇艺 搜索结果列表
    if (obj?.cards?.length > 0) {
      // loon-change: iQIYI search nested stable in-place compaction v1
      compactInPlace(obj.cards, (card) => {
        if (["ad_mobile_flow","hot_query_bottom","hot_query_search_top_ad","search_com_related_query","search_intent_detail_onesearch","search_mid_text_ad","search_onebox_v2","search_small_card_ad","search_topbanner_text","search_vip_banner"]?.includes(card?.strategy_com_id)) return false;
        if (card?.blocks?.length > 0) compactInPlace(card.blocks, (item) =>
          item.hasOwnProperty("block_name") ||
          (item.hasOwnProperty("block_type") && ![861,959]?.includes(item?.block_type))
        );
        return true;
      });
    }
  } else if (url.includes("/waterfall/")) {
    // 爱奇艺 信息流样式2
    if (obj?.base?.statistics?.ad_str) {
      deleteIfPresent(obj.base.statistics, "ad_str");
    }
    if (obj?.cards?.length > 0) {
      // loon-change: iQIYI waterfall nested stable in-place compaction v1
      compactInPlace(obj.cards, (card) => {
        if (card.hasOwnProperty("block_class")) return false;
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, (item) => !item.hasOwnProperty("block_class"));
        }
        return true;
      });
    }
  }
} else if (isMG) {
  if (url.includes("/dynamic/v1/channel/index/")) {
    // 芒果 首页信息流
    if (obj?.adInfo) {
      deleteIfPresent(obj, "adInfo");
    }
    if (obj?.data?.length > 0) {
      // loon-change: Mango dynamic channel nested stable in-place compaction v1
      compactInPlace(obj.data, (item) => {
        if (["842","2237","5418"]?.includes(item?.moduleEntityId)) return false;
        if (item?.moduleEntityId === "91" && item?.DSLList?.length > 0) {
          compactInPlace(item.DSLList, (list) => {
            if (list?.data?.items?.length > 0) compactInPlace(list.data.items, (entry) =>
              entry?.id !== 0 && !["热门","推荐"]?.includes(entry?.cornerTitle)
            );
            return true;
          });
        }
        return true;
      });
    }
    if (obj?.moduleIDS?.length > 0) {
      compactInPlace(obj.moduleIDS, (i) => !["842", "2237", "5418"]?.includes(i?.moduleEntityId));
    }
  } else if (url.includes("/dynamic/v1/channel/vrsList/")) {
    // 芒果 顶部tab
    if (obj?.data?.length > 0) {
      // loon-change: Mango vrsList stable in-place compaction v1
      compactInPlace(obj.data, (item) =>
        !(item?.vclassId > 100033 && item?.vclassId !== 100160)
      );
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
        setIfDifferent(obj.data, i, "0");
      }
    }
    if (obj?.data?.XmFsLvlCatAddr) {
      setIfDifferent(obj.data, "XmFsLvlCatAddr", "");
    }
  } else if (url.includes("/mobile/recommend/v2?")) {
    // 芒果 搜索框填充词
    if (obj?.data?.default) {
      setIfDifferent(obj.data, "default", {0: ["搜索内容"]});
    }
    if (obj?.data?.recommend) {
      setIfDifferent(obj.data, "recommend", []);
    }
    if (obj?.data?.interval) {
      setIfDifferent(obj.data, "interval", 1000);
    }
  } else if (url.includes("/odin/c1/channel/index?")) {
    // 芒果 首页信息流
    if (obj?.data?.length > 0) {
      // loon-change: Mango odin channel stable in-place compaction v1
      compactInPlace(obj.data, (item) => item?.moduleType !== "childslideicon");
    }
  } else if (url.includes("/v1/vod/info?")) {
    // 芒果 播放页详情页组件
    if (obj?.data?.config?.ad) {
      // 播放广告
      setIfDifferent(obj.data.config.ad, "wmShowTime", 0);
    }
    if (obj?.data?.config?.videoRcMod) {
      // 播放弹窗
      setIfDifferent(obj.data.config.videoRcMod, "toastStatus", 0);
      setIfDifferent(obj.data.config.videoRcMod, "toastTime", 0);
    }
    if (obj?.data?.tabs?.length > 0) {
      // 播放标签页 1视频 2讨论
      compactInPlace(obj.data.tabs, (i) => ["1", "2"]?.includes(i?.type));
    }
    if (obj?.data?.template?.modules?.length > 0) {
      // 播放页组件
      // 101简介 102点赞评论收藏 201正片列表 205会员衍生模块 206音频有声剧
      // 202精彩短片 203精选特辑 301热门内容 601周边大放送 701通栏广告 702大风车浮层广告
      // loon-change: Mango player modules stable in-place compaction v1
      compactInPlace(obj.data.template.modules, (item) => {
        if ([202, 203, 301, 601, 701, 702]?.includes(item?.dataType)) return false;
        if (item?.clipInfo?.rcInfo) {
          // 播放界面推荐语
          deleteIfPresent(item.clipInfo, "rcInfo");
        }
        return true;
      });
    }
    if (obj?.data?.template?.theme) {
      // 播放页主题皮肤
      deleteIfPresent(obj.data.template, "theme");
    }
  } else if (url.includes("/v3/module/list?")) {
    // 芒果 我的页面组件
    if (obj?.data?.list?.length > 0) {
      // loon-change: Mango personal center nested stable in-place compaction v1
      compactInPlace(obj.data.list, (item) => {
        if ([3, 5, 6, 8]?.includes(item?.moduleType)) return false;
        if (item?.moduleType === 2 && item?.title === "用户信息模块" && item?.data?.length > 0) {
          compactInPlace(item.data, (entry) =>
            !["领取芒果卡权益", "签到赢积分"]?.includes(entry?.title)
          );
        } else if (item?.moduleType === 7 && item?.title === "我的服务" && item?.data?.length > 0) {
          compactInPlace(item.data, (entry) =>
            !["功能实验室", "芒果壁纸", "我的音乐"]?.includes(entry?.title)
          );
        }
        return true;
      });
    }
  } else if (url.includes("/v10/video/info?")) {
    // 芒果 播放详情页组件
    if (obj?.data?.categoryList?.length > 0) {
      // 1正片 2花絮片段 6设备信息 7未知 8看了还会看 9精华打包 10未知 14vip
      // 15未知 17周边大放送 18未知 20出品人 22未知 30未知 31系列推荐
      // 35音乐fm入口 36为你推荐 37音乐fm入口
      compactInPlace(obj.data.categoryList, (i) => ![2, 8, 9, 14, 17]?.includes(i?.dataType));
    }
  }
} else if (isYK) {
  if (url.includes("/collect-api/get_push_interval_config_wx?")) {
    // 优酷 热剧弹窗
    if (obj?.data) {
      const items = ["tipContent", "tipContentNew"];
      for (let i of items) {
        deleteIfPresent(obj.data, i);
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
            ["detail", "planet"]?.includes(i?.code)
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
                setIfDifferent(node0, "nodes", []);
              }
            } else if (node0?.typeName === "FEED_DRAWER_PAGINATION") {
              // 播放页推荐信息流
              if (node0?.nodes) {
                setIfDifferent(node0, "nodes", []);
              }
            }
          }
        } else {
          setIfDifferent(objData, "nodes", []);
        }
      }
    }
  } else if (url.includes("columbus.home.feed/")) {
    // 优酷 首页信息流
    if (obj?.data?.["2019061000"]?.data) {
      const objData = obj.data["2019061000"].data;
      const rootNodes = objData?.nodes;
      const rootNodesLength = rootNodes?.length || 0;
      if (rootNodesLength > 0) {
        // loon-change: Youku home.feed callback-free route v1
        compactYoukuHomeFeed(rootNodes, rootNodesLength);
      }
    }
  } else if (url.includes("columbus.home.query/")) {
    // 优酷 各菜单列表 剧集 电影 综艺 信息流
    if (obj?.data?.["2019061000"]?.data) {
      const objData = obj.data["2019061000"].data;
      const homeData = objData?.data;
      const indexPositionResult = homeData?.indexPositionResult;
      if (indexPositionResult?.length > 0) {
        // 首页 第零层级 二楼
        setIfDifferent(homeData, "indexPositionResult", []);
      }
      const rootNodes = objData?.nodes;
      const rootNodesLength = rootNodes?.length || 0;
      if (rootNodesLength > 0) {
        // loon-change: Youku home.query callback-free route v1
        compactYoukuHomeQuery(rootNodes, "root", rootNodesLength);
      }
    }
  } else if (url.includes("columbus.uc.query/")) {
    // 优酷 我的页面组件
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.nodes?.length > 0) {
        let objNodes = objData.nodes[0];
        if (objNodes?.nodes?.length > 0) {
          // loon-change: Youku personal center nested stable in-place compaction v1
          compactInPlace(objNodes.nodes, (item) => {
            if ([32133, 32775, 22570, 35942, 36014, 38466]?.includes(item?.id)) return false;
            if (item?.id === 28912 && item?.nodes?.length > 0) {
              compactInPlace(item.nodes, (ii) => ii?.id !== 110429);
            } else if (item?.id === 36015 && item?.nodes?.length > 0) {
              const node0 = item.nodes[0];
              if (node0?.nodes?.length > 0) {
                compactInPlace(node0.nodes, (ii) =>
                  [683367, 683368, 683372, 683502]?.includes(ii?.id)
                );
              }
            }
            return true;
          });
        }
      }
    }
  } else if (url.includes("columbus.ycp.query/")) {
    // 优酷 播放页评论区
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.nodes?.length > 0) {
        let objNodes = objData.nodes[0];
        if (objNodes?.nodes?.length > 0) {
          // loon-change: Youku comment nested stable in-place compaction v1
          compactInPlace(objNodes.nodes, (item) => {
            if ((item?.id === 23242 || item?.id === 23243) && item?.nodes?.length > 0) {
              if (item.id === 23242) {
                compactInPlace(item.nodes, (entry) =>
                  entry?.typeName !== "COMPONENT_YCP_NOTICE" && entry?.id !== 113941
                );
              } else {
                compactInPlace(item.nodes, (entry) => entry?.id !== -1000);
              }
            }
            return true;
          });
        }
      }
    }
  } else if (url.includes("haidai.lantern.appconfig.get/")) {
    // 优酷 底部tab
    if (obj?.data?.model?.configInfo?.bottomNavigate) {
      let bottom = obj.data.model.configInfo.bottomNavigate;
      if (bottom?.data?.bottomTabList?.length > 0) {
        // HOME首页 DONGTAI短视频 SEARCH淘好片 VIP_MEMBER会员 NEW_UCENTER我的
        compactInPlace(bottom.data.bottomTabList, (i) =>
          ["HOME", "NEW_UCENTER", "VIP_MEMBER"]?.includes(i?.type)
        );
        // 修复位置
        for (let i = 0; i < bottom.data.bottomTabList.length; i++) {
          setIfDifferent(bottom.data.bottomTabList[i], "menuIndex", i + 1);
        }
      }
    }
  } else if (url.includes("huluwa.dispatcher.youthmode.config2/")) {
    // 优酷 青少年模式弹窗
    if (obj?.data?.result) {
      setIfDifferent(obj.data, "result", {});
    }
  } else if (url.includes("play.ups.appinfo.get/")) {
    // 优酷 开屏广告 播放广告
    if (obj?.data?.data) {
      const items = ["ad", "watermark", "ykad"];
      for (let i of items) {
        deleteIfPresent(obj.data.data, i);
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

$done(modified ? {body: JSON.stringify(obj)} : {});
}
}
