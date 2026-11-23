#!/usr/bin/env python3
"""Fail-closed local performance optimization for the shared CNFTP response script."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REMOTE_URL = "https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/cnftp.js"
LOCAL_URL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/cnftp/cnftp.js"
EXPECTED_TRIGGER_COUNT = 10
SOURCE_MARKER = "// loon-change: Youku home.query in-place compaction v1"

FILTER_MARKER = "// loon-change: CNFTP response filter in-place compaction v1"
FILTER_ASSIGNMENT_RE = re.compile(
    r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\1\.filter\s*\("
)


def compact_response_filters(source: str) -> str:
    """Replace response-array filter copies with stable in-place compaction."""
    if FILTER_MARKER in source:
        if source.count(FILTER_MARKER) != 1 or FILTER_ASSIGNMENT_RE.search(source):
            raise ValueError("CNFTP in-place filter marker/structure drift")
        return source
    matches = list(FILTER_ASSIGNMENT_RE.finditer(source))
    if not matches:
        return source
    if len(matches) != 11:
        raise ValueError(
            "CNFTP response filter inventory changed: expected 11, got %d"
            % len(matches)
        )
    for match in reversed(matches):
        target = match.group(1)
        source = source[:match.start()] + "compactInPlace(%s, " % target + source[match.end():]
    if FILTER_ASSIGNMENT_RE.search(source):
        raise ValueError("CNFTP allocating response filter remains after compaction")
    return FILTER_MARKER + "\n" + source



EMPTY_BODY_MARKER = "// loon-change: CNFTP terminal empty-body guard v1"


def ensure_terminal_empty_body_guard(source: str) -> str:
    """Prevent the response parser from running after an empty-body completion."""
    wrapped = (
        EMPTY_BODY_MARKER
        + "\nif (!$response.body) {\n  $done({});\n} else {"
    )
    if EMPTY_BODY_MARKER in source:
        if source.count(EMPTY_BODY_MARKER) != 1 or wrapped not in source:
            raise ValueError("CNFTP terminal empty-body guard marker/structure drift")
        return source
    guard = "if (!$response.body) $done({});"
    if source.count(guard) == 0:
        return source
    if source.count(guard) != 1:
        raise ValueError("CNFTP empty-body guard count changed; refusing terminal guard")
    final = "$done({body: JSON.stringify(obj)});"
    if source.count(final) != 1 or not source.rstrip().endswith(final):
        raise ValueError("CNFTP final response completion changed; refusing terminal guard")
    source = source.replace(guard, wrapped, 1)
    return source.rstrip() + "\n}\n"



HELPER = """function compactInPlace(items, keep) {
  let write = 0;
  const length = items.length;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  items.length = write;
  return items;
}

"""

HOME_FEED_BRANCH = """  } else if (url.includes("columbus.home.feed/")) {
    // 优酷 首页信息流
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.nodes?.length > 0) {
        // Reuse response arrays and compact only the nested ad-card groups.
        compactInPlace(objData.nodes, (node1) => {
          if (node1?.typeName === "PHONE_FEED_CARD_GROUP" &&
              node1?.nodes?.length > 0) {
            compactInPlace(node1.nodes, (node2) =>
              node2?.typeName !== "PHONE_FEED_CARD_S_AD" &&
              node2?.typeName !== "PHONE_H_UC_AD"
            );
          }
          return true;
        });
      }
    }
