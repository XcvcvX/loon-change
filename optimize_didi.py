#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize the active Didi response script and pin its plugin triggers locally."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/didi/didi.js"
MARKER = "// loon-change: Didi response compaction optimization v1; upstream zirawell/R-Store@"
EXPECTED_FILTERS = 7

HELPER = """function compactInPlace(items, keep) {
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
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
        if re.search(r"\.filter\s*\(", source):
            raise ValueError("Didi optimization marker exists but allocating filter remains")
        return source

    body_guard = "if (!$response.body) $done({});"
    if source.count(body_guard) != 1:
        raise ValueError("Didi response body guard changed; refusing optimization")
    source = source.replace(
        body_guard,
        "if (!$response.body) {\n  $done({});\n} else {",
        1,
    )

    anchor = "const url = $request.url;"
    if source.count(anchor) != 1:
        raise ValueError("Didi URL dispatch anchor changed; refusing optimization")
    source = source.replace(anchor, anchor + "\n\n" + HELPER, 1)

    matches = list(FILTER_ASSIGNMENT.finditer(source))
    if len(matches) != EXPECTED_FILTERS:
        raise ValueError(
            "Didi filter inventory changed: expected %d, got %d"
            % (EXPECTED_FILTERS, len(matches))
        )
    source = FILTER_ASSIGNMENT.sub(
        lambda match: "compactInPlace(%s, " % match.group(1),
        source,
    )
    if re.search(r"\.filter\s*\(", source):
        raise ValueError("Didi allocating filter remains after optimization")
    if source.count("function compactInPlace(items, keep)") != 1:
        raise ValueError("Didi compaction helper definition count drift")
    if source.count("compactInPlace(") != EXPECTED_FILTERS + 1:
        raise ValueError("expected all seven Didi filters to use compactInPlace")

    source = source.rstrip() + "\n}\n"
    return MARKER + commit + "\n" + source


def rewrite_plugin(plugin):
    lines = plugin.splitlines(keepends=True)
    section = ""
    remote_lines = 0
    local_lines = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            continue
        if section != "script":
            continue
        if REMOTE in line:
            remote_lines += 1
        if LOCAL in line:
            local_lines += 1

    if remote_lines and local_lines:
        raise ValueError("mixed local and remote Didi script URLs")
    count = remote_lines or local_lines
    if count not in (2, 4):
        raise ValueError(
            "Didi trigger inventory changed: expected 2 retained or 4 full triggers, got %d"
            % count
        )
    if local_lines:
        return plugin

    output = []
    section = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
        if section == "script":
            line = line.replace(REMOTE, LOCAL)
        output.append(line)
    result = "".join(output)
    if REMOTE in result or result.count(LOCAL) != count:
        raise ValueError("Didi local trigger migration incomplete")
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
        result = optimize_source(
            Path(args.source).read_text(encoding="utf-8-sig"),
            args.upstream_commit,
        )
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding="utf-8")
        print("Optimized Didi response script: %s (%d bytes)" % (target, len(result)))

    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Routed the retained Didi response triggers to the local optimized script")

    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
