#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize the high-fanout CNTV/iQIYI/MGTV/Youku response script."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/cntv/cntv.js"
LEGACY_MARKERS = (
    "// loon-change: CNTV response compaction optimization v2; upstream zirawell/R-Store@",
    "// loon-change: CNTV response compaction optimization v1; upstream zirawell/R-Store@",
    "// loon-change: CNTV response compaction optimization v3; upstream zirawell/R-Store@",
    "// loon-change: CNTV response compaction optimization v4; upstream zirawell/R-Store@",
    "// loon-change: CNTV response compaction optimization v5; upstream zirawell/R-Store@",
)
MARKER = "// loon-change: CNTV response compaction optimization v6; upstream zirawell/R-Store@"
ROUTE_GUARD_MARKER = "// loon-change: CNTV pre-parse supported-route guard v1"
IQIYI_FEED_MARKER = "// loon-change: CNTV iQIYI feed array compaction v1"
MENUS_MARKER = "// loon-change: CNTV getMyMenus in-place compaction v1"
HELPER = """function compactInPlace(items, keep) {
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
"""
FILTER_ASSIGNMENT = re.compile(
    r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\1\.filter\s*\("
)


def optimize_get_my_menus(source):
    anchor = '  } else if (url.includes("/getMyMenus?")) {'
    end_anchor = '  } else if (url.includes("/home_top_menu?")) {'
    if anchor not in source:
        return source
    if source.count(anchor) != 1 or source.count(end_anchor) != 1:
        raise ValueError("CNTV getMyMenus dispatch inventory changed")
    start = source.index(anchor)
    end = source.index(end_anchor, start)
    branch = source[start:end]
    if MENUS_MARKER in branch:
        if "newMenus" in branch or "newLists" in branch:
            raise ValueError("CNTV getMyMenus marker exists but allocating arrays remain")
        return source
    old_block = "    if (obj?.data?.length > 0) {\n      let newMenus = [];\n      for (let item of obj.data) {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) {\n          // 精简列表\n          continue;\n        } else {\n          if (item?.menuList?.length > 0) {\n            let newLists = [];\n            for (let i of item.menuList) {\n              if (i?.menuType === 121) {\n                // 121有奖限时问卷\n                continue;\n              } else {\n                newLists.push(i);\n              }\n            }\n            item.menuList = newLists;\n            newMenus.push(item);\n          } else {\n            newMenus.push(item);\n          }\n        }\n      }\n      obj.data = newMenus;\n    }"
    new_block = "    if (obj?.data?.length > 0) {\n      compactInPlace(obj.data, item => {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) {\n          // 精简列表\n          return false;\n        }\n        if (item?.menuList?.length > 0) {\n          // 121有奖限时问卷\n          compactInPlace(item.menuList, menu => menu?.menuType !== 121);\n        }\n        return true;\n      });\n    }"
    if source.count(old_block) != 1:
        raise ValueError("CNTV getMyMenus block changed; refusing in-place compaction")
    source = source.replace(old_block, new_block, 1)
    source = source.replace(anchor, anchor + "\n    " + MENUS_MARKER, 1)
    start = source.index(anchor)
    end = source.index(end_anchor, start)
    branch = source[start:end]
    if "newMenus" in branch or "newLists" in branch:
        raise ValueError("CNTV getMyMenus temporary arrays remain")
    return source


ROUTE_GUARD = """// loon-change: CNTV pre-parse supported-route guard v1
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
"""


def optimize_pre_parse_route_guard(source):
    if ROUTE_GUARD_MARKER in source:
        if (
            source.count(ROUTE_GUARD_MARKER) != 1
            or source.count("const shouldProcess =") != 1
            or source.count("if (!shouldProcess)") != 1
        ):
            raise ValueError("CNTV pre-parse route guard marker/structure drift")
        return source
    parse_anchor = "let obj = JSON.parse($response.body);"
    if source.count(parse_anchor) != 1:
        raise ValueError("CNTV JSON.parse anchor changed; refusing route guard")
    source = source.replace(parse_anchor, ROUTE_GUARD + parse_anchor, 1)
    end_anchor = "\n$done({body: JSON.stringify(obj)});\n}\n"
    if source.count(end_anchor) != 1:
        raise ValueError("CNTV response completion anchor changed; refusing route guard")
    source = source.replace(end_anchor, "\n$done({body: JSON.stringify(obj)});\n}\n}\n", 1)
    if source.count(ROUTE_GUARD_MARKER) != 1 or source.count("const shouldProcess =") != 1:
        raise ValueError("CNTV pre-parse route guard insertion failed")
    return source



YOUKU_QUERY_MARKER = "// loon-change: CNTV Youku home.query nested in-place compaction v1"
YOUKU_HOME_QUERY_BRANCH = "  } else if (url.includes(\"columbus.home.query/\")) {\n    // CNTV Youku home.query nested-list compaction: reuse all four response arrays.\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      let objData = obj.data[\"2019061000\"].data;\n      if (objData?.data?.indexPositionResult?.length > 0) objData.data.indexPositionResult = [];\n      if (objData?.nodes?.length > 0) {\n        compactInPlace(objData.nodes, item => {\n          if ([\"CHILD\", \"COMIC2\", \"20230929GREATWORKMFK\"]?.includes(item?.data?.nodeKey)) return false;\n          if (item?.data?.indexPositionResult?.length > 0) item.data.indexPositionResult = [];\n          if (item?.data?.refreshImg) delete item.data.refreshImg;\n          if (item?.nodes?.length > 0) {\n            compactInPlace(item.nodes, i => {\n              if (i?.data?.crmSale) delete i.data.crmSale;\n              if ([\"UC广告抽屉\", \"橱窗广告\"]?.includes(i?.typeName)) return false;\n              if (i?.id === 31476) {\n                if (i?.data?.keywords?.length > 0) delete i.data.keywords;\n                return true;\n              }\n              if (i?.id === 35505 || i?.id === 37335) return false;\n              if (i?.nodes?.length > 0) {\n                compactInPlace(i.nodes, ii => {\n                  if ([\"PHONE_FEED_CARD_B_AD\", \"PHONE_FEED_CARD_S_AD\", \"PHONE_H_UC_AD\", \"PHONE_IMG_A\", \"PHONE_YK_AD_BANNER\"]?.includes(ii?.typeName)) return false;\n                  if (ii?.nodes?.length > 0) {\n                    compactInPlace(ii.nodes, iii =>\n                      iii?.typeName !== \"PHONE_FEED_CARD_S_AD\" &&\n                      !iii?.data?.hasOwnProperty(\"ad\")\n                    );\n                  }\n                  return true;\n                });\n              }\n              return true;\n            });\n          }\n          return true;\n        });\n      }\n    }\n"


YOUKU_HOME_FEED_MARKER = "// loon-change: CNTV Youku home.feed in-place compaction v1"


def optimize_youku_home_feed(source):
    start = '  } else if (url.includes("columbus.home.feed/")) {'
    end = '  } else if (url.includes("columbus.home.query/")) {'
    if YOUKU_HOME_FEED_MARKER in source:
        if source.count(YOUKU_HOME_FEED_MARKER) != 1 or source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("CNTV Youku home.feed marker/structure drift")
        begin, finish = source.index(start), source.index(end, source.index(start))
        branch = source[begin:finish]
        if "newNodes" in branch or "newItems" in branch or ".push(" in branch:
            raise ValueError("CNTV Youku home.feed temporary array allocation remains")
        return source
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV Youku home.feed route anchors changed")
    begin, finish = source.index(start), source.index(end, source.index(start))
    expected = '''  } else if (url.includes("columbus.home.feed/")) {
    // 优酷 首页信息流
    if (obj?.data?.["2019061000"]?.data) {
      let objData = obj.data["2019061000"].data;
      if (objData?.nodes?.length > 0) {
        let newNodes = [];
        for (let item of objData.nodes) {
          if (item?.typeName === "PHONE_FEED_CARD_GROUP") {
            if (item?.nodes?.length > 0) {
              let newItems = [];
              for (let i of item.nodes) {
                if (i?.typeName === "PHONE_FEED_CARD_S_AD") {
                  // 首页 四格小图广告
                  continue;
                } else if (i?.typeName === "PHONE_H_UC_AD") {
                  // 首页 横版独占广告
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
        objData.nodes = newNodes;
      }
    }
'''
    if source[begin:finish] != expected:
        raise ValueError("CNTV Youku home.feed branch changed; refusing in-place compaction")
    optimized = '''  } else if (url.includes("columbus.home.feed/")) {
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
'''
    return source[:begin] + optimized + source[finish:]


def optimize_youku_home_query(source):
    start = '  } else if (url.includes("columbus.home.query/")) {'
    end = '  } else if (url.includes("columbus.uc.query/")) {'
    if YOUKU_QUERY_MARKER in source:
        if source.count(YOUKU_QUERY_MARKER) != 1 or source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("CNTV Youku home.query compaction marker/structure drift")
        begin, finish = source.index(start), source.index(end)
        branch = source[begin:finish]
        if any(token in branch for token in ("let newNodes = []", "let newItems = []", "let newII = []", "let newIII = []")):
            raise ValueError("CNTV Youku home.query temporary nested arrays remain")
        return optimize_youku_home_query_callback_free(source)
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV Youku home.query route anchors changed")
    begin, finish = source.index(start), source.index(end)
    result = source[:begin] + YOUKU_HOME_QUERY_BRANCH + "  " + YOUKU_QUERY_MARKER + "\n" + source[finish:]
    optimized_end = result.index(end, begin)
    branch = result[begin:optimized_end]
    if any(token in branch for token in ("let newNodes = []", "let newItems = []", "let newII = []", "let newIII = []")):
        raise ValueError("CNTV Youku home.query temporary nested arrays remain")
    return optimize_youku_home_query_callback_free(result)



YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER_MARKER = "// loon-change: CNTV Youku home.query callback-free nested compaction v1"
YOUKU_HOME_QUERY_CALLBACK_FREE_ROUTE_MARKER = "// loon-change: CNTV Youku home.query callback-free route v1"

YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER = """// loon-change: CNTV Youku home.query callback-free nested compaction v1
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
}"""

YOUKU_HOME_QUERY_CALLBACK_FREE_BRANCH = """  } else if (url.includes("columbus.home.query/")) {
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
"""


def optimize_youku_home_query_callback_free(source):
    """Replace all four predicate-callback traversals with a fixed-mode indexed walker."""
    start = '  } else if (url.includes("columbus.home.query/")) {'
    end = '  } else if (url.includes("columbus.uc.query/")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV Youku home.query callback-free route boundary drift")
    begin = source.index(start)
    finish = source.index(end, begin + len(start))
    branch = source[begin:finish]

    required_helper = (
        "function compactCntvYoukuHomeQuery(items, mode, knownLength) {",
        'if (mode === "root")',
        'if (mode === "level2")',
        'if (mode === "level3")',
        'if (mode === "level4")',
        "const length = knownLength === undefined ? items.length : knownLength;",
        'compactCntvYoukuHomeQuery(childNodes, "level2", childLength);',
        'compactCntvYoukuHomeQuery(childNodes, "level3", childLength);',
        'compactCntvYoukuHomeQuery(childNodes, "level4", childLength);',
    )
    required_route = (
        YOUKU_HOME_QUERY_CALLBACK_FREE_ROUTE_MARKER,
        "const rootNodes = objData?.nodes;",
        "const rootNodesLength = rootNodes?.length || 0;",
        'compactCntvYoukuHomeQuery(rootNodes, "root", rootNodesLength);',
    )

    if YOUKU_HOME_QUERY_CALLBACK_FREE_ROUTE_MARKER in branch:
        if branch.count(YOUKU_HOME_QUERY_CALLBACK_FREE_ROUTE_MARKER) != 1:
            raise ValueError("CNTV Youku home.query callback-free route marker count drift")
        if source.count(YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER_MARKER) != 1:
            raise ValueError("CNTV Youku home.query callback-free helper marker count drift")
        if any(token not in branch for token in required_route):
            raise ValueError("CNTV Youku home.query callback-free route structure drift")
        if "compactInPlace(" in branch or "=>" in branch:
            raise ValueError("CNTV Youku home.query route still contains predicate callbacks")
        helper_start = source.index(YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER_MARKER)
        helper_end = source.find("\n}\n\n", helper_start)
        if helper_end < 0:
            raise ValueError("CNTV Youku home.query callback-free helper boundary drift")
        helper = source[helper_start:helper_end + 2]
        if any(token not in helper for token in required_helper):
            raise ValueError("CNTV Youku home.query callback-free helper structure drift")
        if "=>" in helper or "compactInPlace(" in helper or ".filter(" in helper or ".map(" in helper or ".forEach(" in helper:
            raise ValueError("CNTV Youku home.query helper retains callback-based traversal")
        return source

    legacy_required = (
        YOUKU_QUERY_MARKER,
        "compactInPlace(objData.nodes, item => {",
        "compactInPlace(item.nodes, i => {",
        "compactInPlace(i.nodes, ii => {",
        "compactInPlace(ii.nodes, iii =>",
        '["CHILD", "COMIC2", "20230929GREATWORKMFK"]?.includes(item?.data?.nodeKey)',
        '["UC广告抽屉", "橱窗广告"]?.includes(i?.typeName)',
        '["PHONE_FEED_CARD_B_AD", "PHONE_FEED_CARD_S_AD", "PHONE_H_UC_AD", "PHONE_IMG_A", "PHONE_YK_AD_BANNER"]?.includes(ii?.typeName)',
        'iii?.typeName !== "PHONE_FEED_CARD_S_AD"',
        'i?.id === 35505 || i?.id === 37335',
    )
    if branch.count("compactInPlace(") != 4 or branch.count("=>") != 4 or any(token not in branch for token in legacy_required):
        raise ValueError("CNTV Youku home.query callback branch drift; refusing unreviewed rewrite")

    if source.count(YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER_MARKER) != 0:
        raise ValueError("CNTV Youku home.query partial helper marker exists without route marker")
    helper_anchor = 'const isIQY = url.includes("iqiyi.com/");'
    if source.count(helper_anchor) != 1:
        raise ValueError("CNTV Youku home.query helper insertion anchor drift")
    source = source.replace(helper_anchor, YOUKU_HOME_QUERY_CALLBACK_FREE_HELPER + "\n\n" + helper_anchor, 1)
    # Inserting the helper changes all offsets below the insertion point.
    begin = source.index(start)
    finish = source.index(end, begin + len(start))
    source = source[:begin] + YOUKU_HOME_QUERY_CALLBACK_FREE_BRANCH + source[finish:]
    return source



YOUKU_PROFILE_MARKER = "// loon-change: CNTV Youku user-center nested in-place compaction v1"
YOUKU_COMMENT_MARKER = "// loon-change: CNTV Youku comment-list nested in-place compaction v1"


def optimize_youku_profile_comment_arrays(source):
    """Remove nested replacement-array allocations from Youku profile and comment responses."""
    specs = (
        {
            "start": '  } else if (url.includes("columbus.uc.query/")) {',
            "end": '  } else if (url.includes("columbus.ycp.query/")) {',
            "marker": YOUKU_PROFILE_MARKER,
            "required": (
                "const userCenterNodes = objNodes?.nodes;",
                "const downloadNodes = item?.nodes;",
                "const settingNodes = firstNode?.nodes;",
                "userCenterNodes.length = userCenterWrite;",
            ),
            "old": "  } else if (url.includes(\"columbus.uc.query/\")) {\n    // 优酷 我的页面组件\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      let objData = obj.data[\"2019061000\"].data;\n      if (objData?.nodes?.length > 0) {\n        let objNodes = objData.nodes[0];\n        if (objNodes?.nodes?.length > 0) {\n          let newNodes = [];\n          for (let item of objNodes.nodes) {\n            if (item?.id === 32133) {\n              // 横幅视频广告\n              continue;\n            } else if (item?.id === 32775) {\n              // 个人中心二楼\n              continue;\n            } else if (item?.id === 22570) {\n              // 横版轮播图\n              continue;\n            } else if (item?.id === 28912) {\n              // 我的下载 收藏 购买 场景\n              if (item?.nodes?.length > 0) {\n                let newII = [];\n                for (let ii of item.nodes) {\n                  if (ii?.id === 110429) {\n                    // 免费兑换VIP\n                    continue;\n                  }\n                  newII.push(ii);\n                }\n                item.nodes = newII;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 35942) {\n              // 我的专属推荐\n              continue;\n            } else if (item?.id === 36014) {\n              // 业务区 星光币 优酷购 数字藏品\n              continue;\n            } else if (item?.id === 36015) {\n              // 功能区 卡卷包 商城 设置\n              if (item?.nodes?.length > 0) {\n                let node0 = item.nodes[0];\n                if (node0?.nodes?.length > 0) {\n                  let newII = [];\n                  for (let ii of node0.nodes) {\n                    // 683364卡卷包 683359个性商城 683501TV助手 683367设置\n                    // 683368我的客服 683502意见反馈 683366有奖调研 683372更多\n                    if ([683367, 683368, 683372, 683502]?.includes(ii?.id)) {\n                      newII.push(ii);\n                    }\n                  }\n                  node0.nodes = newII;\n                  newNodes.push(item);\n                } else {\n                  newNodes.push(item);\n                }\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 38466) {\n              // 横幅广告\n              continue;\n            } else {\n              newNodes.push(item);\n            }\n          }\n          objNodes.nodes = newNodes;\n        }\n      }\n    }\n",
            "new": "  } else if (url.includes(\"columbus.uc.query/\")) {\n    // loon-change: CNTV Youku user-center nested in-place compaction v1\n    // 保留原有 allowlist 和顺序，直接压缩个人中心节点及两层子节点。\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      const objNodes = obj.data[\"2019061000\"].data.nodes?.[0];\n      const userCenterNodes = objNodes?.nodes;\n      const userCenterLength = userCenterNodes?.length || 0;\n      if (userCenterLength > 0) {\n        let userCenterWrite = 0;\n        for (let userCenterRead = 0; userCenterRead < userCenterLength; userCenterRead++) {\n          const item = userCenterNodes[userCenterRead];\n          const itemId = item?.id;\n          if (itemId === 32133 || itemId === 32775 || itemId === 22570 ||\n              itemId === 35942 || itemId === 36014 || itemId === 38466) {\n            continue;\n          }\n          if (itemId === 28912) {\n            // 我的下载 收藏 购买 场景\n            const downloadNodes = item?.nodes;\n            const downloadLength = downloadNodes?.length || 0;\n            if (downloadLength > 0) {\n              let downloadWrite = 0;\n              for (let downloadRead = 0; downloadRead < downloadLength; downloadRead++) {\n                const downloadItem = downloadNodes[downloadRead];\n                if (downloadItem?.id === 110429) continue;\n                if (downloadWrite !== downloadRead) downloadNodes[downloadWrite] = downloadItem;\n                downloadWrite++;\n              }\n              downloadNodes.length = downloadWrite;\n            }\n          } else if (itemId === 36015) {\n            // 功能区 卡卷包 商城 设置\n            const itemNodes = item?.nodes;\n            if (itemNodes?.length > 0) {\n              const firstNode = itemNodes[0];\n              const settingNodes = firstNode?.nodes;\n              const settingLength = settingNodes?.length || 0;\n              if (settingLength > 0) {\n                let settingWrite = 0;\n                for (let settingRead = 0; settingRead < settingLength; settingRead++) {\n                  const settingItem = settingNodes[settingRead];\n                  if (![683367, 683368, 683372, 683502]?.includes(settingItem?.id)) continue;\n                  if (settingWrite !== settingRead) settingNodes[settingWrite] = settingItem;\n                  settingWrite++;\n                }\n                settingNodes.length = settingWrite;\n              }\n            }\n          }\n          if (userCenterWrite !== userCenterRead) userCenterNodes[userCenterWrite] = item;\n          userCenterWrite++;\n        }\n        userCenterNodes.length = userCenterWrite;\n      }\n    }\n  }\n",
        },
        {
            "start": '  } else if (url.includes("columbus.ycp.query/")) {',
            "end": '  } else if (url.includes("haidai.lantern.appconfig.get/")) {',
            "marker": YOUKU_COMMENT_MARKER,
            "required": (
                "const commentNodes = objNodes?.nodes;",
                "const childNodes = item?.nodes;",
                "commentNodes.length = commentWrite;",
            ),
            "old": "  } else if (url.includes(\"columbus.ycp.query/\")) {\n    // 优酷 播放页评论区\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      let objData = obj.data[\"2019061000\"].data;\n      if (objData?.nodes?.length > 0) {\n        let objNodes = objData.nodes[0];\n        if (objNodes?.nodes?.length > 0) {\n          let newNodes = [];\n          for (let item of objNodes.nodes) {\n            if (item?.id === 23242) {\n              // 评论区顶部\n              if (item?.nodes?.length > 0) {\n                let newItems = [];\n                for (let i of item.nodes) {\n                  if (i?.typeName === \"COMPONENT_YCP_NOTICE\") {\n                    // 评论区守则 轮播通告\n                    continue;\n                  } else if (i?.id === 113941) {\n                    // 明星空降评论区\n                    continue;\n                  } else {\n                    newItems.push(i);\n                  }\n                }\n                item.nodes = newItems;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else if (item?.id === 23243) {\n              // 评论区留言\n              if (item?.nodes?.length > 0) {\n                let newItems = [];\n                for (let i of item.nodes) {\n                  if (i?.id === -1000) {\n                    // 评论区广告\n                    continue;\n                  } else {\n                    newItems.push(i);\n                  }\n                }\n                item.nodes = newItems;\n                newNodes.push(item);\n              } else {\n                newNodes.push(item);\n              }\n            } else {\n              newNodes.push(item);\n            }\n          }\n          objNodes.nodes = newNodes;\n        }\n      }\n    }\n",
            "new": "  } else if (url.includes(\"columbus.ycp.query/\")) {\n    // loon-change: CNTV Youku comment-list nested in-place compaction v1\n    // 评论区节点及其子节点原地压缩，保持父子顺序和原有过滤条件。\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      const objNodes = obj.data[\"2019061000\"].data.nodes?.[0];\n      const commentNodes = objNodes?.nodes;\n      const commentLength = commentNodes?.length || 0;\n      if (commentLength > 0) {\n        let commentWrite = 0;\n        for (let commentRead = 0; commentRead < commentLength; commentRead++) {\n          const item = commentNodes[commentRead];\n          const itemId = item?.id;\n          if (itemId === 23242 || itemId === 23243) {\n            const childNodes = item?.nodes;\n            const childLength = childNodes?.length || 0;\n            if (childLength > 0) {\n              let childWrite = 0;\n              for (let childRead = 0; childRead < childLength; childRead++) {\n                const child = childNodes[childRead];\n                const removeNotice = itemId === 23242 &&\n                  (child?.typeName === \"COMPONENT_YCP_NOTICE\" || child?.id === 113941);\n                const removeAd = itemId === 23243 && child?.id === -1000;\n                if (removeNotice || removeAd) continue;\n                if (childWrite !== childRead) childNodes[childWrite] = child;\n                childWrite++;\n              }\n              childNodes.length = childWrite;\n            }\n          }\n          if (commentWrite !== commentRead) commentNodes[commentWrite] = item;\n          commentWrite++;\n        }\n        commentNodes.length = commentWrite;\n      }\n    }\n  }\n",
        },
    )
    for spec in specs:
        start, end, marker = spec["start"], spec["end"], spec["marker"]
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("CNTV Youku profile/comment route anchors changed: " + start)
        begin = source.index(start)
        finish = source.index(end, begin + len(start))
        branch = source[begin:finish]
        if marker in source:
            if source.count(marker) != 1:
                raise ValueError("CNTV Youku profile/comment marker count drift: " + marker)
            if any(token in branch for token in ("newNodes", "newItems", "newII", ".push(")):
                raise ValueError("CNTV Youku profile/comment temporary arrays remain: " + marker)
            if marker not in branch or any(token not in branch for token in spec["required"]):
                raise ValueError("CNTV Youku profile/comment branch structure drift: " + marker)
            continue
        if branch != spec["old"]:
            raise ValueError("CNTV Youku profile/comment source drift; refusing in-place rewrite: " + marker)
        replacement = spec["new"]
        # The next route anchor begins with the closing brace for this branch.
        if not replacement.endswith("  }\n"):
            raise ValueError("CNTV Youku replacement branch boundary changed: " + marker)
        replacement = replacement[:-4]
        source = source[:begin] + replacement + source[finish:]
    return source


def optimize_iqiyi_feed_arrays(source):
    """Compact iQIYI feed/search arrays in place instead of allocating replacement arrays."""
    branches = (
        ('  } else if (url.includes("/views_category/")) {',
         '  } else if (url.includes("/views_comment/")) {',
         ''' 
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
    }'''),
        ('  } else if (url.includes("/views_home/")) {',
         '  } else if (url.includes("/views_plt/")) {',
         ''' 
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
    }'''),
        ('  } else if (url.includes("/views_search/")) {',
         '  } else if (url.includes("/waterfall/")) {',
         ''' 
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
    }'''),
        ('  } else if (url.includes("/waterfall/")) {',
         '  }\n} else if (isMG) {',
         ''' 
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
    }'''),
    )
    if IQIYI_FEED_MARKER in source:
        if source.count(IQIYI_FEED_MARKER) != 1:
            raise ValueError("CNTV iQIYI feed marker count drift")
        for start, end, _ in branches:
            a, b = source.find(start), source.find(end)
            if a < 0 or b < 0 or any(token in source[a:b] for token in ("newCards", "newItems", "newBlocks")):
                raise ValueError("CNTV iQIYI feed compaction drift")
        return source
    for start, end, body in branches:
        if source.count(start) != 1 or source.count(end) != 1:
            raise ValueError("CNTV iQIYI feed branch inventory changed: " + start)
        a = source.index(start)
        b = source.index(end, a + len(start))
        source = source[:a + len(start)] + body + "\n" + source[b:]
    anchor = '  } else if (url.includes("/views_category/")) {'
    source = source.replace(anchor, anchor + "\n    " + IQIYI_FEED_MARKER, 1)
    return source



IQIYI_HOME_FEED_CALLBACK_FREE_HELPER = "// loon-change: CNTV iQIYI home-feed callback-free compaction v1\nfunction compactCntvIqiyiHomeCards(cards, knownLength) {\n  const length = knownLength === undefined ? cards.length : knownLength;\n  let write = 0;\n\n  for (let read = 0; read < length; read++) {\n    const card = cards[read];\n    const aliasName = card?.alias_name;\n    if (aliasName === \"ad_mobile_flow\" ||\n        aliasName === \"ad_trueview\" ||\n        aliasName === \"focus\" ||\n        aliasName === \"qy_home_vip_opr_banner\") continue;\n\n    const topBanner = card?.top_banner;\n    const blocks = topBanner?.l_blocks;\n    const blocksLength = blocks?.length || 0;\n    for (let blockIndex = 0; blockIndex < blocksLength; blockIndex++) {\n      const block = blocks[blockIndex];\n      const buttons = block?.buttons;\n      if (buttons?.length > 0) delete block.buttons;\n    }\n\n    if (write !== read) cards[write] = card;\n    write++;\n  }\n\n  if (write !== length) cards.length = write;\n  return cards;\n}"
IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER = "// loon-change: CNTV iQIYI home-feed callback-free compaction v1"
IQIYI_HOME_FEED_CALLBACK_FREE_ROUTE_MARKER = "// loon-change: CNTV iQIYI home-feed callback-free route v1"

def optimize_iqiyi_home_feed_callback_free(source):
    """Remove per-card predicate callbacks from the active iQIYI home-feed route."""
    start = '  } else if (url.includes("/views_home/")) {'
    end = '  } else if (url.includes("/views_plt/")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV iQIYI home-feed route anchors changed")
    begin = source.index(start)
    finish = source.index(end, begin + len(start))
    branch = source[begin:finish]

    if IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER in source or IQIYI_HOME_FEED_CALLBACK_FREE_ROUTE_MARKER in source:
        required = (
            IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER,
            IQIYI_HOME_FEED_CALLBACK_FREE_ROUTE_MARKER,
            "function compactCntvIqiyiHomeCards(cards, knownLength)",
            "const homeCards = obj?.cards;",
            "const homeCardsLength = homeCards?.length || 0;",
            "compactCntvIqiyiHomeCards(homeCards, homeCardsLength);",
            "if (write !== length) cards.length = write;",
        )
        helper_start = source.find(IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER)
        helper_end = source.find("\n}\n", helper_start)
        helper_block = source[helper_start:helper_end + 2] if helper_start >= 0 and helper_end >= 0 else ""
        if (source.count(IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER) != 1 or
                source.count(IQIYI_HOME_FEED_CALLBACK_FREE_ROUTE_MARKER) != 1 or
                any(token not in source for token in required) or
                not helper_block or "=>" in helper_block or ".includes(" in helper_block or
                "compactInPlace(obj.cards, card =>" in branch or
                "CNTV_STATIC_FILTER_06.includes(card?.alias_name)" in branch):
            raise ValueError("CNTV iQIYI home-feed callback-free marker/structure drift")
        stale_filter = 'const CNTV_STATIC_FILTER_06 = ["ad_mobile_flow", "ad_trueview", "focus", "qy_home_vip_opr_banner"];\n'
        if source.count(stale_filter) == 1 and source.count("CNTV_STATIC_FILTER_06") == 1:
            source = source.replace(stale_filter, "", 1)
        return source

    old_block = """    // 爱奇艺首页信息流：原地移除广告卡片。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    if (obj?.cards?.length > 0) {
      compactInPlace(obj.cards, card => {
        if (CNTV_STATIC_FILTER_06.includes(card?.alias_name)) return false;
        if (card?.top_banner?.l_blocks?.length > 0) {
          for (let i = 0, blocks = card.top_banner.l_blocks; i < blocks.length; i++) {
            if (blocks[i]?.buttons?.length > 0) delete blocks[i].buttons;
          }
        }
        return true;
      });
    }"""
    if branch.count(old_block) != 1:
        raise ValueError("CNTV iQIYI home-feed predicate block changed; refusing rewrite")
    replacement = """    // 爱奇艺首页信息流：回调-free 稳定原地压缩广告卡片。
    if (obj?.base?.statistics?.ad_str) delete obj.base.statistics.ad_str;
    const homeCards = obj?.cards;
    const homeCardsLength = homeCards?.length || 0;
    if (homeCardsLength > 0) {
      compactCntvIqiyiHomeCards(homeCards, homeCardsLength);
    }
    // loon-change: CNTV iQIYI home-feed callback-free route v1"""
    branch = branch.replace(old_block, replacement, 1)
    source = source[:begin] + branch + source[finish:]

    helper_anchor = 'const isIQY = url.includes("iqiyi.com/");'
    if source.count(helper_anchor) != 1:
        raise ValueError("CNTV iQIYI home-feed helper insertion anchor changed")
    source = source.replace(helper_anchor, IQIYI_HOME_FEED_CALLBACK_FREE_HELPER + "\n\n" + helper_anchor, 1)
    if source.count(IQIYI_HOME_FEED_CALLBACK_FREE_HELPER_MARKER) != 1 or source.count(IQIYI_HOME_FEED_CALLBACK_FREE_ROUTE_MARKER) != 1:
        raise ValueError("CNTV iQIYI home-feed callback-free insertion failed")
    stale_filter = 'const CNTV_STATIC_FILTER_06 = ["ad_mobile_flow", "ad_trueview", "focus", "qy_home_vip_opr_banner"];\n'
    if source.count(stale_filter) == 1 and source.count("CNTV_STATIC_FILTER_06") == 1:
        source = source.replace(stale_filter, "", 1)
    return source


MGTV_ARRAY_MARKER = "// loon-change: CNTV MangoTV response array compaction v1"


def optimize_mgtv_arrays(source):
    """Remove allocating array rebuilds from high-volume MangoTV feeds and page payloads."""
    def replace_once(old, new, label):
        nonlocal source
        count = source.count(old)
        if count != 1:
            raise ValueError("CNTV MangoTV " + label + " block changed: expected 1, got %d" % count)
        source = source.replace(old, new, 1)

    if MGTV_ARRAY_MARKER in source:
        if source.count(MGTV_ARRAY_MARKER) != 1:
            raise ValueError("CNTV MangoTV marker count drift")
        for token in ("newItems", "newLists", "newII", "newMods", "newList"):
            # Only inspect the five optimized route branches, not unrelated source code.
            pass
        return source

    old_home = """    if (obj?.data?.length > 0) {
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
    }"""
    new_home = """    if (obj?.data?.length > 0) {
      compactInPlace(obj.data, item => {
        // 908热剧轮播
        if (item?.moduleEntityId === "91" && item?.DSLList?.length > 0) {
          compactInPlace(item.DSLList, entry => {
            if (entry?.data?.items?.length > 0) {
              compactInPlace(entry.data.items, video =>
                video?.id !== 0 && !["热门", "推荐"]?.includes(video?.cornerTitle)
              );
            }
            return true;
          });
        }
        // 842会员首月特惠 2237横版购物tab 5418横版推广图片
        return !["842", "2237", "5418"]?.includes(item?.moduleEntityId);
      });
    }"""
    replace_once(old_home, new_home, "home feed")

    old_tabs = """    if (obj?.data?.length > 0) {
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
    }"""
    new_tabs = """    if (obj?.data?.length > 0) {
      // 100033热门 100043短剧 100160会员频道精选 100308短视频
      compactInPlace(obj.data, item => !(item?.vclassId > 100033 && item?.vclassId !== 100160));
    }"""
    replace_once(old_tabs, new_tabs, "top tabs")

    old_index = """    if (obj?.data?.length > 0) {
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
    }"""
    new_index = """    if (obj?.data?.length > 0) {
      // 横版按钮
      compactInPlace(obj.data, item => item?.moduleType !== "childslideicon");
    }"""
    replace_once(old_index, new_index, "channel index")

    old_modules = """      let newMods = [];
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
      obj.data.template.modules = newMods;"""
    new_modules = """      compactInPlace(obj.data.template.modules, item => {
        if ([202, 203, 301, 601, 701, 702]?.includes(item?.dataType)) return false;
        if (item?.clipInfo?.rcInfo) {
          // 播放界面推荐语
          delete item.clipInfo.rcInfo;
        }
        return true;
      });"""
    replace_once(old_modules, new_modules, "vod modules")

    old_list = """      let newList = [];
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
      obj.data.list = newList;"""
    new_list = """      compactInPlace(obj.data.list, item => {
        // 3推荐位模块 5大芒计划/我的小芒 6banner图模块 8运营商/兴趣/推荐功能
        if ([3, 5, 6, 8]?.includes(item?.moduleType)) return false;
        if (item?.moduleType === 2 && item?.title === "用户信息模块" && item?.data?.length > 0) {
          compactInPlace(item.data, entry => !["领取芒果卡权益", "签到赢积分"]?.includes(entry?.title));
        } else if (item?.moduleType === 7 && item?.title === "我的服务" && item?.data?.length > 0) {
          compactInPlace(item.data, entry => !["功能实验室", "芒果壁纸", "我的音乐"]?.includes(entry?.title));
        }
        return true;
      });"""
    replace_once(old_list, new_list, "my page modules")

    # Place the marker once at the start of the first optimized MangoTV route.
    anchor = '  if (url.includes("/dynamic/v") && url.includes("/channel/index/")) {'
    if source.count(anchor) != 1:
        raise ValueError("CNTV MangoTV dispatch anchor changed")
    source = source.replace(anchor, anchor + "\n    " + MGTV_ARRAY_MARKER, 1)
    # Fail closed if allocating rebuilds remain in any optimized route.
    ranges = (
        ('  if (url.includes("/dynamic/v") && url.includes("/channel/index/")) {', '  } else if (url.includes("/channel/vrsList/")) {'),
        ('  } else if (url.includes("/channel/vrsList/")) {', '  } else if (url.includes("/mobile/config?")) {'),
        ('  } else if (url.includes("/channel/index?") && url.includes("/odin/c")) {', '  } else if (url.includes("/vod/info?")) {'),
        ('  } else if (url.includes("/vod/info?")) {', '  } else if (url.includes("/module/list?")) {'),
        ('  } else if (url.includes("/module/list?")) {', '  } else if (url.includes("/video/info?")) {'),
    )
    for start, end in ranges:
        a, b = source.find(start), source.find(end)
        if a < 0 or b < 0 or any(token in source[a:b] for token in ("newItems", "newLists", "newII", "newMods", "newList", ".push(")):
            raise ValueError("CNTV MangoTV temporary array allocation remains in " + start)
    return source



STATIC_FILTER_MARKER = "// loon-change: CNTV hoisted static membership lists v1"
STATIC_FILTER_PATTERN = re.compile(
    r"""(\[(?:\s*(?:"[^"\n]*"|'[^'\n]*'|-?\d+)\s*,?)+\s*\])\?\.includes\(([^()\n]*)\)"""
)


def optimize_static_filter_arrays(source):
    """Hoist literal membership arrays so response loops do not allocate them per item."""
    if STATIC_FILTER_MARKER in source:
        if source.count(STATIC_FILTER_MARKER) != 1 or STATIC_FILTER_PATTERN.search(source):
            raise ValueError("CNTV static membership-list hoist marker/structure drift")
        return source
    matches = list(STATIC_FILTER_PATTERN.finditer(source))
    if not matches:
        return source
    literals = {}
    for match in matches:
        literal = match.group(1)
        key = re.sub(r"\s+", " ", literal).strip()
        literals.setdefault(key, literal)
    names = {key: "CNTV_STATIC_FILTER_%02d" % (index + 1)
             for index, key in enumerate(literals)}
    source = STATIC_FILTER_PATTERN.sub(
        lambda match: names[re.sub(r"\s+", " ", match.group(1)).strip()]
        + ".includes(" + match.group(2) + ")",
        source,
    )
    declarations = [STATIC_FILTER_MARKER]
    declarations.extend(
        "const %s = %s;" % (names[key], literal)
        for key, literal in literals.items()
    )
    anchor = "const url = $request.url;"
    if source.count(anchor) != 1:
        raise ValueError("CNTV static membership-list insertion anchor changed")
    return source.replace(anchor, "\n".join(declarations) + "\n" + anchor, 1)


def optimize_source(source, commit="unknown"):
    def apply_optimizers(result):
        for optimizer in (
            optimize_get_my_menus,
            optimize_youku_home_feed,
            optimize_youku_home_query,
            optimize_youku_profile_comment_arrays,
            optimize_iqiyi_feed_arrays,
            optimize_mgtv_arrays,
            optimize_pre_parse_route_guard,
            optimize_static_filter_arrays,
            optimize_iqiyi_home_feed_callback_free,
        ):
            result = optimizer(result)
        return result

    if MARKER in source:
        return apply_optimizers(source)
    for legacy_marker in LEGACY_MARKERS:
        if legacy_marker in source:
            source = source.replace(legacy_marker, MARKER, 1)
            return apply_optimizers(source)
    body_guard = "if (!$response.body) $done({});"
    if source.count(body_guard) != 1:
        raise ValueError("CNTV response body guard changed; refusing optimization")
    source = source.replace(
        body_guard,
        "if (!$response.body) {\n  $done({});\n} else {",
        1,
    )
    anchor = 'const isYK = url.includes("youku.com/");'
    if source.count(anchor) != 1:
        raise ValueError("CNTV app dispatch anchor changed; refusing optimization")
    source = source.replace(anchor, anchor + "\n" + HELPER, 1)
    matches = list(FILTER_ASSIGNMENT.finditer(source))
    if len(matches) != 11:
        raise ValueError("CNTV filter inventory changed: expected 11, got %d" % len(matches))
    source = FILTER_ASSIGNMENT.sub(lambda match: "compactInPlace(%s, " % match.group(1), source)
    if re.search(r"\.filter\s*\(", source):
        raise ValueError("CNTV allocating filter remains after optimization")
    if source.count("function compactInPlace(items, keep)") != 1:
        raise ValueError("CNTV compaction helper definition count drift")
    if source.count("compactInPlace(") != 12:
        raise ValueError("expected 11 CNTV filters to use compactInPlace")
    source = source.rstrip() + "\n}\n"
    return apply_optimizers(MARKER + commit + "\n" + source)
def rewrite_plugin(plugin):
    local_count = plugin.count(LOCAL)
    remote_count = plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote CNTV script URLs")
    if local_count:
        if local_count != 26:
            raise ValueError("CNTV local trigger inventory changed: expected 26, got %d" % local_count)
        return plugin
    if remote_count != 26:
        raise ValueError("CNTV trigger inventory changed: expected 26, got %d" % remote_count)
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != 26:
        raise ValueError("CNTV local trigger migration incomplete")
    return result


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
        print("Optimized CNTV response script: %s (%d bytes)" % (args.output, len(result)))
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Routed all 26 CNTV/iQIYI/MGTV/Youku response triggers to the local optimized script")
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
