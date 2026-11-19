#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove duplicate Taobao splash response handlers while preserving optimized local triggers."""
import argparse
from pathlib import Path

LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/taobao/taobao.js"
KELEE_PATH = "/Modules/JavaScript/Kelee/Taobao_remove_ads/kelee.one_Taobao_remove_ads.js"

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
            if section != "script" or "response if ${url}" not in line or "requires_body=true" not in line:
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
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
    print("Removed duplicate Taobao response handlers; retained two local optimized triggers")

if __name__ == "__main__": main()
