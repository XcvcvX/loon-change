#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Dushu365 local response runtime and migrate its five active hooks."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/dushu365.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/dushu365/dushu365.js"
EXPECTED_TRIGGERS = 5
MARKER = "// Dushu365 (FanShu) response optimizer"
UPSTREAM_ANCHORS = (
    '"/abtest-front/banner-modular/get"',
    '"/fs-member/user/profile/v100/detail"',
    '"/task-orchestration/taskCenter/api/v101/taskList"',
    '"/resource-orchestration-system/book/v101/content"',
    '"/user-orchestration/user/api/v101/ceiltip"',
    'reqentryption',
    'base64.decode',
    'utf8.decode',
    'base64.encode',
    'utf8.encode',
)


def optimize_source(source: str, template: str, commit: str = "unknown") -> str:
    missing = [anchor for anchor in UPSTREAM_ANCHORS if anchor not in source]
    if missing:
        raise ValueError("Dushu365 upstream behavior/encryption anchors changed: " + ", ".join(missing))
    if source.count('Pathname.includes("/abtest-front/banner-modular/get")') != 1:
        raise ValueError("Dushu365 banner route anchor count drift")
    if source.count('Pathname.includes("/fs-member/user/profile/v100/detail")') != 1:
        raise ValueError("Dushu365 profile route anchor count drift")
    if source.count('Pathname.includes("/task-orchestration/taskCenter/api/v101/taskList")') != 1:
        raise ValueError("Dushu365 task route anchor count drift")
    if source.count('Pathname.includes("/resource-orchestration-system/book/v101/content")') != 1:
        raise ValueError("Dushu365 book route anchor count drift")
    if source.count('Pathname.includes("/user-orchestration/user/api/v101/ceiltip")') != 1:
        raise ValueError("Dushu365 ceiltip route anchor count drift")
    if template.count(MARKER) != 1:
        raise ValueError("Dushu365 local runtime template marker count drift")
    if template.count("pathname.includes(") != EXPECTED_TRIGGERS:
        raise ValueError("Dushu365 local runtime route inventory drift")
    if ".filter(" in template or ".map(" in template:
        raise ValueError("Dushu365 local runtime contains allocating filter/map calls")
    result = re.sub(
        r"(?m)^// Upstream: zirawell/R-Store [0-9a-f]{40}$",
        "// Upstream: zirawell/R-Store " + commit,
        template,
        count=1,
    )
    if result == template and commit not in template:
        raise ValueError("Dushu365 upstream commit marker could not be updated")
    return result


def rewrite_plugin(plugin: str) -> str:
    local_count, remote_count = plugin.count(LOCAL), plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote Dushu365 script URLs")
    if local_count:
        if local_count != EXPECTED_TRIGGERS:
            raise ValueError("Dushu365 local trigger inventory changed: expected 5, got %d" % local_count)
        return plugin
    if remote_count != EXPECTED_TRIGGERS:
        raise ValueError("Dushu365 trigger inventory changed: expected 5, got %d" % remote_count)
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != EXPECTED_TRIGGERS:
        raise ValueError("Dushu365 local trigger migration incomplete")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source")
    parser.add_argument("--output")
    parser.add_argument("--upstream-commit", default="unknown")
    parser.add_argument("--plugin")
    args = parser.parse_args()
    if args.source or args.output:
        if not args.source or not args.output:
            parser.error("--source and --output must be supplied together")
        template_path = Path(__file__).resolve().parents[1] / "scripts" / "dushu365" / "dushu365.js"
        template = template_path.read_text(encoding="utf-8")
        result = optimize_source(Path(args.source).read_text(encoding="utf-8-sig"), template, args.upstream_commit)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result, encoding="utf-8")
        print("Optimized Dushu365 response script: %s (%d bytes)" % (output, len(result.encode("utf-8"))))
    if args.plugin:
        path = Path(args.plugin)
        rewritten = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(rewritten, encoding="utf-8")
        print("Routed all %d Dushu365 response triggers to the local optimized handler" % EXPECTED_TRIGGERS)
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
