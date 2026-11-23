#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preserve Taobao trigger deduplication and response hot-path optimizations."""
import argparse
from pathlib import Path

LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/taobao/taobao.js"
KELEE_PATH = "/Modules/JavaScript/Kelee/Taobao_remove_ads/kelee.one_Taobao_remove_ads.js"
RUNTIME_MARKER = "// loon-change: Taobao pre-parse supported-route guard v1"
RUNTIME_GUARD = """  %s
  const shouldProcess =
    url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query") ||
    url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get") ||
    url.includes("poplayer.template.alibaba.com/");
  if (!shouldProcess) {
    $done({});
  } else {
""" % RUNTIME_MARKER

SPLASH_LOOP_MARKER = "// loon-change: Taobao indexed splash traversal v1"
OLD_SPLASH_BLOCK = "  if (obj?.data?.containers?.splash_home_base) {\n    let splash = obj.data.containers.splash_home_base;\n    if (splash?.base?.sections?.length > 0) {\n      for (let items of splash.base.sections) {\n        if (\"taobao-splash\" in items.bizData) {\n          if (items?.bizData?.[\"taobao-splash\"]?.data?.length > 0) {\n            for (let item of items.bizData[\"taobao-splash\"].data) {\n              setIfDifferent(item, \"waitTime\", \"0\");\n              setIfDifferent(item, \"times\", \"0\");\n              setIfDifferent(item, \"hotStart\", \"false\");\n              setIfDifferent(item, \"haveVoice\", \"false\");\n              setIfDifferent(item, \"hideTBLogo\", \"false\");\n              setIfDifferent(item, \"enable4G\", \"false\");\n              setIfDifferent(item, \"coldStart\", \"false\");\n              setIfDifferent(item, \"startTime\", \"3818332800000\");\n              setIfDifferent(item, \"endTime\", \"3818419199000\");\n              setIfDifferent(item, \"gmtStart\", \"2090-12-31 00:00:00\");\n              setIfDifferent(item, \"gmtEnd\", \"2090-12-31 23:59:59\");\n              setIfDifferent(item, \"gmtStartMs\", \"3818332800000\");\n              setIfDifferent(item, \"gmtEndMs\", \"3818419199000\");\n              if (item?.imgUrl) setIfDifferent(item, \"imgUrl\", \"\");\n              if (item?.videoUrl) setIfDifferent(item, \"videoUrl\", \"\");\n            }\n          }\n        }\n      }\n    }\n  }"
NEW_SPLASH_BLOCK = "  if (obj?.data?.containers?.splash_home_base) {\n    const sections = obj.data.containers.splash_home_base.base?.sections;\n    if (Array.isArray(sections) && sections.length > 0) {\n      // loon-change: Taobao indexed splash traversal v1\n      const sectionCount = sections.length;\n      for (let sectionIndex = 0; sectionIndex < sectionCount; sectionIndex++) {\n        const bizData = sections[sectionIndex]?.bizData;\n        const splashItems = bizData?.[\"taobao-splash\"]?.data;\n        if (!Array.isArray(splashItems) || splashItems.length === 0) continue;\n\n        const itemCount = splashItems.length;\n        for (let itemIndex = 0; itemIndex < itemCount; itemIndex++) {\n          const item = splashItems[itemIndex];\n          setIfDifferent(item, \"waitTime\", \"0\");\n          setIfDifferent(item, \"times\", \"0\");\n          setIfDifferent(item, \"hotStart\", \"false\");\n          setIfDifferent(item, \"haveVoice\", \"false\");\n          setIfDifferent(item, \"hideTBLogo\", \"false\");\n          setIfDifferent(item, \"enable4G\", \"false\");\n          setIfDifferent(item, \"coldStart\", \"false\");\n          setIfDifferent(item, \"startTime\", \"3818332800000\");\n          setIfDifferent(item, \"endTime\", \"3818419199000\");\n          setIfDifferent(item, \"gmtStart\", \"2090-12-31 00:00:00\");\n          setIfDifferent(item, \"gmtEnd\", \"2090-12-31 23:59:59\");\n          setIfDifferent(item, \"gmtStartMs\", \"3818332800000\");\n          setIfDifferent(item, \"gmtEndMs\", \"3818419199000\");\n          if (item?.imgUrl) setIfDifferent(item, \"imgUrl\", \"\");\n          if (item?.videoUrl) setIfDifferent(item, \"videoUrl\", \"\");\n        }\n      }\n    }\n  }"

