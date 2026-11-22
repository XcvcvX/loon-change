#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a guarded, in-place local Amap R-Store response handler."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/amap.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js"
MARKER = "// loon-change: Amap R-Store local fast path; upstream zirawell/R-Store@"
GUARD_MARKER = "// loon-change: Amap R-Store supported-route guard v1"
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
FILTER_ASSIGNMENT = re.compile(r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\1\.filter\s*\(")
ROUTE_GUARD = """// loon-change: Amap R-Store supported-route guard v1
const shouldProcess =
  url.includes("/aos/perception/publicTravel/beforeNavi") ||
  url.includes("/bus/plan/integrate") ||
  url.includes("/c3frontend/af-hotel/page/main") ||
  url.includes("/c3frontend/af-launch/page/main") ||
  url.includes("/perception/drive/routeInfo") ||
  url.includes("/perception/drive/routePlan") ||
  url.includes("/shield/search/common/coupon/info") ||
  url.includes("/shield/search/poi/detail") ||
  url.includes("/shield/search_business/process/marketingOperationStructured") ||
  url.includes("/shield/search_poi/") ||
  url.includes("/faas/amap-navigation/card-service-plan-home") ||
  url.includes("/faas/amap-navigation/main-page") ||
  url.includes("/shield/frogserver/aocs/updatable/1") ||
  url.includes("/shield/dsp/profile/index/nodefaasv") ||
  url.includes("/shield/search/nearbyrec_smart") ||
  url.includes("/boss/car/order/content_info") ||
  url.includes("/boss/order_web/friendly_information") ||
  url.includes("/promotion-web/resource") ||
  url.includes("/sharedtrip/taxi/order_detail_car_tips");
if (!shouldProcess) {
  $done({});
} else {
"""


ARRAY_MARKER = "// loon-change: Amap hoisted static filter arrays v1"
STATIC_ARRAY_PATTERN = re.compile(
    r"""(\[(?:\s*(?:"[^"\n]*"|'[^'\n]*'|-?\d+)\s*,?)+\s*\])\?\.includes\(([^()\n]*)\)"""
)


def hoist_static_arrays(source):
    marker_present = ARRAY_MARKER in source
    if marker_present and source.count(ARRAY_MARKER) != 1:
        raise ValueError("Amap static array hoist marker count drift")

    existing_ids = [int(value) for value in re.findall(r"const AMAP_STATIC_ITEMS_(\d+)\s*=", source)]
    next_id = max(existing_ids, default=0) + 1
    arrays = {}
    names = {}

    def register(literal):
        key = re.sub(r"\s+", " ", literal).strip()
        if key not in names:
            names[key] = "AMAP_STATIC_ITEMS_%02d" % (next_id + len(names))
            arrays[key] = literal
        return names[key]

    declaration_pattern = re.compile(
        r"^([ \t]*)const items = (\[[^\n]*?\];?|\[[\s\S]*?^[ \t]*\];?)(?=\n|$)",
        re.M,
    )
    source = declaration_pattern.sub(
        lambda match: match.group(1) + "const items = " + register(match.group(2)) + ";",
        source,
    )
    source = STATIC_ARRAY_PATTERN.sub(
        lambda match: register(match.group(1)) + ".includes(" + match.group(2) + ")",
        source,
    )

    if not arrays:
        return source
    declarations = ["const %s = %s;" % (names[key], literal) for key, literal in arrays.items()]
    if marker_present:
        return source.replace(ARRAY_MARKER, ARRAY_MARKER + "\n" + "\n".join(declarations), 1)

    anchor = "const url = $request.url;"
    if source.count(anchor) != 1:
        raise ValueError("Amap static array insertion anchor changed")
    return source.replace(anchor, anchor + "\n" + ARRAY_MARKER + "\n" + "\n".join(declarations), 1)



def compact_search_suggestions_in_place(source):
    start = 'if (url.includes("/shield/search_poi/sug")) {'
    end = '} else if (url.includes("/shield/search_poi/tips_operation_location")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Amap search suggestion block boundary drift")
    i = source.index(start)
    j = source.index(end, i + len(start))
    replacement = "if (url.includes(\"/shield/search_poi/sug\")) {\n  if (Array.isArray(obj?.tip_list) && obj.tip_list.length > 0) {\n    compactInPlace(obj.tip_list, item =>\n      !AMAP_STATIC_ITEMS_10.includes(item?.tip?.datatype_spec) &&\n      !AMAP_STATIC_ITEMS_11.includes(item?.tip?.result_type) &&\n      !AMAP_STATIC_ITEMS_12.includes(item?.tip?.task_tag)\n    );\n  } else if (Array.isArray(obj?.city_list) && obj.city_list.length > 0) {\n    for (const city of obj.city_list) {\n      if (Array.isArray(city?.tip_list) && city.tip_list.length > 0) {\n        compactInPlace(city.tip_list, item =>\n          !AMAP_STATIC_ITEMS_10.includes(item?.tip?.datatype_spec) &&\n          !AMAP_STATIC_ITEMS_13.includes(item?.tip?.result_type)\n        );\n      }\n    }\n  }"
    return source[:i] + replacement + "\n" + source[j:]

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(GUARD_MARKER) != 1:
            raise ValueError("Amap optimizer markers are inconsistent")
        if ".filter(" in source or "function compactInPlace(items, keep)" not in source:
            raise ValueError("Amap optimized runtime has drifted")
        return hoist_static_arrays(compact_search_suggestions_in_place(source))
    body_guard = "if (!$response.body) $done({});"
    if source.count(body_guard) != 1:
        raise ValueError("Amap empty-body guard anchor changed")
    source = source.replace(body_guard, "if (!$response.body) {\n  $done({});\n} else {", 1)
    url_anchor = "const url = $request.url;"
    if source.count(url_anchor) != 1:
        raise ValueError("Amap URL anchor changed")
    source = source.replace(url_anchor, url_anchor + "\n" + HELPER, 1)
    parse_anchor = "let obj = JSON.parse($response.body);"
    if source.count(parse_anchor) != 1:
        raise ValueError("Amap JSON.parse anchor changed")
    source = source.replace(parse_anchor, ROUTE_GUARD + parse_anchor, 1)
    end_anchor = "\n$done({body: JSON.stringify(obj)});"
    if source.count(end_anchor) != 1:
        raise ValueError("Amap completion anchor changed")
    source = source.replace(end_anchor, end_anchor + "\n}\n}", 1)
    matches = list(FILTER_ASSIGNMENT.finditer(source))
    if len(matches) != 11:
        raise ValueError("Amap filter inventory changed: expected 11, got %d" % len(matches))
    source = FILTER_ASSIGNMENT.sub(lambda match: "compactInPlace(%s, " % match.group(1), source)
    if re.search(r"\.filter\s*\(", source):
        raise ValueError("Amap allocating Array.filter remains")
    if source.count("compactInPlace(") != 12:
        raise ValueError("Amap in-place compaction call inventory drift")
    source = hoist_static_arrays(compact_search_suggestions_in_place(source))
    return MARKER + commit + "\n" + source

def rewrite_plugin(plugin):
    local_count, remote_count = plugin.count(LOCAL), plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote Amap R-Store script URLs")
    if local_count:
        if local_count != 14:
            raise ValueError("Amap local trigger inventory changed: expected 14, got %d" % local_count)
        return plugin
    if remote_count != 14:
        raise ValueError("Amap trigger inventory changed: expected 14, got %d" % remote_count)
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != 14:
        raise ValueError("Amap local trigger migration incomplete")
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
        print("Optimized Amap R-Store handler: %s (%d bytes)" % (args.output, len(result)))
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Migrated all fourteen Amap R-Store response hooks to the local handler")
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")

if __name__ == "__main__":
    main()
