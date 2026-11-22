// loon-change: CNTV response compaction optimization v6; upstream zirawell/R-Store@a4f3b10d6038d77ae3e1ff68bd19a49071ebabd3
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

const url = $request.url;
if (!$response.body) {
  $done({});
} else {
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
        compactInPlace(card.items, (i) => ["29", "31", "34"]?.includes(i?._id));
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
        if (["wd_liebiao_2", "wd_liebiao_3", "wd_liebiao_4"]?.includes(item?.statistic?.block)) {
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
        compactInPlace(card.items, (i) => !["1017", "8196", "4525518866820370"]?.includes(i?._id));
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
            !["block_321", "block_415", "block_416"]?.includes(item?.block_name) &&
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
              !["comment_resource_card", "comment_resource_convention_card"]?.includes(i?.alias_name)
      );
    }
  } else if (url.includes("/views_home/")) { 
    // 爱奇艺首页信息流：原地移除广告卡片。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, card => {
        if (["ad_mobile_flow", "ad_trueview", "focus", "qy_home_vip_opr_banner"]?.includes(card?.alias_name)) return false;
        if (card?.top_banner?.l_blocks?.length > 0) {
          for (let i = 0, blocks = card.top_banner.l_blocks; i < blocks.length; i++) {
            if (blocks[i]?.buttons?.length > 0) delete blocks[i].buttons;
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
        if ([
          "ad_mobile_flow", "hot_query_bottom", "hot_query_search_top_ad",
          "search_com_related_query", "search_intent_detail_onesearch",
          "search_mid_text_ad", "search_onebox_v2", "search_small_card_ad",
          "search_topbanner_text", "search_vip_banner"
        ]?.includes(card?.strategy_com_id)) return false;
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, item =>
            item.hasOwnProperty("block_name") ||
            (item.hasOwnProperty("block_type") && ![861, 959]?.includes(item?.block_type))
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
    // 芒果 首页信息流
    if (obj?.adInfo) {
      delete obj.adInfo;
    }
    if (obj?.data?.length > 0) {
      let newItems = [];
      for (let item of obj.data) {
        // 908热剧轮播
        if (item?.moduleEntityId === "91") {
          // 首页正在追模块
          if (item?.DSLList?.length > 0) {
            let newLists = [];
            for (let i of item.DSLList) {
              if (i?.data?.items?.length > 0) {
                let newII = [];
                for (let ii of i.data.items) {
                  if (ii?.id === 0) {
                    // 正在追模块 艺人周边 小芒
                    continue;
                  } else if (["热门", "推荐"]?.includes(ii?.cornerTitle)) {
                    continue;
                  } else {
                    newII.push(ii);
                  }
                }
                i.data.items = newII;
                newLists.push(i);
              } else {
                newLists.push(i);
              }
            }
            item.DSLList = newLists;
            newItems.push(item);
          } else {
            newItems.push(item);
          }
        } else if (["842", "2237", "5418"]?.includes(item?.moduleEntityId)) {
          // 842会员首月特惠 2237横版购物tab 5418横版推广图片
          continue;
        } else {
          newItems.push(item);
        }
      }
      obj.data = newItems;
    }
    if (obj?.moduleIDS?.length > 0) {
      compactInPlace(obj.moduleIDS, (i) => !["842", "2237", "5418"]?.includes(i?.moduleEntityId));
    }
  } else if (url.includes("/channel/vrsList/")) {
    // 芒果 顶部tab
    if (obj?.data?.length > 0) {
      let newItems = [];
      for (let item of obj.data) {
        if (item?.vclassId > 100033 && item?.vclassId !== 100160) {
          // 100033热门 100043短剧 100160会员频道精选 100308短视频
          continue;
        } else {
          newItems.push(item);
        }
      }
      obj.data = newItems;
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
      let newItems = [];
      for (let item of obj.data) {
        if (item?.moduleType === "childslideicon") {
          // 横版按钮
          continue;
        } else {
          newItems.push(item);
        }
      }
      obj.data = newItems;
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
      compactInPlace(obj.data.tabs, (i) => ["1", "2"]?.includes(i?.type));
    }
    if (obj?.data?.template?.modules?.length > 0) {
      // 播放页组件
      // 101简介 102点赞评论收藏 201正片列表 205会员衍生模块 206音频有声剧
      // 202精彩短片 203精选特辑 301热门内容 601周边大放送 701通栏广告 702大风车浮层广告
      let newMods = [];
      for (let item of obj.data.template.modules) {
        if ([202, 203, 301, 601, 701, 702]?.includes(item?.dataType)) {
          continue;
        } else {
          if (item?.clipInfo?.rcInfo) {
            // 播放界面推荐语
            delete item.clipInfo.rcInfo;
          }
          newMods.push(item);
        }
      }
      obj.data.template.modules = newMods;
    }
    if (obj?.data?.template?.theme) {
      // 播放页主题皮肤
      delete obj.data.template.theme;
    }
  } else if (url.includes("/module/list?")) {
    // 芒果 我的页面组件
    if (obj?.data?.list?.length > 0) {
      let newList = [];
      for (let item of obj.data.list) {
        // 1顶部模块 扫一扫 消息 搜索 设置
        // 2用户信息模块 芒果卡 个人信息
        // 3推荐位模块 购买会员 会员周边
        // 4用户内容模块 播放记录 追更
        // 5大芒计划 创作中心 热门作品 征稿活动
        // 5我的小芒 电商 订单
        // 6banner图模块 广告轮播图
        // 7我的服务 客服 皮肤 意见反馈
        // 8运营商专区 芒果卡 免流
        // 8兴趣中心 抓娃娃
        // 8推荐功能 钱包 福袋 芒果公益
        if ([3, 5, 6, 8]?.includes(item?.moduleType)) {
          // 推广模块
          continue;
        } else if (item?.moduleType === 2 && item?.title === "用户信息模块") {
          // 用户信息
          if (item?.data?.length > 0) {
            let newItems = [];
            for (let i of item.data) {
              if (["领取芒果卡权益", "签到赢积分"]?.includes(i?.title)) {
                continue;
              } else {
                newItems.push(i);
              }
            }
            item.data = newItems;
            newList.push(item);
          } else {
            newList.push(item);
          }
        } else if (item?.moduleType === 7 && item?.title === "我的服务") {
          // 我的服务
          if (item?.data?.length > 0) {
            let newItems = [];
            for (let i of item.data) {
              if (["功能实验室", "芒果壁纸", "我的音乐"]?.includes(i?.title)) {
                continue;
              } else {
                newItems.push(i);
              }
            }
            item.data = newItems;
            newList.push(item);
          } else {
            newList.push(item);
          }
        } else {
          newList.push(item);
        }
      }
      obj.data.list = newList;
    }
  } else if (url.includes("/video/info?")) {
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
    // CNTV Youku home.query nested-list compaction: reuse all four response arrays.
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.data?.indexPositionResult?.length > 0) objData.data.indexPositionResult = [];
      if (objData?.nodes?.length > 0) {
        compactInPlace(objData.nodes, item => {
          if (["CHILD", "COMIC2", "20230929GREATWORKMFK"]?.includes(item?.data?.nodeKey)) return false;
          if (item?.data?.indexPositionResult?.length > 0) item.data.indexPositionResult = [];
          if (item?.data?.refreshImg) delete item.data.refreshImg;
          if (item?.nodes?.length > 0) {
            compactInPlace(item.nodes, i => {
              if (i?.data?.crmSale) delete i.data.crmSale;
              if (["UC广告抽屉", "橱窗广告"]?.includes(i?.typeName)) return false;
              if (i?.id === 31476) {
                if (i?.data?.keywords?.length > 0) delete i.data.keywords;
                return true;
              }
              if (i?.id === 35505 || i?.id === 37335) return false;
              if (i?.nodes?.length > 0) {
                compactInPlace(i.nodes, ii => {
                  if (["PHONE_FEED_CARD_B_AD", "PHONE_FEED_CARD_S_AD", "PHONE_H_UC_AD", "PHONE_IMG_A", "PHONE_YK_AD_BANNER"]?.includes(ii?.typeName)) return false;
                  if (ii?.nodes?.length > 0) {
                    compactInPlace(ii.nodes, iii =>
                      iii?.typeName !== "PHONE_FEED_CARD_S_AD" &&
                      !iii?.data?.hasOwnProperty("ad")
                    );
                  }
                  return true;
                });
              }
              return true;
            });
          }
          return true;
        });
      }
    }
  // loon-change: CNTV Youku home.query nested in-place compaction v1\n  } else if (url.includes("columbus.uc.query/")) {
    // 优酷 我的页面组件
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.nodes?.length > 0) {
        let objNodes = objData.nodes[0];
        if (objNodes?.nodes?.length > 0) {
          let newNodes = [];
          for (let item of objNodes.nodes) {
            if (item?.id === 32133) {
              // 横幅视频广告
              continue;
            } else if (item?.id === 32775) {
              // 个人中心二楼
              continue;
            } else if (item?.id === 22570) {
              // 横版轮播图
              continue;
            } else if (item?.id === 28912) {
              // 我的下载 收藏 购买 场景
              if (item?.nodes?.length > 0) {
                let newII = [];
                for (let ii of item.nodes) {
                  if (ii?.id === 110429) {
                    // 免费兑换VIP
                    continue;
                  }
                  newII.push(ii);
                }
                item.nodes = newII;
                newNodes.push(item);
              } else {
                newNodes.push(item);
              }
            } else if (item?.id === 35942) {
              // 我的专属推荐
              continue;
            } else if (item?.id === 36014) {
              // 业务区 星光币 优酷购 数字藏品
              continue;
            } else if (item?.id === 36015) {
              // 功能区 卡卷包 商城 设置
              if (item?.nodes?.length > 0) {
                let node0 = item.nodes[0];
                if (node0?.nodes?.length > 0) {
                  let newII = [];
                  for (let ii of node0.nodes) {
                    // 683364卡卷包 683359个性商城 683501TV助手 683367设置
                    // 683368我的客服 683502意见反馈 683366有奖调研 683372更多
                    if ([683367, 683368, 683372, 683502]?.includes(ii?.id)) {
                      newII.push(ii);
                    }
                  }
                  node0.nodes = newII;
                  newNodes.push(item);
                } else {
                  newNodes.push(item);
                }
              } else {
                newNodes.push(item);
              }
            } else if (item?.id === 38466) {
              // 横幅广告
              continue;
            } else {
              newNodes.push(item);
            }
          }
          objNodes.nodes = newNodes;
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
          let newNodes = [];
          for (let item of objNodes.nodes) {
            if (item?.id === 23242) {
              // 评论区顶部
              if (item?.nodes?.length > 0) {
                let newItems = [];
                for (let i of item.nodes) {
                  if (i?.typeName === "COMPONENT_YCP_NOTICE") {
                    // 评论区守则 轮播通告
                    continue;
                  } else if (i?.id === 113941) {
                    // 明星空降评论区
                    continue;
                  } else {
                    newItems.push(i);
                  }
                }
                item.nodes = newItems;
                newNodes.push(item);
              } else {
                newNodes.push(item);
              }
            } else if (item?.id === 23243) {
              // 评论区留言
              if (item?.nodes?.length > 0) {
                let newItems = [];
                for (let i of item.nodes) {
                  if (i?.id === -1000) {
                    // 评论区广告
                    continue;
                  } else {
                    newItems.push(i);
                  }
                }
                item.nodes = newItems;
                newNodes.push(item);
              } else {
                newNodes.push(item);
              }
            } else {
              newNodes.push(item);
            }
          }
          objNodes.nodes = newNodes;
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
