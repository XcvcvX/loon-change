#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply callback-free, scenario-specific compaction to the local Bilibili response script."""
import argparse
from pathlib import Path

MARKER = "// loon-change: Bilibili callback-free response list compaction v1"

HELPER = "  // loon-change: Bilibili callback-free response list compaction v1\n  function bilibiliTabRank(name, mode) {\n    if (mode === \"bottomTab\") {\n      if (name === \"首页\") return 0;\n      if (name === \"动态\") return 1;\n      if (name === \"关注\") return 2;\n      if (name === \"我的\") return 3;\n    } else {\n      if (name === \"推荐\") return 0;\n      if (name === \"热门\") return 1;\n      if (name === \"影视\") return 2;\n      if (name === \"动画\") return 3;\n    }\n    return -1;\n  }\n\n  function compactBilibiliList(items, mode) {\n    const length = items.length;\n    let write = 0;\n\n    if (mode === \"bottomTab\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        const name = item?.name;\n        if (name === \"首页\" || name === \"动态\" || name === \"关注\" || name === \"我的\") {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"homeTab\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        const name = item?.name;\n        if (name === \"推荐\" || name === \"热门\" || name === \"影视\" || name === \"动画\") {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"topMessage\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        if (item?.name === \"消息\") {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"ipadRecommend\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        const id = item.id;\n        if (id === 789 || id === 790) {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"ipadMore\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        const id = item.id;\n        if (id === 797 || id === 798) {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"feedAv\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        if (item?.card_goto === \"av\") {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"pgcBanner\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        if (item?.link?.includes(\"play\")) {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"pgcFunction\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        if (item?.blink?.startsWith(\"bilibili\")) {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else if (mode === \"liveOuterList\") {\n      for (let read = 0; read < length; read++) {\n        const item = items[read];\n        if (item?.biz_id !== 33) {\n          if (write !== read) items[write] = item;\n          write++;\n        }\n      }\n    } else {\n      return items;\n    }\n\n    if (write !== length) {\n      items.length = write;\n      modified = true;\n    }\n\n    if (mode === \"bottomTab\" || mode === \"homeTab\") {\n      let needsSort = false;\n      for (let read = 1; read < write; read++) {\n        if (bilibiliTabRank(items[read - 1]?.name, mode) >\n            bilibiliTabRank(items[read]?.name, mode)) {\n          needsSort = true;\n          break;\n        }\n      }\n      if (needsSort) {\n        modified = true;\n        for (let read = 1; read < write; read++) {\n          const item = items[read];\n          const rank = bilibiliTabRank(item?.name, mode);\n          let insert = read - 1;\n          while (insert >= 0 && bilibiliTabRank(items[insert]?.name, mode) > rank) {\n            items[insert + 1] = items[insert];\n            insert--;\n          }\n          if (insert + 1 !== read) items[insert + 1] = item;\n        }\n      }\n    }\n    return items;\n  }\n\n"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Bilibili {label} anchor drift: expected 1, found {count}")
    return source.replace(old, new, 1)


def validate(source: str) -> str:
    required = (
        MARKER,
        "function bilibiliTabRank(name, mode)",
        "function compactBilibiliList(items, mode)",
        'compactBilibiliList(obj.data.bottom, "bottomTab");',
        'compactBilibiliList(obj.data.tab, "homeTab");',
        'compactBilibiliList(obj.data.top, "topMessage");',
        'compactBilibiliList(obj.data.items, "feedAv");',
        'compactBilibiliList(obj.data.new_tab_info.outer_list, "liveOuterList");',
        "const modulesLength = modules.length;",
        "const splashListLength = splashList.length;",
    )
    if any(token not in source for token in required):
        raise ValueError("Bilibili callback-free compaction is incomplete")
    for forbidden in ("function filterInPlace(", "filterTracked(", "filterAndSortAllowed(", ".forEach(", ".sort(", "for (let i of "):
        if forbidden in source:
            raise ValueError(f"Bilibili callback/iterator path remains: {forbidden}")
    if source.count(MARKER) != 1:
        raise ValueError("Bilibili callback-free marker count changed")
    return source


def optimize_source(source: str) -> str:
    if MARKER in source:
        return validate(source)

    start_token = "  function filterInPlace(items, predicate) {"
    end_token = "  function deleteTracked(target, key) {"
    if source.count(start_token) != 1 or source.count(end_token) != 1:
        raise ValueError("Bilibili generic filter helper boundary changed; refusing rewrite")
    start = source.index(start_token)
    end = source.index(end_token, start)
    source = source[:start] + "  let modified = false;\n\n" + HELPER + end_token + source[end + len(end_token):]

    sort_start = source.index("  function filterAndSortAllowed(items, allowedNames) {")
    hot_marker = source.index("// loon-change: Bilibili hot-loop scalar membership v1", sort_start)
    source = source[:sort_start] + source[hot_marker:]

    replacements = (
        ('    const sortLists = ["首页", "动态", "关注", "我的"];\n    filterAndSortAllowed(obj.data.bottom, sortLists);',
         '    compactBilibiliList(obj.data.bottom, "bottomTab");', "bottom tab"),
        ('    const sortLists = ["推荐", "热门", "影视", "动画"];\n    filterAndSortAllowed(obj.data.tab, sortLists);',
         '    compactBilibiliList(obj.data.tab, "homeTab");', "home tab"),
        ('    filterTracked(obj.data.top, (i) => i?.name === "消息");',
         '    compactBilibiliList(obj.data.top, "topMessage");', "top message"),
        ('  const del = ["rework_v1", "vip_section", "vip_section_v2"];\n  for (let i of del) {\n    // 不必要项目\n    deleteTracked(obj.data, i);\n  }',
         '  // 不必要项目\n  deleteTracked(obj.data, "rework_v1");\n  deleteTracked(obj.data, "vip_section");\n  deleteTracked(obj.data, "vip_section_v2");', "profile removals"),
        ('    const itemList = [789, 790];\n    filterTracked(obj.data.ipad_recommend_sections, (i) => itemList.includes(i.id));',
         '    compactBilibiliList(obj.data.ipad_recommend_sections, "ipadRecommend");', "iPad recommend"),
        ('    const itemList = [797, 798];\n    filterTracked(obj.data.ipad_more_sections, (i) => itemList.includes(i.id));',
         '    compactBilibiliList(obj.data.ipad_more_sections, "ipadMore");', "iPad more"),
        ('    filterTracked(obj.data.items, (i) => i?.card_goto === "av");',
         '    compactBilibiliList(obj.data.items, "feedAv");', "feed index"),
        ('    item.forEach((i) => {\n      deleteTracked(obj.data, i);\n    });',
         '    deleteTracked(obj.data, "account");\n    deleteTracked(obj.data, "event_list");\n    deleteTracked(obj.data, "preload");\n    deleteTracked(obj.data, "show");', "splash fields"),
        ('    const item = ["account", "event_list", "preload", "show"];\\n    deleteTracked(obj.data, "account");',
         '    deleteTracked(obj.data, "account");', "splash temporary array"),
        ('      for (let i of obj.data.list) {\n        if (i.duration !== 0 || i.enable_pre_download !== false ||\n            i.begin_time !== 3818332800 || i.end_time !== 3818419199) modified = true;\n        i.duration = 0;\n        i.enable_pre_download = false;\n        i.begin_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00\n        i.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59\n      }',
         '      const splashList = obj.data.list;\n      const splashListLength = splashList.length;\n      for (let splashIndex = 0; splashIndex < splashListLength; splashIndex++) {\n        const i = splashList[splashIndex];\n        if (i.duration !== 0 || i.enable_pre_download !== false ||\n            i.begin_time !== 3818332800 || i.end_time !== 3818419199) modified = true;\n        i.duration = 0;\n        i.enable_pre_download = false;\n        i.begin_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00\n        i.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59\n      }', "splash list"),
        ('          filterTracked(i.items, (ii) => ii?.link?.includes("play"));',
         '          compactBilibiliList(i.items, "pgcBanner");', "PGC banner"),
        ('          filterTracked(i.items, (ii) => ii?.blink?.startsWith("bilibili"));',
         '          compactBilibiliList(i.items, "pgcFunction");', "PGC function"),
        ('    filterTracked(obj.data.new_tab_info.outer_list, (i) => i?.biz_id !== 33);',
         '    compactBilibiliList(obj.data.new_tab_info.outer_list, "liveOuterList");', "live tabs"),
    )
    for old, new, label in replacements:
        source = replace_once(source, old, new, label)

    pgc_start = source.index('} else if (url.includes("/pgc/page/")) {')
    pgc_end = source.index('} else if (url.includes("/index/getInfoByRoom")) {', pgc_start)
    pgc = source[pgc_start:pgc_end]
    pgc = replace_once(
        pgc,
        "    obj.result.modules.forEach((i) => {",
        "    const modules = obj.result.modules;\n    const modulesLength = modules.length;\n    for (let moduleRead = 0; moduleRead < modulesLength; moduleRead++) {\n      const i = modules[moduleRead];",
        "PGC module loop",
    )
    pgc = replace_once(pgc, "    });\n  }\n", "    }\n  }\n", "PGC module loop close")
    source = source[:pgc_start] + pgc + source[pgc_end:]
    return validate(source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    path = Path(args.source)
    path.write_text(optimize_source(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("Bilibili callback-free response list compaction applied")


if __name__ == "__main__":
    main()
