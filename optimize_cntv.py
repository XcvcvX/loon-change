#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize the high-fanout CNTV/iQIYI/MGTV/Youku response script."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/cntv.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/cntv/cntv.js"
MARKER = "// loon-change: CNTV response compaction optimization v1; upstream zirawell/R-Store@"
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


def optimize_source(source, commit="unknown"):
    if MARKER in source:
        return source
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
    return MARKER + commit + "\n" + source


def rewrite_plugin(plugin):
    if LOCAL in plugin:
        if REMOTE in plugin:
            raise ValueError("mixed local and remote CNTV script URLs")
        return plugin
    count = plugin.count(REMOTE)
    if count != 26:
        raise ValueError("CNTV trigger inventory changed: expected 26, got %d" % count)
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
