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
)
MARKER = "// loon-change: CNTV response compaction optimization v3; upstream zirawell/R-Store@"
ROUTE_GUARD_MARKER = "// loon-change: CNTV pre-parse supported-route guard v1"
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
YOUKU_HOME_QUERY_BRANCH = "  } else if (url.includes(\"columbus.home.query/\")) {\n    // CNTV Youku home.query nested-list compaction: reuse all four response arrays.\n    if (obj?.data?.[\"2019061000\"]?.data) {\n      let objData = obj.data[\"2019061000\"].data;\n      if (objData?.data?.indexPositionResult?.length > 0) objData.data.indexPositionResult = [];\n      if (objData?.nodes?.length > 0) {\n        compactInPlace(objData.nodes, item => {\n          if ([\"CHILD\", \"COMIC2\", \"20230929GREATWORKMFK\"]?.includes(item?.data?.nodeKey)) return false;\n          if (item?.data?.indexPositionResult?.length > 0) item.data.indexPositionResult = [];\n          if (item?.data?.refreshImg) delete item.data.refreshImg;\n          if (item?.nodes?.length > 0) {\n            compactInPlace(item.nodes, i => {\n              if (i?.data?.crmSale) delete i.data.crmSale;\n              if ([\"UC广告抽屉\", \"橱窗广告\"]?.includes(i?.typeName)) return false;\n              if (i?.id === 31476 && i?.data?.keywords?.length > 0) delete i.data.keywords;\n              if (i?.id === 35505 || i?.id === 37335) return false;\n              if (i?.nodes?.length > 0) {\n                compactInPlace(i.nodes, ii => {\n                  if ([\"PHONE_FEED_CARD_B_AD\", \"PHONE_FEED_CARD_S_AD\", \"PHONE_H_UC_AD\", \"PHONE_IMG_A\", \"PHONE_YK_AD_BANNER\"]?.includes(ii?.typeName)) return false;\n                  if (ii?.nodes?.length > 0) {\n                    compactInPlace(ii.nodes, iii =>\n                      iii?.typeName !== \"PHONE_FEED_CARD_S_AD\" &&\n                      !iii?.data?.hasOwnProperty(\"ad\")\n                    );\n                  }\n                  return true;\n                });\n              }\n              return true;\n            });\n          }\n          return true;\n        });\n      }\n    }\n"

def optimize_youku_home_query(source):
    start = '  } else if (url.includes("columbus.home.query/")) {'
    end = '  } else if (url.includes("columbus.uc.query/")) {'
    if YOUKU_QUERY_MARKER in source:
        if source.count(YOUKU_QUERY_MARKER) != 1 or "let newIII = []" in source:
            raise ValueError("CNTV Youku home.query compaction marker/structure drift")
        return source
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("CNTV Youku home.query route anchors changed")
    begin, finish = source.index(start), source.index(end)
    result = source[:begin] + YOUKU_HOME_QUERY_BRANCH + "  " + YOUKU_QUERY_MARKER + "\\n" + source[finish:]
    if "let newIII = []" in result or "let newII = []" in result:
        raise ValueError("CNTV Youku home.query temporary nested arrays remain")
    return result

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        return optimize_pre_parse_route_guard(optimize_youku_home_query(optimize_get_my_menus(source)))
    for legacy_marker in LEGACY_MARKERS:
        if legacy_marker in source:
            source = source.replace(legacy_marker, MARKER, 1)
            return optimize_pre_parse_route_guard(optimize_youku_home_query(optimize_get_my_menus(source)))
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
        optimize_youku_home_query(optimize_get_my_menus(MARKER + commit + "\n" + source))
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
