#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the lightweight local Ximalaya response handler."""
from __future__ import annotations

import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/xmly.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/xmly/xmly.js"
EXPECTED_TRIGGERS = 5
MARKER = "// loon-change: Ximalaya in-place filters and lazy response serialization v1; upstream zirawell/R-Store@"
HANDLER = r'''const KEEP_CATEGORY_TYPES = new Set(["recommend", "template_category", "single_category"]);
const KEEP_HOME_ENTRANCE_IDS = new Set([210, 213, 215]);

const url = typeof $request !== "undefined" && $request ? ($request.url || "") : "";
const body = typeof $response !== "undefined" && $response ? $response.body : "";

if (typeof body !== "string" || body.length === 0) {
  $done({});
} else {
  let route = 0;
  if (url.includes("/discovery-category/customCategories")) route = 1;
  else if (/\/discovery-category\/v\d\/category/.test(url)) route = 2;
  else if (url.includes("/focus-mobile/focusPic")) route = 3;
  else if (/\/discovery-feed\/v\d\/mix/.test(url)) route = 4;
  else if (/\/mobile-user\/v\d\/homePage/.test(url)) route = 5;

  if (route === 0) {
    $done({});
  } else {
    let modified = false;
    try {
      const obj = JSON.parse(body);

      switch (route) {
        case 1:
          if (obj.customCategoryList) {
            modified = compactInPlace(obj.customCategoryList, item =>
              KEEP_CATEGORY_TYPES.has(item.itemType) && item.categoryId !== 1005
            ) || modified;
          }
          if (obj.defaultTabList) {
            modified = compactInPlace(obj.defaultTabList, item =>
              KEEP_CATEGORY_TYPES.has(item.itemType) && item.categoryId !== 1005
            ) || modified;
          }
          break;

        case 2:
          if (obj.focusImages && obj.focusImages.data) {
            modified = compactInPlace(obj.focusImages.data, item =>
              item.realLink.indexOf("open") !== -1 && !item.isAd
            ) || modified;
          }
          break;

        case 3:
          if (obj.header && obj.header.length <= 1) {
            modified = compactInPlace(obj.header[0].item.list[0].data, item =>
              item.realLink.indexOf("open") !== -1 && !item.isAd
            ) || modified;
          }
          break;

        case 4:
          if (Array.isArray(obj.header) && obj.header.length === 2) {
            delete obj.header[0];
            modified = true;
          }
          modified = compactInPlace(obj.body, item =>
            !(item.item?.adInfo || item.item?.moduleType == "mix_ad" || "bigCard" == item.displayClass)
          ) || modified;
          break;

        case 5:
          if (obj.data.serviceModule.entrances) {
            modified = compactInPlace(obj.data.serviceModule.entrances, item =>
              KEEP_HOME_ENTRANCE_IDS.has(item.id)
            ) || modified;
          }
          break;
      }

      if (modified) {
        $done({body: JSON.stringify(obj)});
      } else {
        $done({});
      }
    } catch (error) {
      console.log("[Ximalaya] response cleanup failed; keeping original response: " + error.message);
      $done({});
    }
  }
}

function compactInPlace(items, keep) {
  if (!Array.isArray(items)) {
    throw new TypeError("Expected an array for Ximalaya response cleanup");
  }
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item, read)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  if (write === length) return false;
  items.length = write;
  return true;
}

'''


def optimize_source(source: str, commit: str = "unknown") -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("Ximalaya optimization marker count drift")
        if ".filter(" in source or ".map(" in source:
            raise ValueError("Ximalaya allocating Array.filter/map call remains")
        if source.count("function compactInPlace(items, keep)") != 1:
            raise ValueError("Ximalaya in-place compaction helper count drift")
        if source.count("const KEEP_CATEGORY_TYPES =") != 1 or source.count("const KEEP_HOME_ENTRANCE_IDS =") != 1:
            raise ValueError("Ximalaya shared lookup constants must be initialized exactly once")
        if source.count("$done(") != 5:
            raise ValueError("Ximalaya completion path count drift")
        return source

    required = (
        "const version = 'V1.0.38';",
        r"case/discovery-category\/customCategories/.test($request.url):",
        r"case/discovery-category\/v\d\/category/.test($request.url):",
        r"case/focus-mobile\/focusPic/.test($request.url):",
        r"case/discovery-feed\/v\d\/mix/.test($request.url):",
        r"case/mobile-user\/v\d\/homePage/.test($request.url):",
    )
    missing = [anchor for anchor in required if anchor not in source]
    if missing:
        raise ValueError("Ximalaya upstream route inventory changed: " + ", ".join(missing))
    if source.count(".filter(") != 6:
        raise ValueError("Ximalaya filter inventory changed; expected 6 allocating filters")
    return MARKER + commit + "\n" + HANDLER


def rewrite_plugin(plugin: str) -> str:
    local_count = plugin.count(LOCAL)
    remote_count = plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote Ximalaya script URLs")
    if local_count:
        if local_count != EXPECTED_TRIGGERS:
            raise ValueError("Ximalaya local trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, local_count))
        return plugin
    if remote_count != EXPECTED_TRIGGERS:
        raise ValueError("Ximalaya trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, remote_count))
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != EXPECTED_TRIGGERS:
        raise ValueError("Ximalaya local trigger migration incomplete")
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
        result = optimize_source(Path(args.source).read_text(encoding="utf-8-sig"), args.upstream_commit)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized Ximalaya response script: %s (%d bytes)" % (args.output, len(result.encode("utf-8"))))
    if args.plugin:
        path = Path(args.plugin)
        rewritten = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(rewritten, encoding="utf-8")
        print("Routed all %d Ximalaya response triggers to the local optimized handler" % EXPECTED_TRIGGERS)
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