"""
HOME_QUERY_BRANCH = """  } else if (url.includes("columbus.home.query/")) {
    // 优酷 各菜单列表 剧集 电影 综艺 信息流
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.data?.indexPositionResult?.length > 0) {
        // 首页 第零层级 二楼
        objData.data.indexPositionResult = [];
      }
      if (objData?.nodes?.length > 0) {
        // Stable in-place compaction avoids four generations of nested filtered-copy arrays.
        compactInPlace(objData.nodes, (node1) => {
          if (node1?.data?.nodeKey === "CHILD" ||
              node1?.data?.nodeKey === "COMIC2" ||
              node1?.data?.nodeKey === "20230929GREATWORKMFK") {
            return false;
          }
          if (node1?.data?.indexPositionResult?.length > 0) {
            // 剧集 电影 二楼
            node1.data.indexPositionResult = [];
          }
          if (node1?.data?.refreshImg) {
            // 电影 综艺 纪录片 下拉刷新的背景图片
            delete node1.data.refreshImg;
          }
          if (node1?.nodes?.length > 0) {
            compactInPlace(node1.nodes, (node2) => {
              if (node2?.data?.crmSale) {
                // 季卡会员横幅
                delete node2.data.crmSale;
              }
              if (node2?.typeName === "UC广告抽屉" || node2?.typeName === "橱窗广告") {
                // 横版独占广告
                return false;
              }
              if (node2?.id === 31476 && node2?.data?.keywords?.length > 0) {
                // 正在热播滚动热词
                delete node2.data.keywords;
              }
              if (node2?.id === 35505 || node2?.id === 37335) {
                // 优惠购会员横幅、首页二楼
                return false;
              }
              if (node2?.nodes?.length > 0) {
                compactInPlace(node2.nodes, (node3) => {
                  if (
                    node3?.typeName === "PHONE_FEED_CARD_B_AD" ||
                    node3?.typeName === "PHONE_FEED_CARD_S_AD" ||
                    node3?.typeName === "PHONE_H_UC_AD" ||
                    node3?.typeName === "PHONE_IMG_A" ||
                    node3?.typeName === "PHONE_YK_AD_BANNER"
                  ) {
                    return false;
                  }
                  // 首页轮播广告
                  if (node3?.id === 272768) return false;
                  if (node3?.nodes?.length > 0) {
                    compactInPlace(node3.nodes, (node4) => {
                      if (node4?.typeName === "PHONE_FEED_CARD_S_AD") return false;
                      if (node4?.data?.hasOwnProperty("ad")) return false;
                      return true;
                    });
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
"""
MANGO_VRSLIST_OLD = """      let newItems = [];
      for (let item of obj.data) {
        if (item?.vclassId > 100033 && item?.vclassId !== 100160) {
          // 100033热门 100043短剧 100160会员频道精选 100308短视频
          continue;
        } else {
          newItems.push(item);
        }
      }
      obj.data = newItems;"""
MANGO_VRSLIST_NEW = """      // loon-change: Mango vrsList stable in-place compaction v1
      compactInPlace(obj.data, (item) =>
        !(item?.vclassId > 100033 && item?.vclassId !== 100160)
      );"""
MANGO_ODIN_OLD = """      let newItems = [];
      for (let item of obj.data) {
        if (item?.moduleType === "childslideicon") {
          // 横版按钮
          continue;
        } else {
          newItems.push(item);
        }
      }
      obj.data = newItems;"""
MANGO_ODIN_NEW = """      // loon-change: Mango odin channel stable in-place compaction v1
      compactInPlace(obj.data, (item) => item?.moduleType !== "childslideicon");"""
IQIYI_WATERFALL_OLD = """      let newCards = [];
      for (let card of obj.cards) {
        if (card.hasOwnProperty("block_class")) {
          // 有block_class字段的为广告
          continue;
        } else {
          if (card?.blocks?.length > 0) {
            let newItems = [];
            for (let item of card.blocks) {
              if (item.hasOwnProperty("block_class")) {
                // 有block_class字段的为广告
                continue;
              } else {
                newItems.push(item);
              }
            }
            card.blocks = newItems;
            newCards.push(card);
          } else {
            newCards.push(card);
          }
        }
      }
      obj.cards = newCards;"""
IQIYI_WATERFALL_NEW = """      // loon-change: iQIYI waterfall nested stable in-place compaction v1
      compactInPlace(obj.cards, (card) => {
        if (card.hasOwnProperty("block_class")) return false;
        if (card?.blocks?.length > 0) {
          compactInPlace(card.blocks, (item) => !item.hasOwnProperty("block_class"));
        }
        return true;
      });"""


def ensure_iqiyi_mango_compaction(source: str) -> str:
    """Reapply audited response-array compactions after upstream refresh."""
    replacements = (
        ("          let newNodes = [];\n          for (let item of objNodes.nodes) {\n            if (item?.id === 32133) {\n              // 横幅视频广告\n              continue;\n            } else if (item?.id === 32775) {\n              // 个人中心二楼\n              continue;\n            } else if (item?.id === 22570) {\n              // 横版轮播图\n              continue;\n            } else if (item?.id === 28912) {\n              // 我的下载 收藏 购买 场景\n              if (item?.nodes?.length > 0) {\n                let newII = [];\n                for (let ii of item.nodes) {\n                  if (ii?.id === 110429) {\n                    // 免费兑换VIP\n                    continue;\n                  }\n                  newII.push(ii);\n                }\n                item.nodes = newII;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 35942) {\n              // 我的专属推荐\n              continue;\n            } else if (item?.id === 36014) {\n              // 业务区 星光币 优酷购 数字藏品\n              continue;\n            } else if (item?.id === 36015) {\n              // 功能区 卡卷包 商城 设置\n              if (item?.nodes?.length > 0) {\n                let node0 = item.nodes[0];\n                if (node0?.nodes?.length > 0) {\n                  let newII = [];\n                  for (let ii of node0.nodes) {\n                    // 683364卡卷包 683359个性商城 683501TV助手 683367设置\n                    // 683368我的客服 683502意见反馈 683366有奖调研 683372更多\n                    if ([683367, 683368, 683372, 683502]?.includes(ii?.id)) {\n                      newII.push(ii);\n                    }\n                  }\n                  node0.nodes = newII;\n                  newNodes.push(item);\n                } else {\n                  newNodes.push(item);\n                }\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 38466) {\n              // 横幅广告\n              continue;\n            } else {\n              newNodes.push(item);\n            }\n          }\n          objNodes.nodes = newNodes;", "          // loon-change: Youku personal center nested stable in-place compaction v1\n          compactInPlace(objNodes.nodes, (item) => {\n            if ([32133, 32775, 22570, 35942, 36014, 38466]?.includes(item?.id)) return false;\n            if (item?.id === 28912 && item?.nodes?.length > 0) {\n              compactInPlace(item.nodes, (ii) => ii?.id !== 110429);\n            } else if (item?.id === 36015 && item?.nodes?.length > 0) {\n              const node0 = item.nodes[0];\n              if (node0?.nodes?.length > 0) {\n                compactInPlace(node0.nodes, (ii) =>\n                  [683367, 683368, 683372, 683502]?.includes(ii?.id)\n                );\n              }\n            }\n            return true;\n          });", "Youku personal", '// 优酷 我的页面组件'),
        ("          let newNodes = [];\n          for (let item of objNodes.nodes) {\n            if (item?.id === 23242) {\n              // 评论区顶部\n              if (item?.nodes?.length > 0) {\n                let newItems = [];\n                for (let i of item.nodes) {\n                  if (i?.typeName === \"COMPONENT_YCP_NOTICE\") {\n                    // 评论区守则 轮播通告\n                    continue;\n                  } else if (i?.id === 113941) {\n                    // 明星空降评论区\n                    continue;\n                  } else {\n                    newItems.push(i);\n                  }\n                }\n                item.nodes = newItems;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 23243) {\n              // 评论区留言\n              if (item?.nodes?.length > 0) {\n                let newItems = [];\n                for (let i of item.nodes) {\n                  if (i?.id === -1000) {\n                    // 评论区广告\n                    continue;\n                  } else {\n                    newItems.push(i);\n                  }\n                }\n                item.nodes = newItems;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else {\n              newNodes.push(item);\n            }\n          }\n          objNodes.nodes = newNodes;", "          // loon-change: Youku comment nested stable in-place compaction v1\n          compactInPlace(objNodes.nodes, (item) => {\n            if ((item?.id === 23242 || item?.id === 23243) && item?.nodes?.length > 0) {\n              if (item.id === 23242) {\n                compactInPlace(item.nodes, (entry) =>\n                  entry?.typeName !== \"COMPONENT_YCP_NOTICE\" && entry?.id !== 113941\n                );\n              } else {\n                compactInPlace(item.nodes, (entry) => entry?.id !== -1000);\n              }\n            }\n            return true;\n          });", "Youku comments", '// 优酷 播放页评论区'),
        ("      let newList = [];\n      for (let item of obj.data.list) {\n        // 1顶部模块 扫一扫 消息 搜索 设置\n        // 2用户信息模块 芒果卡 个人信息\n        // 3推荐位模块 购买会员 会员周边\n        // 4用户内容模块 播放记录 追更\n        // 5大芒计划 创作中心 热门作品 征稿活动\n        // 5我的小芒 电商 订单\n        // 6banner图模块 广告轮播图\n        // 7我的服务 客服 皮肤 意见反馈\n        // 8运营商专区 芒果卡 免流\n        // 8兴趣中心 抓娃娃\n        // 8推荐功能 钱包 福袋 芒果公益\n        if ([3, 5, 6, 8]?.includes(item?.moduleType)) {\n          // 推广模块\n          continue;\n        } else if (item?.moduleType === 2 && item?.title === \"用户信息模块\") {\n          // 用户信息\n          if (item?.data?.length > 0) {\n            let newItems = [];\n            for (let i of item.data) {\n              if ([\"领取芒果卡权益\", \"签到赢积分\"]?.includes(i?.title)) {\n                continue;\n              } else {\n                newItems.push(i);\n              }\n            }\n            item.data = newItems;\n            newList.push(item);\n          } else {\n            newList.push(item);\n          }\n        } else if (item?.moduleType === 7 && item?.title === \"我的服务\") {\n          // 我的服务\n          if (item?.data?.length > 0) {\n            let newItems = [];\n            for (let i of item.data) {\n              if ([\"功能实验室\", \"芒果壁纸\", \"我的音乐\"]?.includes(i?.title)) {\n                continue;\n              } else {\n                newItems.push(i);\n              }\n            }\n            item.data = newItems;\n            newList.push(item);\n          } else {\n            newList.push(item);\n          }\n        } else {\n          newList.push(item);\n        }\n      }\n      obj.data.list = newList;", "      // loon-change: Mango personal center nested stable in-place compaction v1\n      compactInPlace(obj.data.list, (item) => {\n        if ([3, 5, 6, 8]?.includes(item?.moduleType)) return false;\n        if (item?.moduleType === 2 && item?.title === \"用户信息模块\" && item?.data?.length > 0) {\n          compactInPlace(item.data, (entry) =>\n            ![\"领取芒果卡权益\", \"签到赢积分\"]?.includes(entry?.title)\n          );\n        } else if (item?.moduleType === 7 && item?.title === \"我的服务\" && item?.data?.length > 0) {\n          compactInPlace(item.data, (entry) =>\n            ![\"功能实验室\", \"芒果壁纸\", \"我的音乐\"]?.includes(entry?.title)\n          );\n        }\n        return true;\n      });", "Mango personal", '// 芒果 我的页面组件'),
        ("      let newMenus = [];\n      for (let item of obj.data) {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) {\n          // 精简列表\n          continue;\n        } else {\n          if (item?.menuList?.length > 0) {\n            let newLists = [];\n            for (let i of item.menuList) {\n              if (i?.menuType === 121) {\n                // 121有奖限时问卷\n                continue;\n              } else {\n                newLists.push(i);\n              }\n            }\n            item.menuList = newLists;\n            newMenus.push(item);\n          } else {\n            newMenus.push(item);\n          }\n        }\n      }\n      obj.data = newMenus;", "      // loon-change: iQIYI personal menus nested stable in-place compaction v1\n      compactInPlace(obj.data, (item) => {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) return false;\n        if (item?.menuList?.length > 0) {\n          compactInPlace(item.menuList, (entry) => entry?.menuType !== 121);\n        }\n        return true;\n      });", "iQIYI personal menus", 'url.includes("/getMyMenus?")'),
        ("      let newCards = [];\n      for (let card of obj.cards) {\n        // ad_mobile_flow信息流广告 ad_trueview信息流广告 focus顶部横版广告 qy_home_vip_opr_banner会员营销banner\n        if ([\"ad_mobile_flow\", \"ad_trueview\", \"focus\", \"qy_home_vip_opr_banner\"]?.includes(card?.alias_name)) {\n          continue;\n        } else {\n          if (card?.top_banner?.l_blocks?.length > 0) {\n            // 模块右边文字按钮\n            for (let item of card.top_banner.l_blocks) {\n              if (item?.buttons?.length > 0) {\n                // 移除按钮 娱乐资源\n                delete item.buttons;\n              }\n            }\n            newCards.push(card);\n          } else {\n            newCards.push(card);\n          }\n        }\n      }\n      obj.cards = newCards;", "      // loon-change: iQIYI home cards allocation-free traversal v1\n      compactInPlace(obj.cards, (card) => {\n        // ad_mobile_flow信息流广告 ad_trueview信息流广告 focus顶部横版广告 qy_home_vip_opr_banner会员营销banner\n        if ([\"ad_mobile_flow\", \"ad_trueview\", \"focus\", \"qy_home_vip_opr_banner\"]?.includes(card?.alias_name)) return false;\n        if (card?.top_banner?.l_blocks?.length > 0) {\n          // 模块右边文字按钮\n          for (let item of card.top_banner.l_blocks) {\n            if (item?.buttons?.length > 0) {\n              // 移除按钮 娱乐资源\n              delete item.buttons;\n            }\n          }\n        }\n        return true;\n      });", "iQIYI home cards", 'url.includes("/views_home/")'),
        ("      let newMods = [];\n      for (let item of obj.data.template.modules) {\n        if ([202, 203, 301, 601, 701, 702]?.includes(item?.dataType)) {\n          continue;\n        } else {\n          if (item?.clipInfo?.rcInfo) {\n            // 播放界面推荐语\n            delete item.clipInfo.rcInfo;\n          }\n          newMods.push(item);\n        }\n      }\n      obj.data.template.modules = newMods;", "      // loon-change: Mango player modules stable in-place compaction v1\n      compactInPlace(obj.data.template.modules, (item) => {\n        if ([202, 203, 301, 601, 701, 702]?.includes(item?.dataType)) return false;\n        if (item?.clipInfo?.rcInfo) {\n          // 播放界面推荐语\n          delete item.clipInfo.rcInfo;\n        }\n        return true;\n      });", "Mango player modules", 'url.includes("/v1/vod/info?")'),
        (MANGO_VRSLIST_OLD, MANGO_VRSLIST_NEW, "Mango vrsList", 'url.includes("/dynamic/v1/channel/vrsList/")'),
        (MANGO_ODIN_OLD, MANGO_ODIN_NEW, "Mango odin", 'url.includes("/odin/c1/channel/index?")'),
        (IQIYI_WATERFALL_OLD, IQIYI_WATERFALL_NEW, "iQIYI waterfall", 'url.includes("/waterfall/")'),
        ("      let newCards = [];\n      for (let card of obj.cards) {\n        if (card?.blocks?.length > 0) {\n          let newItems = [];\n          for (let item of card.blocks) {\n            // block_321顶部轮播广告 block_415横版独占广告标题 block_416 横版独占视频广告\n            if ([\"block_321\", \"block_415\", \"block_416\"]?.includes(item?.block_name)) {\n              continue;\n            } else if (item?.buttons?.[0]?.id === \"ad\") {\n              continue;\n            } else {\n              newItems.push(item);\n            }\n          }\n          card.blocks = newItems;\n          newCards.push(card);\n        } else {\n          newCards.push(card);\n        }\n      }\n      obj.cards = newCards;", "      // loon-change: iQIYI category nested stable in-place compaction v1\n      compactInPlace(obj.cards, (card) => {\n        if (card?.blocks?.length > 0) compactInPlace(card.blocks, (item) =>\n          ![\"block_321\", \"block_415\", \"block_416\"]?.includes(item?.block_name) &&\n          item?.buttons?.[0]?.id !== \"ad\"\n        );\n        return true;\n      });", "iQIYI category", 'url.includes("/views_category/")'),
        ("      let newCards = [];\n      for (let card of obj.cards) {\n        if (\n          [\n            \"ad_mobile_flow\", // 信息流广告\n            \"hot_query_bottom\", // 底部图标\n            \"hot_query_search_top_ad\", //顶部广告\n            \"search_com_related_query\", // 相关搜索\n            \"search_intent_detail_onesearch\", // 为你推荐信息流\n            \"search_mid_text_ad\", // 底部广告\n            \"search_onebox_v2\", // 搜索界面 赢年卡\n            \"search_small_card_ad\", // 搜索短视频小图广告\n            \"search_topbanner_text\", // 为你推荐标题\n            \"search_vip_banner\" // vip营销\n          ]?.includes(card?.strategy_com_id)\n        ) {\n          continue;\n        } else {\n          // 相关内容推荐 相关短视频\n          if (card?.blocks?.length > 0) {\n            let newBlocks = [];\n            for (let i of card.blocks) {\n              if (i.hasOwnProperty(\"block_name\")) {\n                newBlocks.push(i);\n              } else if (i.hasOwnProperty(\"block_type\")) {\n                if (![861, 959]?.includes(i?.block_type)) {\n                  // 861搜索页精确搜索时 第一个自动播放的内容\n                  // 959广告\n                  newBlocks.push(i);\n                }\n              }\n            }\n            card.blocks = newBlocks;\n            newCards.push(card);\n          } else {\n            newCards.push(card);\n          }\n        }\n      }\n      obj.cards = newCards;", "      // loon-change: iQIYI search nested stable in-place compaction v1\n      compactInPlace(obj.cards, (card) => {\n        if ([\"ad_mobile_flow\",\"hot_query_bottom\",\"hot_query_search_top_ad\",\"search_com_related_query\",\"search_intent_detail_onesearch\",\"search_mid_text_ad\",\"search_onebox_v2\",\"search_small_card_ad\",\"search_topbanner_text\",\"search_vip_banner\"]?.includes(card?.strategy_com_id)) return false;\n        if (card?.blocks?.length > 0) compactInPlace(card.blocks, (item) =>\n          item.hasOwnProperty(\"block_name\") ||\n          (item.hasOwnProperty(\"block_type\") && ![861,959]?.includes(item?.block_type))\n        );\n        return true;\n      });", "iQIYI search", 'url.includes("/views_search/")'),
        ("      let newItems = [];\n      for (let item of obj.data) {\n        // 908热剧轮播\n        if (item?.moduleEntityId === \"91\") {\n          // 首页正在追模块\n          if (item?.DSLList?.length > 0) {\n            let newLists = [];\n            for (let i of item.DSLList) {\n              if (i?.data?.items?.length > 0) {\n                let newII = [];\n                for (let ii of i.data.items) {\n                  if (ii?.id === 0) {\n                    // 正在追模块 艺人周边 小芒\n                    continue;\n                  } else if ([\"热门\", \"推荐\"]?.includes(ii?.cornerTitle)) {\n                    continue;\n                  } else {\n                    newII.push(ii);\n                  }\n                }\n                i.data.items = newII;\n                newLists.push(i);\n              } else {\n                newLists.push(i);\n              }\n            }\n            item.DSLList = newLists;\n            newItems.push(item);\n          } else {\n            newItems.push(item);\n          }\n        } else if ([\"842\", \"2237\", \"5418\"]?.includes(item?.moduleEntityId)) {\n          // 842会员首月特惠 2237横版购物tab 5418横版推广图片\n          continue;\n        } else {\n          newItems.push(item);\n        }\n      }\n      obj.data = newItems;", "      // loon-change: Mango dynamic channel nested stable in-place compaction v1\n      compactInPlace(obj.data, (item) => {\n        if ([\"842\",\"2237\",\"5418\"]?.includes(item?.moduleEntityId)) return false;\n        if (item?.moduleEntityId === \"91\" && item?.DSLList?.length > 0) {\n          compactInPlace(item.DSLList, (list) => {\n            if (list?.data?.items?.length > 0) compactInPlace(list.data.items, (entry) =>\n              entry?.id !== 0 && ![\"热门\",\"推荐\"]?.includes(entry?.cornerTitle)\n            );\n            return true;\n          });\n        }\n        return true;\n      });", "Mango dynamic", 'url.includes("/dynamic/v1/channel/index/")'),
    )
    for old, new, label, route_anchor in replacements:
        marker = new.splitlines()[0]
        if marker in source:
            if source.count(marker) != 1 or old in source:
                raise ValueError(label + " compaction marker/structure drift")
            continue
        if source.count(old) != 1:
            if route_anchor not in source:
                continue
            raise ValueError(label + " upstream structure changed; refusing an unreviewed optimization")
        source = source.replace(old, new, 1)
    return source



SUPPORTED_ROUTE_MARKER = "// loon-change: CNFTP pre-parse supported-route guard v1"
SUPPORTED_ROUTE_GUARD = """// loon-change: CNFTP pre-parse supported-route guard v1
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
} else {"""
 
def ensure_supported_route_guard(source: str) -> str:
    """Skip JSON parsing for host responses outside the CNFTP script's handled routes."""
    if SUPPORTED_ROUTE_MARKER in source:
        if source.count(SUPPORTED_ROUTE_MARKER) != 1 or source.count(SUPPORTED_ROUTE_GUARD) != 1:
            raise ValueError("CNFTP supported-route guard marker/structure drift")
        if source.count("let obj = JSON.parse($response.body);") != 1:
            raise ValueError("CNFTP supported-route parse anchor drift")
        if not source.rstrip().endswith("$done({body: JSON.stringify(obj)});\n}\n}"):
            raise ValueError("CNFTP supported-route terminal structure drift")
        return source
    parse_line = "let obj = JSON.parse($response.body);"
    if "const shouldProcess =" in source or "if (!shouldProcess)" in source:
        raise ValueError("CNFTP supported-route guard marker/structure drift")
    parse_count = source.count(parse_line)
    if parse_count == 0:
        return source
    if parse_count != 1:
        raise ValueError("CNFTP response parse anchor changed; refusing pre-parse guard")
    if source.count('const isIQY = url.includes("iqiyi.com/");') != 1:
        raise ValueError("CNFTP domain dispatch anchor changed; refusing pre-parse guard")
    if not source.rstrip().endswith("$done({body: JSON.stringify(obj)});\n}"):
        raise ValueError("CNFTP terminal response structure changed; refusing pre-parse guard")
    source = source.replace(parse_line, SUPPORTED_ROUTE_GUARD + "\n" + parse_line, 1)
    source = source.rstrip() + "\n}\n"
    return source



LAZY_SERIALIZATION_MARKER = "// loon-change: CNFTP lazy response serialization v1"


def ensure_lazy_serialization(source: str) -> str:
    """Serialize only when a reviewed CNFTP mutation actually changes the response."""
    final = "$done({body: JSON.stringify(obj)});"
    lazy_final = "$done(modified ? {body: JSON.stringify(obj)} : {});"
    if LAZY_SERIALIZATION_MARKER in source:
        if (source.count(LAZY_SERIALIZATION_MARKER) != 1
                or source.count("let modified = false;") != 1
                or source.count(lazy_final) != 1
                or "function setIfDifferent(" not in source
                or "function deleteIfPresent(" not in source):
            raise ValueError("CNFTP lazy serialization marker/structure drift")
        return source
    if "let modified = false;" in source or lazy_final in source:
        raise ValueError("CNFTP lazy serialization marker/structure drift")
    if source.count("const url = $request.url;") != 1:
        raise ValueError("CNFTP URL initialization changed; refusing lazy serialization")
    if source.count("function compactInPlace(items, keep) {") != 1:
        raise ValueError("CNFTP compaction helper changed; refusing lazy serialization")
    if source.count("  items.length = write;\n  return items;") != 1:
        raise ValueError("CNFTP compaction mutation anchor changed; refusing lazy serialization")
    parse_count = source.count("let obj = JSON.parse($response.body);")
    final_count = source.count(final)
    if parse_count == 0 and final_count == 0:
        return source
    if parse_count != 1 or final_count != 1:
        raise ValueError("CNFTP response parse/serialize anchors changed; refusing lazy serialization")

    source = source.replace("const url = $request.url;",
                            "const url = $request.url;\n\nlet modified = false;", 1)
    source = source.replace(
        "  items.length = write;\n  return items;",
        "  if (write !== length) {\n    items.length = write;\n    modified = true;\n  }\n  return items;",
        1,
    )
    helper = """\n\n""" + LAZY_SERIALIZATION_MARKER + """\nfunction setIfDifferent(target, key, value) {
  if (target[key] !== value) {
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
"""
    compact_end = "  return items;\n}\n"
    if source.count(compact_end) != 1:
        raise ValueError("CNFTP compaction helper insertion anchor changed")
    source = source.replace(compact_end, compact_end + helper, 1)

    parse_line = "let obj = JSON.parse($response.body);"
    start, finish = source.index(parse_line), source.index(final)
    body = source[start:finish]
    body, deleted = re.subn(
        r"^([ \t]*)delete\s+(.+)\.([A-Za-z_$][\w$]*);$",
        lambda m: m.group(1) + "deleteIfPresent(" + m.group(2) + ', "' + m.group(3) + ');',
        body, flags=re.MULTILINE,
    )
    body, deleted_index = re.subn(
        r"^([ \t]*)delete\s+(.+)\[([^\\]\n]+)\];$",
        lambda m: m.group(1) + "deleteIfPresent(" + m.group(2) + ", " + m.group(3) + ");",
        body, flags=re.MULTILINE,
    )
    body, assigned = re.subn(
        r"^([ \t]*)([A-Za-z_$][\w$]*(?:(?:\.[A-Za-z_$][\w$]*)|(?:\[[^\\]\n]+\]))*)\.([A-Za-z_$][\w$]*)\s*=\s*(.*);$",
        lambda m: m.group(1) + "setIfDifferent(" + m.group(2) + ', "' + m.group(3) + '", ' + m.group(4) + ");",
        body, flags=re.MULTILINE,
    )
    body, assigned_index = re.subn(
        r"^([ \t]*)([A-Za-z_$][\w$]*(?:(?:\.[A-Za-z_$][\w$]*)|(?:\[[^\\]\n]+\]))*)\[([^\\]\n]+)\]\s*=\s*(.*);$",
        lambda m: m.group(1) + "setIfDifferent(" + m.group(2) + ", " + m.group(3) + ", " + m.group(4) + ");",
        body, flags=re.MULTILINE,
    )
    if deleted + deleted_index + assigned + assigned_index == 0:
        raise ValueError("CNFTP mutation inventory unexpectedly empty")
    if re.search(r"^[ \t]*delete\s+", body, re.MULTILINE):
        raise ValueError("CNFTP untracked delete remains; refusing lazy serialization")
    source = source[:start] + body + source[finish:]
    source = source.replace(final, lazy_final, 1)
    return source



def optimize_source(source: str, upstream_commit: str | None = None) -> str:
    """Replace Youku home.query's nested filtered-copy arrays with stable in-place compaction."""
    if SOURCE_MARKER in source:
        if not upstream_commit:
            return ensure_lazy_serialization(compact_response_filters(ensure_supported_route_guard(ensure_terminal_empty_body_guard(ensure_iqiyi_mango_compaction(source)))))
        if not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
            raise ValueError("invalid Wool Scripts upstream commit")
        source = re.sub(r"^// loon-change:.*\n", "", source, count=1)
        source = SOURCE_MARKER + "; upstream fmz200/wool_scripts@" + upstream_commit + "\n" + source
        return ensure_lazy_serialization(compact_response_filters(ensure_supported_route_guard(ensure_terminal_empty_body_guard(ensure_iqiyi_mango_compaction(source)))))

    feed_start = '  } else if (url.includes("columbus.home.feed/")) {'
    feed_end = '  } else if (url.includes("columbus.home.query/")) {'
    if source.count(feed_start) != 1 or source.count(feed_end) != 1:
        raise ValueError("CNFTP Youku home.feed branch changed; refusing an unreviewed optimization")
    feed_begin, feed_finish = source.index(feed_start), source.index(feed_end)
    feed_branch = source[feed_begin:feed_finish]
    feed_required = ("let newNodes1 = [];", "let newNode2 = [];",
                     'node2?.typeName === "PHONE_FEED_CARD_S_AD"',
                     'node2?.typeName === "PHONE_H_UC_AD"')
    if any(token not in feed_branch for token in feed_required):
        raise ValueError("CNFTP Youku home.feed structure changed; refusing an unreviewed optimization")
    source = source[:feed_begin] + HOME_FEED_BRANCH + source[feed_finish:]

    start = '  } else if (url.includes("columbus.home.query/")) {'
    end = '  } else if (url.includes("columbus.uc.query/")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNFTP Youku home.query branch changed; refusing an unreviewed optimization")
    begin, finish = source.index(start), source.index(end)
    branch = source[begin:finish]
    required = ("let newNodes1 = [];", "let newNode2 = [];", "let newNode3 = [];", "let newNode4 = [];", "node3.id === 272768")
    if any(token not in branch for token in required):
        raise ValueError("CNFTP Youku nested-list structure changed; refusing an unreviewed optimization")
    source = source[:begin] + HOME_QUERY_BRANCH + source[finish:]
    url_line = "const url = $request.url;"
    if source.count(url_line) != 1:
        raise ValueError("CNFTP URL initialization changed; refusing helper insertion")
    source = source.replace(url_line, url_line + "\n\n" + HELPER, 1)
    if upstream_commit:
        if not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
            raise ValueError("invalid Wool Scripts upstream commit")
    else:
        upstream_commit = "unrecorded"
    result = SOURCE_MARKER + "; upstream fmz200/wool_scripts@" + upstream_commit + "\n// loon-change: Youku home.feed in-place compaction v1\n" + source
    return ensure_lazy_serialization(compact_response_filters(ensure_supported_route_guard(ensure_terminal_empty_body_guard(ensure_iqiyi_mango_compaction(result)))))


def rewrite_plugin(plugin: str) -> str:
    """Use the local optimized copy for exactly the ten reviewed active CNFTP triggers."""
    lines, section = [], ""
    remote_count = local_count = 0
    for line in plugin.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            lines.append(line)
            continue
        if section == "Script" and REMOTE_URL in line:
            remote_count += 1
            line = line.replace(REMOTE_URL, LOCAL_URL)
        elif section == "Script" and LOCAL_URL in line:
            local_count += 1
        lines.append(line)
    if remote_count == 0 and local_count == 0:
        # The supplemental CNFTP handler is absent from the base-only feed.
        return plugin
    if remote_count == EXPECTED_TRIGGER_COUNT and local_count == 0:
        return "\n".join(lines) + ("\n" if plugin.endswith("\n") else "")
    if remote_count == 0 and local_count == EXPECTED_TRIGGER_COUNT:
        return plugin
    raise ValueError(
        "CNFTP trigger inventory changed; expected exactly %d upstream or local references, got remote=%d local=%d"
        % (EXPECTED_TRIGGER_COUNT, remote_count, local_count)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="upstream cnftp.js input")
    parser.add_argument("--output", help="optimized local script output")
    parser.add_argument("--upstream-commit", help="full Wool Scripts commit SHA")
    parser.add_argument("--plugin", help="plugin to rewrite to the local optimized script")
    args = parser.parse_args()
    if args.source:
        if not args.output:
            parser.error("--source requires --output")
        source = Path(args.source).read_text(encoding="utf-8-sig")
        result = optimize_source(source, args.upstream_commit)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized CNFTP Youku home.feed and home.query in place; upstream=%s" % (args.upstream_commit or "unrecorded"))
    if args.plugin:
        path = Path(args.plugin)
        result = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(result, encoding="utf-8")
        print("Migrated %d CNFTP response triggers to the local optimized script" % EXPECTED_TRIGGER_COUNT)
    if not args.source and not args.plugin:
        parser.error("provide --source or --plugin")


if __name__ == "__main__":
    main()
