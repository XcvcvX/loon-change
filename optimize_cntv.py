#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize the high-fanout CNTV/iQIYI/MGTV/Youku response script."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/cntv/cntv.js"
LEGACY_MARKER = "// loon-change: CNTV response compaction optimization v1; upstream zirawell/R-Store@"
MARKER = "// loon-change: CNTV response compaction optimization v2; upstream zirawell/R-Store@"
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
    if MENUS_MARKER in source:
        if "newMenus" in source or "newLists" in source:
            raise ValueError("CNTV getMyMenus marker exists but allocating arrays remain")
        return source
    anchor = '  } else if (url.includes("/getMyMenus?")) {'
    if anchor not in source:
        return source
    old_block = "    if (obj?.data?.length > 0) {\n      let newMenus = [];\n      for (let item of obj.data) {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) {\n          // 精简列表\n          continue;\n        } else {\n          if (item?.menuList?.length > 0) {\n            let newLists = [];\n            for (let i of item.menuList) {\n              if (i?.menuType === 121) {\n                // 121有奖限时问卷\n                continue;\n              } else {\n                newLists.push(i);\n              }\n            }\n            item.menuList = newLists;\n            newMenus.push(item);\n          } else {\n            newMenus.push(item);\n          }\n        }\n      }\n      obj.data = newMenus;\n    }"
    new_block = "    if (obj?.data?.length > 0) {\n      compactInPlace(obj.data, item => {\n        if ([\"wd_liebiao_2\", \"wd_liebiao_3\", \"wd_liebiao_4\"]?.includes(item?.statistic?.block)) {\n          // 精简列表\n          return false;\n        }\n        if (item?.menuList?.length > 0) {\n          // 121有奖限时问卷\n          compactInPlace(item.menuList, menu => menu?.menuType !== 121);\n        }\n        return true;\n      });\n    }"
    if source.count(old_block) != 1:
        raise ValueError("CNTV getMyMenus block changed; refusing in-place compaction")
    source = source.replace(old_block, new_block, 1)
    source = source.replace(anchor, anchor + "\n    " + MENUS_MARKER, 1)
    if "newMenus" in source or "newLists" in source:
        raise ValueError("CNTV getMyMenus temporary arrays remain")
    return source


def optimize_source(source, commit="unknown"):
    if MARKER in source:
        return optimize_get_my_menus(source)
    if LEGACY_MARKER in source:
        source = source.replace(LEGACY_MARKER, MARKER, 1)
        return optimize_get_my_menus(source)
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
    return optimize_get_my_menus(MARKER + commit + "\n" + source)


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
