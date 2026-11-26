#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize the active Didi response script and pin its plugin triggers locally."""
import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/didi.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/didi/didi.js"
LEGACY_MARKER = "// loon-change: Didi response compaction optimization v1; upstream zirawell/R-Store@"
MARKER = "// loon-change: Didi response compaction and lazy serialization optimization v2; upstream zirawell/R-Store@"
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

DIDI_MODE_MARKER = "// loon-change: Didi hot-loop specialized property loops v2;"
DIDI_WALLET_PROPERTY_CACHE_MARKER = "// loon-change: Didi wallet nested property cache v1"
DIDI_MODE_HELPER = r"""// loon-change: Didi hot-loop specialized property loops v2;
function compactDidiByField(items, mode) {
  const length = items.length;
  let write = 0;

  if (mode === "scene") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item.text !== "优惠商城") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "sceneId") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item !== "scene_coupon_mall") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "nav") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item.nav_id;
      if (value === "dache_anycar" || value === "driverservice" || value === "bike") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "bottomNav") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item.id;
      if (value === "v6x_home" || value === "user_center") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletItem") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item.title === "优惠券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "walletBottom") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const value = item.title;
      if (value === "省钱套餐" || value === "天天神券") {
        if (write !== read) items[write] = item;
        write++;
      }
    }
  } else if (mode === "card") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const title = item.title;
      if (title === "天天领福利" || title === "金融服务" || title === "更多服务" ||
          title === "企业服务" || title === "安全中心") {
        continue;
      }
      if (item.tag === "wallet") {
        if (Array.isArray(item.items) && item.items.length > 0) {
          compactDidiByField(item.items, "walletItem");
        }
        if (item.card_type === 4 && Array.isArray(item.bottom_items) && item.bottom_items.length > 0) {
          compactDidiByField(item.bottom_items, "walletBottom");
        }
      }
      if (write !== read) items[write] = item;
      write++;
    }
  } else {
    return items;
  }

  if (write !== length) {
    items.length = write;
    modified = true;
  }
  return items;
}"""

