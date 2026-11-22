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
)
MARKER = "// loon-change: CNTV response compaction optimization v5; upstream zirawell/R-Store@"
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
    // 首页信息流：原地压缩广告卡片组内节点，避免创建 newNodes/newItems 临时数组。
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
        return source
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV Youku home.query route anchors changed")
    begin, finish = source.index(start), source.index(end)
    result = source[:begin] + YOUKU_HOME_QUERY_BRANCH + "  " + YOUKU_QUERY_MARKER + "\\n" + source[finish:]
    optimized_end = result.index(end, begin)
    branch = result[begin:optimized_end]
    if any(token in branch for token in ("let newNodes = []", "let newItems = []", "let newII = []", "let newIII = []")):
        raise ValueError("CNTV Youku home.query temporary nested arrays remain")
    return result


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

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        return optimize_pre_parse_route_guard(optimize_iqiyi_feed_arrays(optimize_youku_home_query(optimize_youku_home_feed(optimize_get_my_menus(source)))))
    for legacy_marker in LEGACY_MARKERS:
        if legacy_marker in source:
            source = source.replace(legacy_marker, MARKER, 1)
            return optimize_pre_parse_route_guard(optimize_iqiyi_feed_arrays(optimize_youku_home_query(optimize_youku_home_feed(optimize_get_my_menus(source)))))
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
    return optimize_pre_parse_route_guard(
        optimize_iqiyi_feed_arrays(optimize_youku_home_query(optimize_youku_home_feed(optimize_get_my_menus(MARKER + commit + "\n" + source))))
    )

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