def optimize_splash_loop(source):
    if SPLASH_LOOP_MARKER in source:
        required = (
            SPLASH_LOOP_MARKER,
            "const sections = obj.data.containers.splash_home_base.base?.sections;",
            "const sectionCount = sections.length;",
            "const bizData = sections[sectionIndex]?.bizData;",
            'const splashItems = bizData?.["taobao-splash"]?.data;',
            "const itemCount = splashItems.length;",
            "for (let itemIndex = 0; itemIndex < itemCount; itemIndex++)",
        )
        if any(token not in source for token in required):
            raise ValueError("Taobao indexed splash traversal drifted; refusing to overwrite")
        if "for (let items of splash.base.sections)" in source or 'for (let item of items.bizData["taobao-splash"].data)' in source:
            raise ValueError("Legacy Taobao splash iterator remains beside optimization marker")
        return source
    if source.count(OLD_SPLASH_BLOCK) != 1:
        raise ValueError("Expected exactly one Taobao splash traversal anchor")
    optimized = source.replace(OLD_SPLASH_BLOCK, NEW_SPLASH_BLOCK, 1)
    if optimized.count(SPLASH_LOOP_MARKER) != 1:
        raise ValueError("Taobao indexed splash traversal postcondition failed")
    return optimized


def optimize_runtime_source(source):
    if RUNTIME_MARKER not in source:
        anchor = "  const obj = JSON.parse($response.body);\n"
        if source.count(anchor) != 1:
            raise ValueError("Expected exactly one Taobao JSON.parse anchor")
        source = source.replace(anchor, RUNTIME_GUARD + anchor, 1)
        tail = "$done(modified ? {body: JSON.stringify(obj)} : {});\n}\n"
        if not source.endswith(tail):
            raise ValueError("Taobao runtime tail changed; refusing to add guard")
        source = source[:-len(tail)] + tail.replace("}\n", "  }\n}\n")
    else:
        required = (RUNTIME_MARKER, "const shouldProcess =", "if (!shouldProcess) {",
                    'url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query")',
                    'url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get")',
                    'url.includes("poplayer.template.alibaba.com/")')
        if any(token not in source for token in required):
            raise ValueError("Taobao pre-parse guard drifted; refusing to overwrite")
        if source.index("const shouldProcess =") > source.index("JSON.parse($response.body)"):
            raise ValueError("Taobao pre-parse guard moved after JSON.parse")
    source = optimize_splash_loop(source)
    if source.index("const shouldProcess =") > source.index("JSON.parse($response.body)"):
        raise ValueError("Taobao pre-parse guard insertion order invalid")
    return source

def classify(line):
    if "guide-acs" in line and "cloudvideo" in line and "splash" in line: return "guide"
    if "poplayer" in line: return "poplayer"
    return None

def rewrite_plugin(plugin):
    lines = plugin.splitlines(keepends=True)
    section = None
    local = {"guide": 0, "poplayer": 0}
    duplicates = {"guide": [], "poplayer": []}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"): section = stripped[1:-1].strip().lower()
        if section == "script" and LOCAL in line:
            kind = classify(line)
            if kind: local[kind] += 1
        if KELEE_PATH in line:
            if section != "script" or ("response if " + "$" + "{url}") not in line or "requires_body=true" not in line:
                raise ValueError("Unreviewed Taobao Kelee handler section/format; refusing cleanup")
            kind = classify(line)
            if not kind: raise ValueError("Unrecognized Taobao Kelee URL matcher; refusing cleanup")
            duplicates[kind].append(index)
    if local != {"guide": 1, "poplayer": 1}:
        raise ValueError("Local optimized Taobao trigger inventory changed: %r" % local)
    if not any(duplicates.values()): return plugin
    if len(duplicates["guide"]) != 1 or len(duplicates["poplayer"]) != 1:
        raise ValueError("Taobao Kelee trigger inventory changed: expected one guide and one poplayer handler")
    removed = set(duplicates["guide"] + duplicates["poplayer"])
    result = "".join(line for index, line in enumerate(lines) if index not in removed)
    if KELEE_PATH in result or result.count(LOCAL) < 2:
        raise ValueError("Taobao duplicate cleanup removed local coverage or left a Kelee handler")
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin")
    parser.add_argument("--runtime")
    args = parser.parse_args()
    if not args.plugin and not args.runtime:
        parser.error("at least one of --plugin or --runtime is required")
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Removed duplicate Taobao response handlers; retained two local optimized triggers")
    if args.runtime:
        path = Path(args.runtime)
        path.write_text(optimize_runtime_source(path.read_text(encoding="utf-8")), encoding="utf-8")
        print("Applied/verified Taobao pre-parse supported-route guard")

if __name__ == "__main__": main()
