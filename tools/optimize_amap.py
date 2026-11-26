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
SCALAR_MARKER = "// loon-change: Amap scalar membership hot loops v1"
TRACKING_MARKER = "// loon-change: Amap mutation-aware lazy serialization v1"
DYNAMIC_MATCHER_MARKER = "// loon-change: Amap shared dynamic ad matcher v1"
ROUTE_INFO_MARKER = "// loon-change: Amap routeInfo cached nested references v1"
ROUTE_PLAN_MARKER = "// loon-change: Amap routePlan cached nested references v1"
COMPACTION_MARKER = "// loon-change: Amap specialized in-place compaction v1"
DYNAMIC_MATCHER_LITERAL = "/ads-\\d+/.test(i?.dynamic_id_s)"
DYNAMIC_MATCHER_CALL = "AMAP_AD_DYNAMIC_ID.test(i?.dynamic_id_s)"
DYNAMIC_MATCHER_ITEM_LITERAL = "/ads-\\d+/.test(item?.dynamic_id_s)"
DYNAMIC_MATCHER_ITEM_CALL = "AMAP_AD_DYNAMIC_ID.test(item?.dynamic_id_s)"
TRACKING_HELPER = """// loon-change: Amap mutation-aware lazy serialization v1
let modified = false;
function sameValue(current, next) {
  if (Object.is(current, next)) return true;
  if (Array.isArray(next)) return Array.isArray(current) && current.length === next.length && next.length === 0;
  if (!next || typeof next !== "object" || !current || typeof current !== "object" || Array.isArray(current)) return false;
  let count = 0;
  for (const key in next) {
    if (!Object.prototype.hasOwnProperty.call(next, key)) continue;
    count++;
    if (!Object.prototype.hasOwnProperty.call(current, key) || !Object.is(current[key], next[key])) return false;
  }
  for (const key in current) {
    if (Object.prototype.hasOwnProperty.call(current, key)) count--;
  }
  return count === 0;
}
function setIfDifferent(target, key, value) {
  if (sameValue(target[key], value)) return false;
  target[key] = value;
  modified = true;
  return true;
}
function deleteIfPresent(target, key) {
  if (!Object.prototype.hasOwnProperty.call(target, key)) return false;
  delete target[key];
  modified = true;
  return true;
}
"""
HELPER = """function compactInPlace(items, mode) {
  const length = items.length;
  let write = 0;

  if (mode === "withoutSchema") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (!item || !Object.prototype.hasOwnProperty.call(item, "schema")) {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "homeCards") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const key = item?.dataKey;
      if (key === "ContinueNavigationCard" || key === "FrequentLocation" || key === "LoginCard") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "findCar") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item?.dataKey === "FindCarVirtualCard") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "dynamicAds") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (!AMAP_AD_DYNAMIC_ID.test(item?.dynamic_id_s)) {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "nonMusic") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item?.biz_type !== "music") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "myOrder") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item?.dataKey === "MyOrderCard") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "nearbyModules") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item === "head" || item === "search_hot_words" || item === "feed_rec") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "searchContent") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const itemType = item?.item_type;
      if (itemType !== "brandAdCard" && itemType !== "toplist_al") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "suggestions") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const tip = item?.tip;
      if (
        tip?.datatype_spec !== "12" &&
        tip?.result_type !== "ad" &&
        tip?.result_type !== "poi_ad" &&
        tip?.result_type !== "toplist" &&
        tip?.task_tag !== "ad" &&
        tip?.task_tag !== "exct_query_sug_merge_theme" &&
        tip?.task_tag !== "query_sug_merge_theme" &&
        tip?.task_tag !== "sp"
      ) {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "citySuggestions") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const tip = item?.tip;
      if (
        tip?.datatype_spec !== "12" &&
        tip?.result_type !== "ad" &&
        tip?.result_type !== "poi_ad"
      ) {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else {
    return false;
  }

  if (write !== length) {
    items.length = write;
    modified = true;
    return true;
  }
  return false;
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
  url.includes("/sharedtrip/taxi/order_detail_car_tips") ||
  url.includes("/shield/search_bff/hotword") ||
  url.includes("/valueadded/alimama/splash_screen");
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
    marker = "// loon-change: Amap cached suggestion tip access v1"
    start = 'if (url.includes("/shield/search_poi/sug")) {'
    end = '} else if (url.includes("/shield/search_poi/tips_operation_location")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Amap search suggestion block boundary drift")
    if source.count(marker) > 1:
        raise ValueError("Amap cached suggestion marker is duplicated")
    i = source.index(start)
    j = source.index(end, i + len(start))
    prefix = marker + "\n" if marker not in source else ""
    replacement = prefix + """if (url.includes("/shield/search_poi/sug")) {
  if (Array.isArray(obj?.tip_list) && obj.tip_list.length > 0) {
    compactInPlace(obj.tip_list, item => {
      const tip = item?.tip;
      return tip?.datatype_spec !== "12" &&
        tip?.result_type !== "ad" &&
        tip?.result_type !== "poi_ad" &&
        tip?.result_type !== "toplist" &&
        tip?.task_tag !== "ad" &&
        tip?.task_tag !== "exct_query_sug_merge_theme" &&
        tip?.task_tag !== "query_sug_merge_theme" &&
        tip?.task_tag !== "sp";
    });
  } else if (Array.isArray(obj?.city_list) && obj.city_list.length > 0) {
    for (const city of obj.city_list) {
      if (Array.isArray(city?.tip_list) && city.tip_list.length > 0) {
        compactInPlace(city.tip_list, item => {
          const tip = item?.tip;
          return tip?.datatype_spec !== "12" &&
            tip?.result_type !== "ad" &&
            tip?.result_type !== "poi_ad";
        });
      }
    }
  }"""
    return source[:i] + replacement + "\n" + source[j:]


def optimize_compaction_modes(source):
    """Replace callback predicates with mode-specialized direct loops."""
    callback = re.compile(
        r'compactInPlace\(([^,\n]+),\s*(?:\(([A-Za-z_$][\w$]*)\)|([A-Za-z_$][\w$]*))\s*=>\s*([\s\S]*?)\);'
    )
    expected = {
        "withoutSchema": 1,
        "homeCards": 1,
        "findCar": 1,
        "dynamicAds": 4,
        "nonMusic": 1,
        "myOrder": 1,
        "nearbyModules": 1,
        "searchContent": 1,
        "suggestions": 1,
        "citySuggestions": 1,
    }

    def mode_for(predicate):
        if "hasOwnProperty" in predicate and "schema" in predicate:
            return "withoutSchema"
        if "ContinueNavigationCard" in predicate:
            return "homeCards"
        if "FindCarVirtualCard" in predicate:
            return "findCar"
        if "AMAP_AD_DYNAMIC_ID.test" in predicate:
            return "dynamicAds"
        if "biz_type" in predicate and '"music"' in predicate:
            return "nonMusic"
        if "MyOrderCard" in predicate:
            return "myOrder"
        if '"head"' in predicate and "search_hot_words" in predicate and "feed_rec" in predicate:
            return "nearbyModules"
        if "item_type" in predicate and "brandAdCard" in predicate and "toplist_al" in predicate:
            return "searchContent"
        if "task_tag" in predicate and "exct_query_sug_merge_theme" in predicate:
            return "suggestions"
        if "datatype_spec" in predicate and "poi_ad" in predicate and "task_tag" not in predicate:
            return "citySuggestions"
        raise ValueError("Amap compaction predicate is not in the reviewed inventory")

    actual = {name: 0 for name in expected}

    def replace_call(match):
        mode = mode_for(match.group(4))
        actual[mode] += 1
        return 'compactInPlace(%s, "%s");' % (match.group(1).strip(), mode)

    source = callback.sub(replace_call, source)
    if any(actual[name] > expected[name] for name in expected):
        raise ValueError("Amap callback compaction inventory drift: %r" % actual)

    helper_start = "function compactInPlace(items, keep) {"
    helper_end = "function compactInPlace(items, mode) {"
    marker_count = source.count(COMPACTION_MARKER)
    if marker_count > 1:
        raise ValueError("Amap specialized compaction marker is duplicated")
    if helper_start in source:
        if source.count(helper_start) != 1 or marker_count:
            raise ValueError("Amap legacy compaction helper/marker drift")
        start = source.index(helper_start)
        end = source.index("\n}", start) + 2
        source = source[:start] + HELPER.strip() + source[end:]
    elif source.count(helper_end) != 1:
        raise ValueError("Amap specialized compaction helper signature drift")

    if source.count(COMPACTION_MARKER) == 0:
        source = source.replace(helper_end, COMPACTION_MARKER + "\n" + helper_end, 1)
    elif source.count(COMPACTION_MARKER) != 1:
        raise ValueError("Amap specialized compaction marker count drift")

    for name, count in expected.items():
        actual_count = source.count(', "' + name + '")')
        if actual_count != count:
            raise ValueError(
                "Amap specialized mode %s expected %d call(s), found %d"
                % (name, count, actual_count)
            )
    if source.count("compactInPlace(") != 14:
        raise ValueError("Amap specialized compaction call inventory drift")
    if re.search(
        r'compactInPlace\([^,\n]+,\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>',
        source,
    ):
        raise ValueError("Amap per-item compaction callback remains")
    if source.count(COMPACTION_MARKER) != 1 or source.count(helper_end) != 1:
        raise ValueError("Amap specialized compaction marker/signature drift")
    return source


def optimize_scalar_membership(source):
    if source.count(SCALAR_MARKER) > 1:
        raise ValueError("Amap scalar membership marker is duplicated")
    if SCALAR_MARKER not in source:
        nearby_old = """  const items = AMAP_STATIC_ITEMS_06;
  if (obj?.data?.modules?.length > 0) {
    if (obj?.data?.modules?.length > 0) {
      compactInPlace(obj.data.modules, (i) => items?.includes(i));
    }
  }"""
        nearby_new = """  if (Array.isArray(obj?.data?.modules) && obj.data.modules.length > 0) {
    compactInPlace(obj.data.modules, (i) =>
      i === "head" || i === "search_hot_words" || i === "feed_rec"
    );
  }"""
        if source.count(nearby_old) != 1:
            raise ValueError("Amap nearby modules membership block changed")
        source = source.replace(nearby_old, nearby_new, 1)

        brand_old = "compactInPlace(list.content, (i) => !AMAP_STATIC_ITEMS_09.includes(i?.item_type));"
        brand_new = """compactInPlace(list.content, (i) => {
          const itemType = i?.item_type;
          return itemType !== "brandAdCard" && itemType !== "toplist_al";
        });"""
        if source.count(brand_old) != 1:
            raise ValueError("Amap search card membership block changed")
        source = source.replace(brand_old, brand_new, 1)

        for name, literal in (
            ("AMAP_STATIC_ITEMS_06", r'\["head", "search_hot_words", "feed_rec"\]'),
            ("AMAP_STATIC_ITEMS_09", r'\["brandAdCard", "toplist_al"\]'),
            ("AMAP_STATIC_ITEMS_10", r'\["12"\]'),
            ("AMAP_STATIC_ITEMS_11", r'\["ad", "poi_ad", "toplist"\]'),
            ("AMAP_STATIC_ITEMS_12", r'\["ad", "exct_query_sug_merge_theme", "query_sug_merge_theme", "sp"\]'),
            ("AMAP_STATIC_ITEMS_13", r'\["ad", "poi_ad"\]'),
        ):
            pattern = re.compile(r"^const " + name + r"\s*=\s*" + literal + r";*\s*$", re.M)
            if len(pattern.findall(source)) != 1:
                raise ValueError("Amap unused membership array changed: " + name)
            source = pattern.sub("", source, count=1)

        anchors = (
            "function compactInPlace(items, mode) {",
            "function compactInPlace(items, keep) {",
        )
        anchor = next((value for value in anchors if source.count(value) == 1), None)
        if anchor is None:
            raise ValueError("Amap scalar membership marker insertion anchor changed")
        source = source.replace(anchor, SCALAR_MARKER + "\n" + anchor, 1)

    if source.count(SCALAR_MARKER) != 1:
        raise ValueError("Amap scalar membership marker count drift")
    forbidden = (
        "AMAP_STATIC_ITEMS_06", "AMAP_STATIC_ITEMS_09",
        "AMAP_STATIC_ITEMS_10", "AMAP_STATIC_ITEMS_11",
        "AMAP_STATIC_ITEMS_12", "AMAP_STATIC_ITEMS_13",
        ".includes(item?.tip?.", ".includes(i?.item_type)",
        "items?.includes(i)",
    )
    if any(value in source for value in forbidden):
        raise ValueError("Amap scalar membership optimization is incomplete")
    nearby_predicates = (
        'i === "head" || i === "search_hot_words" || i === "feed_rec"',
        'item === "head" || item === "search_hot_words" || item === "feed_rec"',
    )
    if not any(predicate in source for predicate in nearby_predicates):
        raise ValueError("Amap nearby scalar predicate is missing")
    card_pattern = re.compile(
        r'compactInPlace\(list\.content, \((\w+)\) =>\s*\1\?\.item_type !== "brandAdCard" && \1\?\.item_type !== "toplist_al"\s*\);'
    )
    source, card_rewrites = card_pattern.subn(
        lambda match: (
            "compactInPlace(list.content, (" + match.group(1) + ") => {\n"
            "          const itemType = " + match.group(1) + "?.item_type;\n"
            "          return itemType !== \"brandAdCard\" && itemType !== \"toplist_al\";\n"
            "        });"
        ),
        source,
    )
    if card_rewrites > 1:
        raise ValueError("Amap search card itemType cache anchor is duplicated")
    if not re.search(r"const itemType = \w+\?\.item_type;", source):
        raise ValueError("Amap search card itemType cache is missing")
    if re.search(r"\b\w+\?\.item_type !== \"(?:brandAdCard|toplist_al)\"", source):
        raise ValueError("Amap repeated search card itemType access remains")
    return source


def optimize_shared_dynamic_ad_matcher(source):
    if source.count(DYNAMIC_MATCHER_MARKER) > 1:
        raise ValueError("Amap shared dynamic matcher marker is duplicated")
    specialized = "function compactInPlace(items, mode) {" in source

    if DYNAMIC_MATCHER_MARKER not in source:
        old_literal_count = source.count(DYNAMIC_MATCHER_LITERAL)
        item_literal_count = source.count(DYNAMIC_MATCHER_ITEM_LITERAL)
        if old_literal_count == 4:
            source = source.replace(DYNAMIC_MATCHER_LITERAL, DYNAMIC_MATCHER_CALL)
        elif specialized and old_literal_count == 0 and item_literal_count == 1:
            source = source.replace(DYNAMIC_MATCHER_ITEM_LITERAL, DYNAMIC_MATCHER_ITEM_CALL)
        else:
            raise ValueError("Amap dynamic ad matcher inventory changed")

        anchors = (
            "function compactInPlace(items, mode) {",
            "function compactInPlace(items, keep) {",
        )
        anchor = next((value for value in anchors if source.count(value) == 1), None)
        if anchor is None:
            raise ValueError("Amap shared matcher insertion anchor changed")
        source = source.replace(
            anchor,
            DYNAMIC_MATCHER_MARKER + "\nconst AMAP_AD_DYNAMIC_ID = /ads-\\d+/;\n\n" + anchor,
            1,
        )

    if source.count(DYNAMIC_MATCHER_MARKER) != 1:
        raise ValueError("Amap shared dynamic matcher marker count drift")
    if source.count(r"const AMAP_AD_DYNAMIC_ID = /ads-\d+/;") != 1:
        raise ValueError("Amap shared dynamic matcher declaration drift")

    if specialized:
        if source.count(DYNAMIC_MATCHER_ITEM_CALL) != 1 or DYNAMIC_MATCHER_ITEM_LITERAL in source:
            raise ValueError("Amap specialized dynamic matcher helper drift")
        if source.count(DYNAMIC_MATCHER_CALL) not in (0, 4) or DYNAMIC_MATCHER_LITERAL in source:
            raise ValueError("Amap upstream dynamic matcher transition drift")
    else:
        if source.count(DYNAMIC_MATCHER_CALL) != 4 or DYNAMIC_MATCHER_LITERAL in source:
            raise ValueError("Amap shared dynamic matcher call inventory drift")
    return source


def optimize_route_info_cached_references(source):
    if source.count(ROUTE_INFO_MARKER) > 1:
        raise ValueError("Amap routeInfo cache marker is duplicated")
    start = '} else if (url.includes("/perception/drive/routeInfo")) {'
    end = '} else if (url.includes("/perception/drive/routePlan")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Amap routeInfo branch boundary drift")
    i = source.index(start)
    j = source.index(end, i + len(start))
    block = source[i:j]
    if ROUTE_INFO_MARKER in block:
        required = (
            "const routeInfoData = obj?.data;",
            "const routeInfoFrontEnd = routeInfoData?.front_end;",
            "const routeInfoEvents = routeInfoData?.tbt?.event;",
            "const routeInfoGuideTips = routeInfoFrontEnd?.guide_tips;",
            "const routeInfoDownloads = routeInfoFrontEnd?.download;",
        )
        if any(value not in block for value in required):
            raise ValueError("Amap routeInfo cached reference declarations drift")
        return source

    replacements = (
        ("obj?.data?.tbt?.event?.length", "routeInfoEvents?.length"),
        ("obj.data.tbt.event", "routeInfoEvents"),
        ("obj?.data?.front_end?.guide_tips?.length", "routeInfoGuideTips?.length"),
        ("obj.data.front_end.guide_tips", "routeInfoGuideTips"),
        ("obj?.data?.front_end?.download?.length", "routeInfoDownloads?.length"),
        ("obj.data.front_end.download", "routeInfoDownloads"),
        ("obj?.data?.front_end", "routeInfoFrontEnd"),
        ("obj.data.front_end", "routeInfoFrontEnd"),
    )
    for old, new in replacements:
        block = block.replace(old, new)

    required_accesses = (
        "routeInfoEvents?.length", "compactInPlace(routeInfoEvents,",
        "routeInfoFrontEnd", "routeInfoGuideTips", "routeInfoDownloads",
    )
    if any(value not in block for value in required_accesses):
        raise ValueError("Amap routeInfo nested access inventory changed")
    declaration = """  // loon-change: Amap routeInfo cached nested references v1
  const routeInfoData = obj?.data;
  const routeInfoFrontEnd = routeInfoData?.front_end;
  const routeInfoEvents = routeInfoData?.tbt?.event;
  const routeInfoGuideTips = routeInfoFrontEnd?.guide_tips;
  const routeInfoDownloads = routeInfoFrontEnd?.download;"""
    comment = "  // 导航详情页"
    if block.count(comment) != 1:
        raise ValueError("Amap routeInfo declaration anchor changed")
    block = block.replace(comment, comment + "\n" + declaration, 1)
    return source[:i] + block + source[j:]


def optimize_route_plan_cached_references(source):
    if source.count(ROUTE_PLAN_MARKER) > 1:
        raise ValueError("Amap routePlan cache marker is duplicated")
    start = '} else if (url.includes("/perception/drive/routePlan")) {'
    end = '} else if (url.includes("/promotion-web/resource")) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("Amap routePlan branch boundary drift")
    i = source.index(start)
    j = source.index(end, i + len(start))
    block = source[i:j]
    if ROUTE_PLAN_MARKER in block:
        required = (
            "const routePlanData = obj?.data;",
            "const routePlanFrontEnd = routePlanData?.front_end;",
            "const routePlanEvents = routePlanData?.tbt?.event;",
            "const routePlanDownloads = routePlanFrontEnd?.download;",
        )
        if any(value not in block for value in required):
            raise ValueError("Amap routePlan cached reference declarations drift")
        return source
    replacements = (
        ("obj?.data?.tbt?.event?.length", "routePlanEvents?.length"),
        ("obj.data.tbt.event", "routePlanEvents"),
        ("obj?.data?.front_end?.download?.length", "routePlanDownloads?.length"),
        ("obj.data.front_end.download", "routePlanDownloads"),
        ("obj?.data?.front_end", "routePlanFrontEnd"),
        ("obj.data.front_end", "routePlanFrontEnd"),
    )
    for old, new in replacements:
        block = block.replace(old, new)
    required_accesses = (
        "routePlanEvents?.length", "compactInPlace(routePlanEvents,",
        "routePlanFrontEnd", "routePlanDownloads",
    )
    if any(value not in block for value in required_accesses):
        raise ValueError("Amap routePlan nested access inventory changed")
    declaration = """  // loon-change: Amap routePlan cached nested references v1
  const routePlanData = obj?.data;
  const routePlanFrontEnd = routePlanData?.front_end;
  const routePlanEvents = routePlanData?.tbt?.event;
  const routePlanDownloads = routePlanFrontEnd?.download;"""
    comment = "  // 路线规划页"
    if block.count(comment) != 1:
        raise ValueError("Amap routePlan declaration anchor changed")
    block = block.replace(comment, comment + "\n" + declaration, 1)
    return source[:i] + block + source[j:]

def repair_supported_route_guard(source):
    pattern = re.compile(
        re.escape(GUARD_MARKER)
        + r"\nconst shouldProcess =[\s\S]*?if \(!shouldProcess\) \{\n  \$done\(\{\}\);\n\} else \{\n"
    )
    if len(pattern.findall(source)) != 1:
        raise ValueError("Amap supported-route guard structure changed")
    return pattern.sub(lambda _: ROUTE_GUARD, source, count=1)


def _split_member_path(path):
    match = re.match(r"^(.*)(?:\.([A-Za-z_$][\w$]*)|\[([^\]]+)\])$", path)
    if not match or not match.group(1):
        raise ValueError("Amap mutation target is unsupported: " + path)
    key = '"' + match.group(2) + '"' if match.group(2) else match.group(3).strip()
    return match.group(1), key


def instrument_mutations(source):
    if source.count(TRACKING_MARKER) > 1:
        raise ValueError("Amap mutation tracking marker is duplicated")
    was_instrumented = TRACKING_MARKER in source
    if not was_instrumented:
        url_anchor = "const url = $request.url;"
        if source.count(url_anchor) != 1:
            raise ValueError("Amap mutation tracking insertion anchor changed")
        source = source.replace(url_anchor, url_anchor + "\n" + TRACKING_HELPER, 1)

    compact_pattern = re.compile(r"function compactInPlace\(items, (?:keep|mode)\) \{[\s\S]*?\n\}")
    if len(compact_pattern.findall(source)) != 1:
        raise ValueError("Amap compaction helper structure changed")
    source = compact_pattern.sub(lambda _: HELPER.rstrip(), source, count=1)

    parse_anchor = "let obj = JSON.parse($response.body);"
    old_done = "$done({body: JSON.stringify(obj)});"
    lazy_done = "$done(modified ? {body: JSON.stringify(obj)} : {});"
    if source.count(parse_anchor) != 1:
        raise ValueError("Amap mutation tracking parse anchor changed")
    if source.count(old_done) + source.count(lazy_done) != 1:
        raise ValueError("Amap mutation tracking completion anchor changed")
    start = source.index(parse_anchor)
    done = old_done if old_done in source else lazy_done
    end = source.index(done, start)
    body = source[start:end]
    delete_count = 0
    set_count = 0
    rewritten = []
    for raw_line in body.splitlines(keepends=True):
        line = raw_line[:-1] if raw_line.endswith("\n") else raw_line
        ending = "\n" if raw_line.endswith("\n") else ""
        match = re.match(r"^(\s*)delete\s+(.+?);(\s*(?://.*)?)$", line)
        if match:
            parent, key = _split_member_path(match.group(2))
            rewritten.append(match.group(1) + "deleteIfPresent(" + parent + ", " + key + ");" + match.group(3) + ending)
            delete_count += 1
            continue
        match = re.match(
            r"^(\s*)([A-Za-z_$][\w$]*(?:(?:\.[A-Za-z_$][\w$]*)|(?:\[[^\]]+\]))*)\s*=\s*(.+?);(\s*(?://.*)?)$",
            line,
        )
        if match:
            parent, key = _split_member_path(match.group(2))
            rewritten.append(
                match.group(1) + "setIfDifferent(" + parent + ", " + key + ", "
                + match.group(3) + ");" + match.group(4) + ending
            )
            set_count += 1
            continue
        rewritten.append(raw_line)
    body = "".join(rewritten)
    if not was_instrumented and delete_count + set_count < 50:
        raise ValueError(
            "Amap mutation inventory changed: delete=%d set=%d"
            % (delete_count, set_count)
        )
    if re.search(r"^\s*delete\s+", body, re.M):
        raise ValueError("Untracked Amap delete remains")
    # Handler mutations are rooted in the parsed response object or its item aliases.
    if re.search(r"^\s*(?:obj|item|list|poi|hookData)\b.*(?:\.|\[).*\s=(?!=)", body, re.M):
        raise ValueError("Untracked Amap response assignment remains")

    source = source[:start] + body + source[end:]
    if done == old_done:
        source = source.replace(old_done, lazy_done, 1)
    return source

def optimize_source(source, commit="unknown"):
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count(GUARD_MARKER) != 1:
            raise ValueError("Amap optimizer markers are inconsistent")
        source = repair_supported_route_guard(source)
        source = optimize_shared_dynamic_ad_matcher(optimize_scalar_membership(compact_search_suggestions_in_place(hoist_static_arrays(source))))
        source = optimize_route_info_cached_references(source)
        source = optimize_route_plan_cached_references(source)
        source = instrument_mutations(source)
        source = compact_search_suggestions_in_place(hoist_static_arrays(source))
        source = optimize_compaction_modes(source)
        if ".filter(" in source or "function compactInPlace(items, mode)" not in source:
            raise ValueError("Amap optimized runtime has drifted")
        return source
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
    source = compact_search_suggestions_in_place(hoist_static_arrays(source))
    source = optimize_scalar_membership(source)
    source = optimize_shared_dynamic_ad_matcher(source)
    source = optimize_route_info_cached_references(source)
    source = optimize_route_plan_cached_references(source)
    source = instrument_mutations(source)
    source = optimize_compaction_modes(source)
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
