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

def optimize_source(source: str, upstream_commit: str | None = None) -> str:
    """Replace Youku home.query's nested filtered-copy arrays with stable in-place compaction."""
    if SOURCE_MARKER in source:
        if not upstream_commit:
            return source
        if not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
            raise ValueError("invalid Wool Scripts upstream commit")
        source = re.sub(r"^// loon-change:.*\n", "", source, count=1)
        return SOURCE_MARKER + "; upstream fmz200/wool_scripts@" + upstream_commit + "\n" + source

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
    return SOURCE_MARKER + "; upstream fmz200/wool_scripts@" + upstream_commit + "\n// loon-change: Youku home.feed in-place compaction v1\n" + source


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