FILTER_ASSIGNMENT = re.compile(
    r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\1\.filter\s*\("
)


def optimize_lazy_serialization(source):
    if "let modified = false;" in source:
        if "$done(modified ? {body: JSON.stringify(obj)} : {});" not in source:
            raise ValueError("Didi lazy serialization completion guard is missing")
        return source
    url_anchor = "const url = $request.url;"
    helper_return = "  items.length = write;\n  return items;"
    completion = "$done({body: JSON.stringify(obj)});"
    if source.count(url_anchor) != 1 or source.count(helper_return) != 1 or source.count(completion) != 1:
        raise ValueError("Didi lazy serialization anchors changed; refusing optimization")
    source = source.replace(url_anchor, url_anchor + "\nlet modified = false;", 1)
    source = source.replace(helper_return, "  items.length = write;\n  if (write !== length) modified = true;\n  return items;", 1)
    old_for_each = """    obj.data.show_data.forEach((block) => {
      if (block.scene_ids instanceof Array) {
        compactInPlace(block.scene_ids, id => id !== "scene_coupon_mall");
      }
    });"""
    new_for_each = """    const showData = obj.data.show_data;
    for (let read = 0; read < showData.length; read++) {
      const block = showData[read];
      if (block.scene_ids instanceof Array) {
        compactInPlace(block.scene_ids, id => id !== "scene_coupon_mall");
      }
    }"""
    if source.count(old_for_each) == 1:
        source = source.replace(old_for_each, new_for_each, 1)
    splice = "    obj.data.disorder_cards.top_banner_card.data.splice(0, 1);"
    if source.count(splice) > 1:
        raise ValueError("Didi banner removal inventory changed; refusing optimization")
    if source.count(splice) == 1:
        source = source.replace(splice, splice + "\n    modified = true;", 1)
    source = source.replace(completion, "$done(modified ? {body: JSON.stringify(obj)} : {});", 1)
    return source




def optimize_didi_predicates(source):
    """Hoist each Didi list mode dispatch outside its per-item compaction loop."""
    required = (
        DIDI_MODE_MARKER,
        'if (mode === "scene") {',
        'else if (mode === "sceneId") {',
        'else if (mode === "nav") {',
        'else if (mode === "bottomNav") {',
        'else if (mode === "walletItem") {',
        'else if (mode === "walletBottom") {',
        'else if (mode === "card") {',
    )

    def validate(result):
        if any(token not in result for token in required):
            raise ValueError("Didi mode-dispatch optimization is incomplete")
        if ('compactDidiByField(responseData.cards, "card");' not in result and
                'compactDidiByField(obj.data.cards, "card");' not in result):
            raise ValueError("Didi mode-dispatch card compaction is incomplete")
        if result.count("for (let read = 0; read < length; read++)") != 7:
            raise ValueError("Didi specialized loop inventory changed")
        if result.count('mode === "') != 7:
            raise ValueError("Didi per-item mode dispatch inventory changed")
        if "item[field]" in result or "compactDidiByField(items, field, mode)" in result:
            raise ValueError("Didi dynamic property access remains in specialized loops")
        if result.count("compactDidiByField(") != 8:
            raise ValueError("Didi specialized callsite inventory changed")
        return result

    if DIDI_MODE_MARKER in source:
        return validate(source)

    legacy_mode_marker = "// loon-change: Didi hot-loop mode dispatch v1;"
    if legacy_mode_marker in source:
        source = source.replace(legacy_mode_marker, DIDI_MODE_MARKER, 1)

    # Upgrade the already-specialized v2 local snapshot without changing its
    # route, cleanup predicates, or response completion guard.
    if "function compactDidiByField(items, field, mode)" in source:
        helper_start = "function compactDidiByField(items, field, mode) {"
        helper_end = "\n}\nif (!$response.body)"
        start = source.index(helper_start)
        end = source.index(helper_end, start)
        source = source[:start] + DIDI_MODE_HELPER.rstrip() + "\n" + source[end + 3:]
        source, count = re.subn(
            r'compactDidiByField\(([^,\n]+),\s*"[^"]+",\s*"([^"]+)"\)',
            r'compactDidiByField(\1, "\2")',
            source,
        )
        if count != 7:
            raise ValueError("Didi specialized callsite inventory changed during v2 upgrade")
        return validate(source)

    helper_start = "function compactInPlace(items, keep) {"
    helper_end = "\n}\n\nif (!$response.body)"
    if source.count(helper_start) != 1:
        raise ValueError("Didi compaction helper changed; refusing specialized rewrite")
    start = source.index(helper_start)
    end = source.index(helper_end, start)
    source = source[:start] + DIDI_MODE_HELPER.rstrip() + "\n\n" + source[end + 3:]

    replacements = [
        ('compactInPlace(obj.data.scene_list, item => item.text !== "优惠商城");',
         'compactDidiByField(obj.data.scene_list, "scene");'),
        ('compactInPlace(block.scene_ids, id => id !== "scene_coupon_mall");',
         'compactDidiByField(block.scene_ids, "sceneId");'),
        ("  const keepNavIds = ['dache_anycar', 'driverservice', 'bike'];\n", ""),
        ('compactInPlace(obj.data.order_cards.nav_list_card.data, item => keepNavIds.includes(item.nav_id));',
         'compactDidiByField(obj.data.order_cards.nav_list_card.data, "nav");'),
        ("  const keepBottomNavIds = ['v6x_home', 'user_center'];\n", ""),
        ('compactInPlace(obj.data.disorder_cards.bottom_nav_list.data, item => keepBottomNavIds.includes(item.id));',
         'compactDidiByField(obj.data.disorder_cards.bottom_nav_list.data, "bottomNav");'),
        ("  const excludedTitles = ['天天领福利', '金融服务', '更多服务', '企业服务', '安全中心'];\n\n", ""),
        ('compactInPlace(obj.data.cards, card => {\n      if (excludedTitles.includes(card.title)) return false;\n      if (card.tag === "wallet") {\n        if (card.items) {\n          compactInPlace(card.items, item => item.title === "优惠券");\n        }\n        if (card.card_type === 4 && card.bottom_items) {\n          compactInPlace(card.bottom_items, item =>\n              item.title === "省钱套餐" || item.title === "天天神券"\n          );\n        }\n      }\n      return true;\n    });',
         'compactDidiByField(obj.data.cards, "card");'),
    ]
    for old, new in replacements:
        if old not in source:
            raise ValueError("Didi specialized compaction pattern missing: " + old[:72])
        source = source.replace(old, new, 1)

    if re.search(r"compactInPlace\s*\(|keepNavIds|keepBottomNavIds|excludedTitles", source):
        raise ValueError("Didi per-response filter callbacks or allowlist arrays remain")
    if re.search(r"\.filter\s*\(", source):
        raise ValueError("Didi allocating filter remains after mode specialization")
    source, count = re.subn(
        r'compactDidiByField\(([^,\n]+),\s*"[^"]+",\s*"([^"]+)"\)',
        r'compactDidiByField(\1, "\2")',
        source,
    )
    if count not in (0, 7):
        raise ValueError("Didi specialized callsite inventory changed during upstream generation")
    return validate(source)


def optimize_preparse_route_guard(source):
    """Skip unrelated Didi response bodies before JSON.parse."""
    marker = "// loon-change: Didi pre-parse supported-route guard v1"
    routes = (
        'url.includes("/other/pGetSceneList")',
        '(url.includes("/homepage/v") && url.includes("/core"))',
        'url.includes("/ota/na/yuantu/infoList")',
        'url.includes("/usercenter/me")',
    )
    if marker in source:
        marker_at = source.index(marker)
        parse_at = source.find("JSON.parse($response.body)")
        if "// loon-change: Didi route dispatch cache v1" in source:
            cached_routes = (
                "const isSceneList = url.includes(\"/other/pGetSceneList\");",
                "const isHomepageCore = url.includes(\"/homepage/v\") && url.includes(\"/core\");",
                "const isInfoList = url.includes(\"/ota/na/yuantu/infoList\");",
                "const isUserCenter = url.includes(\"/usercenter/me\");",
                "const shouldProcess = isSceneList || isHomepageCore || isInfoList || isUserCenter;",
            )
            valid_routes = all(route in source for route in cached_routes)
        else:
            valid_routes = all(route in source for route in routes)
        if parse_at < 0 or marker_at > parse_at or not valid_routes:
            raise ValueError("Didi pre-parse route guard is incomplete or misplaced")
        return source

    parse_line = "let obj = JSON.parse($response.body);"
    if source.count(parse_line) != 1:
        raise ValueError("Didi JSON parse anchor changed; refusing pre-parse guard")
    guard = (
        marker + "\nconst shouldProcess =\n  " + " ||\n  ".join(routes) +
        ";\nif (!shouldProcess) {\n  $done({});\n} else {\n  " + parse_line
    )
    source = source.replace(parse_line, guard, 1)
    if not source.rstrip().endswith("}"):
        raise ValueError("Didi response handler closing brace missing")
    return source.rstrip() + "\n}\n"

def optimize_didi_route_dispatch_cache(source):
    """Evaluate each supported Didi URL route predicate once and reuse it."""
    marker = "// loon-change: Didi route dispatch cache v1"
    replacements = (
        ('if (url.includes("/other/pGetSceneList")) {', "if (isSceneList) {"),
        ('if (url.includes("/homepage/v") && url.includes("/core")) {', "if (isHomepageCore) {"),
        ('if (url.includes("/ota/na/yuantu/infoList")) {', "if (isInfoList) {"),
        ('if (url.includes("/usercenter/me")) {', "if (isUserCenter) {"),
    )
    if marker in source:
        required = (
            'const isSceneList = url.includes("/other/pGetSceneList");',
            'const isHomepageCore = url.includes("/homepage/v") && url.includes("/core");',
            'const isInfoList = url.includes("/ota/na/yuantu/infoList");',
            'const isUserCenter = url.includes("/usercenter/me");',
            "if (isSceneList) {", "if (isHomepageCore) {",
            "if (isInfoList) {", "if (isUserCenter) {",
        )
        if any(token not in source for token in required):
            raise ValueError("Didi cached route dispatch structure is incomplete")
        if any(source.count(token) != 1 for token in required[:4]):
            raise ValueError("Didi route predicates are repeated")
        return source
    counts = [source.count(old) for old, _ in replacements]
    # Compact optimizer fixtures omit response dispatch branches; preserve them without adding a route marker.
    if counts == [0, 0, 0, 0]:
        return source
    if counts != [1, 1, 1, 1]:
        raise ValueError("Didi route branch anchor changed; refusing route cache rewrite")
    old_guard = '''// loon-change: Didi pre-parse supported-route guard v1
const shouldProcess =
  url.includes("/other/pGetSceneList") ||
  (url.includes("/homepage/v") && url.includes("/core")) ||
  url.includes("/ota/na/yuantu/infoList") ||
  url.includes("/usercenter/me");'''
    new_guard = '''// loon-change: Didi pre-parse supported-route guard v1
// loon-change: Didi route dispatch cache v1
const isSceneList = url.includes("/other/pGetSceneList");
const isHomepageCore = url.includes("/homepage/v") && url.includes("/core");
const isInfoList = url.includes("/ota/na/yuantu/infoList");
const isUserCenter = url.includes("/usercenter/me");
const shouldProcess = isSceneList || isHomepageCore || isInfoList || isUserCenter;'''
    if source.count(old_guard) != 1:
        raise ValueError("Didi route guard anchor changed; refusing route cache rewrite")
    source = source.replace(old_guard, new_guard, 1)
    for old, new in replacements:
        source = source.replace(old, new, 1)
    return source

def optimize_wallet_nested_property_cache(source):
    """Cache nested wallet array references instead of re-reading card properties."""
    marker = DIDI_WALLET_PROPERTY_CACHE_MARKER
    old = """      if (item.tag === "wallet") {
        if (Array.isArray(item.items) && item.items.length > 0) {
          compactDidiByField(item.items, "walletItem");
        }
        if (item.card_type === 4 && Array.isArray(item.bottom_items) && item.bottom_items.length > 0) {
          compactDidiByField(item.bottom_items, "walletBottom");
        }
      }"""
    new = """      if (item.tag === "wallet") {
        // loon-change: Didi wallet nested property cache v1
        const walletItems = item.items;
        if (Array.isArray(walletItems) && walletItems.length > 0) {
          compactDidiByField(walletItems, "walletItem");
        }
        if (item.card_type === 4) {
          const walletBottomItems = item.bottom_items;
          if (Array.isArray(walletBottomItems) && walletBottomItems.length > 0) {
            compactDidiByField(walletBottomItems, "walletBottom");
          }
        }
      }"""
    required = (
        marker,
        "const walletItems = item.items;",
        "Array.isArray(walletItems)",
        'compactDidiByField(walletItems, "walletItem");',
        "const walletBottomItems = item.bottom_items;",
        "Array.isArray(walletBottomItems)",
        'compactDidiByField(walletBottomItems, "walletBottom");',
    )
    forbidden = (
        "Array.isArray(item.items)",
        "item.items.length",
        'compactDidiByField(item.items, "walletItem")',
        "Array.isArray(item.bottom_items)",
        "item.bottom_items.length",
        'compactDidiByField(item.bottom_items, "walletBottom")',
    )
    if marker in source:
        if source.count(marker) != 1 or any(token not in source for token in required):
            raise ValueError("Didi wallet property-cache structure is incomplete")
        if any(token in source for token in forbidden):
            raise ValueError("Didi repeated wallet property reads remain")
        return source
    if source.count(old) != 1:
        raise ValueError("Didi wallet card branch changed; refusing property-cache rewrite")
    source = source.replace(old, new, 1)
    if any(token not in source for token in required) or any(token in source for token in forbidden):
        raise ValueError("Didi wallet property-cache validation failed")
    return source



def optimize_didi_nested_traversal_property_cache(source):
    """Cache show_data length and each nested scene_ids reference once per block."""
    marker = "// loon-change: Didi show_data nested traversal cache v1"
    root = "responseData" if "const responseData = obj.data;" in source else "obj.data"
    old = (
        "    const showData = " + root + ".show_data;\n"
        "    for (let read = 0; read < showData.length; read++) {\n"
        "      const block = showData[read];\n"
        "      if (block.scene_ids instanceof Array) {\n"
        "        compactDidiByField(block.scene_ids, \"sceneId\");\n"
        "      }\n"
        "    }"
    )
    new = (
        "    // loon-change: Didi show_data nested traversal cache v1\n"
        "    const showData = " + root + ".show_data;\n"
        "    const showDataLength = showData.length;\n"
        "    for (let read = 0; read < showDataLength; read++) {\n"
        "      const block = showData[read];\n"
        "      const sceneIds = block.scene_ids;\n"
        "      if (sceneIds instanceof Array) {\n"
        "        compactDidiByField(sceneIds, \"sceneId\");\n"
        "      }\n"
        "    }"
    )
    if marker in source:
        if "const showDataLength = showData.length;" not in source or "const sceneIds = block.scene_ids;" not in source:
            raise ValueError("Didi nested traversal cache structure is incomplete")
        return source
    if root + ".show_data" not in source:
        return source
    if source.count(old) != 1:
        raise ValueError("Didi show_data traversal anchor changed; refusing cache rewrite")
    source = source.replace(old, new, 1)
    if new not in source or old in source:
        raise ValueError("Didi nested traversal cache validation failed")
    return source


def optimize_info_list_cached_references(source):
    """Cache the nested top-banner array and first item on the Didi info-list path."""
    marker = "loon-change: Didi info-list cached nested references v1"
    root = "responseData" if "const responseData = obj.data;" in source else "obj.data"
    old = '''if (isInfoList) {
  if (ROOT && ROOT.disorder_cards && ROOT.disorder_cards.top_banner_card && ROOT.disorder_cards.top_banner_card.data && ROOT.disorder_cards.top_banner_card.data[0] && ROOT.disorder_cards.top_banner_card.data[0].T === "yuentu_top_banner") {
    // 移除顶部卡片
    ROOT.disorder_cards.top_banner_card.data.splice(0, 1);
    modified = true;
  }
}'''.replace("ROOT", root)
    new = '''if (isInfoList) {
  // loon-change: Didi info-list cached nested references v1
  const topBannerData = ROOT?.disorder_cards?.top_banner_card?.data;
  const firstTopBanner = topBannerData?.[0];
  if (firstTopBanner?.T === "yuentu_top_banner") {
    // 移除顶部卡片
    topBannerData.splice(0, 1);
    modified = true;
  }
}'''.replace("ROOT", root)
    if marker in source:
        required = (
            "const topBannerData = " + root + "?.disorder_cards?.top_banner_card?.data;",
            "const firstTopBanner = topBannerData?.[0];",
            'if (firstTopBanner?.T === "yuentu_top_banner")',
            "topBannerData.splice(0, 1);",
        )
        if source.count(marker) != 1 or any(value not in source for value in required) or old in source:
            raise ValueError("Didi info-list reference cache structure is incomplete")
        return source
    if "if (isInfoList) {" not in source:
        return source
    if source.count(old) != 1:
        raise ValueError("Didi info-list nested reference anchor changed; refusing cache rewrite")
    source = source.replace(old, new, 1)
    if marker not in source or old in source:
        raise ValueError("Didi info-list reference cache validation failed")
    return source

DIDI_RESPONSE_DATA_CACHE_MARKER = "// loon-change: Didi response data reference cache v1"

def optimize_response_data_reference_cache(source):
    """Read the parsed response's root data reference once and reuse it across routes."""
    parse = "let obj = JSON.parse($response.body);"
    if DIDI_RESPONSE_DATA_CACHE_MARKER in source:
        required = (DIDI_RESPONSE_DATA_CACHE_MARKER, "const responseData = obj.data;")
        if source.count(DIDI_RESPONSE_DATA_CACHE_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Didi response data reference cache structure is incomplete")
        if source.count("obj.data") != 1:
            raise ValueError("Didi repeated response data root access remains")
        return source
    if source.count(parse) != 1:
        raise ValueError("Didi response data cache parse anchor drift")
    source = source.replace(parse, parse + "\n  " + DIDI_RESPONSE_DATA_CACHE_MARKER + "\n  const responseData = obj.data;", 1)
    source = source.replace("obj.data", "responseData")
    source = source.replace("const responseData = responseData;", "const responseData = obj.data;")
    if source.count("obj.data") != 1:
        raise ValueError("Didi response data cache postcondition failed")
    return source



DIDI_HOMEPAGE_CORE_CACHE_MARKER = "// loon-change: Didi homepage-core cached nested references v1"

def optimize_homepage_core_cached_references(source):
    """Cache homepage nav/card references once before in-place allowlist compaction."""
    marker = DIDI_HOMEPAGE_CORE_CACHE_MARKER
    old = '''if (isHomepageCore) {
  // 保留打车、代驾、青桔骑行
  if (responseData && responseData.order_cards && responseData.order_cards.nav_list_card && responseData.order_cards.nav_list_card.data) {
    compactDidiByField(responseData.order_cards.nav_list_card.data, "nav");
  }
  // 保留底部tap首页、我的
  if (responseData && responseData.disorder_cards && responseData.disorder_cards.bottom_nav_list && responseData.disorder_cards.bottom_nav_list.data) {
    compactDidiByField(responseData.disorder_cards.bottom_nav_list.data, "bottomNav");
  }
}'''
    new = '''if (isHomepageCore) {
  // loon-change: Didi homepage-core cached nested references v1
  const orderCards = responseData?.order_cards;
  const navListCard = orderCards?.nav_list_card;
  const navListData = navListCard?.data;
  if (navListData) {
    compactDidiByField(navListData, "nav");
  }

  const disorderCards = responseData?.disorder_cards;
  const bottomNavList = disorderCards?.bottom_nav_list;
  const bottomNavData = bottomNavList?.data;
  if (bottomNavData) {
    compactDidiByField(bottomNavData, "bottomNav");
  }
}'''
    required = (
        marker,
        "const orderCards = responseData?.order_cards;",
        "const navListCard = orderCards?.nav_list_card;",
        "const navListData = navListCard?.data;",
        "const disorderCards = responseData?.disorder_cards;",
        "const bottomNavList = disorderCards?.bottom_nav_list;",
        "const bottomNavData = bottomNavList?.data;",
        'compactDidiByField(navListData, "nav");',
        'compactDidiByField(bottomNavData, "bottomNav");',
    )
    if marker in source:
        if any(token not in source for token in required) or old in source:
            raise ValueError("Didi homepage-core reference cache structure is incomplete")
        return source
    if "if (isHomepageCore) {" not in source:
        return source
    if source.count(old) != 1:
        raise ValueError("Didi homepage-core nested reference anchor changed; refusing cache rewrite")
    source = source.replace(old, new, 1)
    if any(token not in source for token in required) or old in source:
        raise ValueError("Didi homepage-core reference cache validation failed")
    return source


def optimize_source(source, commit="unknown"):
    if MARKER in source:
        if re.search(r"\.filter\s*\(", source):
            raise ValueError("Didi optimization marker exists but allocating filter remains")
        if "obj.data.cards.forEach" in source:
            raise ValueError("Didi user-center wallet traversal optimization is stale")
        return optimize_route_array_reference_cache(optimize_homepage_core_cached_references(optimize_response_data_reference_cache(optimize_info_list_cached_references(optimize_didi_route_dispatch_cache(optimize_didi_nested_traversal_property_cache(optimize_wallet_nested_property_cache(optimize_preparse_route_guard(optimize_didi_predicates(optimize_lazy_serialization(source))))))))))
    if LEGACY_MARKER in source:
        source = source.replace(LEGACY_MARKER, MARKER, 1)
        return optimize_route_array_reference_cache(optimize_homepage_core_cached_references(optimize_response_data_reference_cache(optimize_info_list_cached_references(optimize_didi_route_dispatch_cache(optimize_didi_nested_traversal_property_cache(optimize_wallet_nested_property_cache(optimize_didi_predicates(optimize_lazy_serialization(source)))))))))

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
    old_wallet_block = "    compactInPlace(obj.data.cards, card => !excludedTitles.includes(card.title));\n\n    obj.data.cards.forEach(card => {\n      if (card.tag === \"wallet\") {\n        if (card.items) {\n          compactInPlace(card.items, item => item.title === \"优惠券\");\n        }\n        if (card.card_type === 4 && card.bottom_items) {\n          compactInPlace(card.bottom_items, item =>\n              item.title === \"省钱套餐\" || item.title === \"天天神券\"\n          );\n        }\n      }\n    });"
    new_wallet_block = "    compactInPlace(obj.data.cards, card => {\n      if (excludedTitles.includes(card.title)) return false;\n      if (card.tag === \"wallet\") {\n        if (card.items) {\n          compactInPlace(card.items, item => item.title === \"优惠券\");\n        }\n        if (card.card_type === 4 && card.bottom_items) {\n          compactInPlace(card.bottom_items, item =>\n              item.title === \"省钱套餐\" || item.title === \"天天神券\"\n          );\n        }\n      }\n      return true;\n    });"
    if source.count(old_wallet_block) != 1:
        raise ValueError("Didi user-center card traversal changed; refusing fusion")
    source = source.replace(old_wallet_block, new_wallet_block, 1)
    if re.search(r"\.filter\s*\(", source):
        raise ValueError("Didi allocating filter remains after optimization")
    if source.count("function compactInPlace(items, keep)") != 1:
        raise ValueError("Didi compaction helper definition count drift")
    if source.count("compactInPlace(") != EXPECTED_FILTERS + 1:
        raise ValueError("expected all seven Didi filters to use compactInPlace")

    source = source.rstrip() + "\n}\n"
    return optimize_route_array_reference_cache(optimize_homepage_core_cached_references(optimize_response_data_reference_cache(optimize_info_list_cached_references(optimize_didi_route_dispatch_cache(optimize_didi_nested_traversal_property_cache(optimize_wallet_nested_property_cache(optimize_preparse_route_guard(optimize_didi_predicates(optimize_lazy_serialization(MARKER + commit + "\n" + source))))))))))


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



DIDI_ROUTE_ARRAY_REFERENCE_CACHE_MARKER = "// loon-change: Didi scene-list and show-data array reference cache v1"
DIDI_ROUTE_ARRAY_OLD_SCENE = """if (isSceneList) {
  if (obj && responseData && responseData.scene_list instanceof Array) {
    compactDidiByField(responseData.scene_list, "scene");
  }
  if (obj && responseData && responseData.show_data instanceof Array) {
    // loon-change: Didi show_data nested traversal cache v1
    const showData = responseData.show_data;
    const showDataLength = showData.length;
    for (let read = 0; read < showDataLength; read++) {
      const block = showData[read];
      const sceneIds = block.scene_ids;
      if (sceneIds instanceof Array) {
        compactDidiByField(sceneIds, "sceneId");
      }
    }
  }
}"""
DIDI_ROUTE_ARRAY_NEW_SCENE = """if (isSceneList) {
  // loon-change: Didi scene-list and show-data array reference cache v1
  const sceneList = responseData?.scene_list;
  if (sceneList instanceof Array) {
    compactDidiByField(sceneList, "scene");
  }
  const showData = responseData?.show_data;
  if (showData instanceof Array) {
    // loon-change: Didi show_data nested traversal cache v1
    const showDataLength = showData.length;
    for (let read = 0; read < showDataLength; read++) {
      const block = showData[read];
      const sceneIds = block.scene_ids;
      if (sceneIds instanceof Array) {
        compactDidiByField(sceneIds, "sceneId");
      }
    }
  }
}"""
DIDI_ROUTE_ARRAY_OLD_USER = """if (isUserCenter) {
  if (responseData && responseData.cards) {
    compactDidiByField(responseData.cards, "card");
  }
}"""
DIDI_ROUTE_ARRAY_NEW_USER = """if (isUserCenter) {
  // loon-change: Didi user-center cards array reference cache v1
  const userCenterCards = responseData?.cards;
  if (userCenterCards) {
    compactDidiByField(userCenterCards, "card");
  }
}"""

def optimize_route_array_reference_cache(source):
    """Cache Didi scene-list, show-data, and user-center array references once."""
    marker = DIDI_ROUTE_ARRAY_REFERENCE_CACHE_MARKER
    required = (
        marker,
        "const sceneList = responseData?.scene_list;",
        "const showData = responseData?.show_data;",
        "const userCenterCards = responseData?.cards;",
        'compactDidiByField(sceneList, "scene");',
        'compactDidiByField(userCenterCards, "card");',
    )
    if marker in source:
        if source.count(marker) != 1 or any(token not in source for token in required):
            raise ValueError("Didi route array-reference cache structure is incomplete")
        if "responseData.scene_list" in source or "responseData.show_data" in source or "responseData.cards" in source:
            raise ValueError("Didi repeated route array property reads remain")
        return source
    if source.count(DIDI_ROUTE_ARRAY_OLD_SCENE) != 1 or source.count(DIDI_ROUTE_ARRAY_OLD_USER) != 1:
        if "if (isSceneList) {" not in source and "if (isUserCenter) {" not in source:
            return source
        raise ValueError("Didi scene-list/user-center cache anchors changed")
    source = source.replace(DIDI_ROUTE_ARRAY_OLD_SCENE, DIDI_ROUTE_ARRAY_NEW_SCENE, 1)
    source = source.replace(DIDI_ROUTE_ARRAY_OLD_USER, DIDI_ROUTE_ARRAY_NEW_USER, 1)
    if source.count(marker) != 1 or any(token not in source for token in required):
        raise ValueError("Didi route array-reference cache postcondition failed")
    if "responseData.scene_list" in source or "responseData.show_data" in source or "responseData.cards" in source:
        raise ValueError("Didi repeated route array property reads remain")
    return source


if __name__ == "__main__":
    main()
