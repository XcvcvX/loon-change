#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replace callback-driven compaction in the vendored Rucu6 Amap runtime."""
import argparse
from pathlib import Path

HELPER_MARKER = "// loon-change: Amap rucu6 callback-free compaction v1"
ROUTE_MARKER = "// loon-change: Amap rucu6 callback-free route calls v1"

OLD_HELPER = """function compactInPlace(items, keep) {
  if (!Array.isArray(items) || items.length === 0) return;
  let write = 0;
  for (let read = 0; read < items.length; read++) {
    const item = items[read];
    if (!keep(item)) continue;
    items[write++] = item;
  }
  items.length = write;
}"""

HELPER = """// loon-change: Amap rucu6 callback-free compaction v1
function compactAmapRucu6(items, mode) {
  if (!Array.isArray(items)) return;
  const length = items.length;
  if (length === 0) return;
  let write = 0;

  if (mode === "withoutSchema") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      if (item && Object.prototype.hasOwnProperty.call(item, "schema")) continue;
      if (write !== read) items[write] = item;
      write++;
    }
  } else if (mode === "homeCards") {
    for (let read = 0; read < length; read++) {
      const item = items[read];
      const dataKey = item?.dataKey;
      if (dataKey === "ContinueNavigationCard" ||
          dataKey === "FrequentLocation" ||
          dataKey === "LoginCard") {
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
      if (!amapAdsPattern.test(item?.dynamic_id_s)) {
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
  } else {
    return;
  }

  if (write !== length) items.length = write;
}"""

# (old callback call, replacement call, expected occurrences, description)
REWRITES = (
    (
        """compactInPlace(obj.data.children, (item) =>
      !item || !Object.prototype.hasOwnProperty.call(item, "schema")
    );""",
        'compactAmapRucu6(obj.data.children, "withoutSchema");',
        1,
        "schema filtering",
    ),
    (
        """compactInPlace(obj.data.cardList, (item) =>
      item?.dataKey === "ContinueNavigationCard" ||
      item?.dataKey === "FrequentLocation" ||
      item?.dataKey === "LoginCard"
    );""",
        'compactAmapRucu6(obj.data.cardList, "homeCards");',
        1,
        "home cards",
    ),
    (
        """compactInPlace(obj.data.mapBizList, (item) =>
      item?.dataKey === "FindCarVirtualCard"
    );""",
        'compactAmapRucu6(obj.data.mapBizList, "findCar");',
        1,
        "find-car cards",
    ),
    (
        """compactInPlace(obj.data.tbt.event, (item) =>
      !amapAdsPattern.test(item?.dynamic_id_s)
    );""",
        'compactAmapRucu6(obj.data.tbt.event, "dynamicAds");',
        2,
        "route event ads",
    ),
    (
        """compactInPlace(obj.data.front_end.download, (item) =>
        !amapAdsPattern.test(item?.dynamic_id_s)
      );""",
        'compactAmapRucu6(obj.data.front_end.download, "dynamicAds");',
        1,
        "routeInfo voice ads",
    ),
    (
        """compactInPlace(obj.data.front_end.download, (item) =>
      !amapAdsPattern.test(item?.dynamic_id_s)
    );""",
        'compactAmapRucu6(obj.data.front_end.download, "dynamicAds");',
        1,
        "routePlan voice ads",
    ),
    (
        """compactInPlace(obj.data.front_end.guide_tips, (item) =>
        item?.biz_type !== "music"
      );""",
        'compactAmapRucu6(obj.data.front_end.guide_tips, "nonMusic");',
        1,
        "music guide tips",
    ),
    (
        'compactInPlace(obj.data.cardList, (item) => item?.dataKey === "MyOrderCard");',
        'compactAmapRucu6(obj.data.cardList, "myOrder");',
        1,
        "profile order card",
    ),
    (
        """compactInPlace(modules, (item) =>
      item === "head" || item === "search_hot_words" || item === "feed_rec"
    );""",
        'compactAmapRucu6(modules, "nearbyModules");',
        1,
        "nearby modules",
    ),
    (
        """compactInPlace(list.content, (item) =>
          item?.item_type !== "brandAdCard" && item?.item_type !== "toplist_al"
        );""",
        'compactAmapRucu6(list.content, "searchContent");',
        1,
        "search result content",
    ),
)


def validate_source(source):
    if source.count(HELPER_MARKER) != 1 or source.count(ROUTE_MARKER) != 1:
        raise ValueError("Amap Rucu6 callback-free markers are missing or duplicated")
    if source.count("function compactAmapRucu6(items, mode)") != 1:
        raise ValueError("Amap Rucu6 specialized helper inventory changed")
    if "function compactInPlace(" in source or "compactInPlace(" in source:
        raise ValueError("Amap Rucu6 callback compaction remains")
    if "keep(item)" in source or "items[read] = item" in source:
        raise ValueError("Amap Rucu6 callback or redundant self-write remains")
    expected_modes = {
        "withoutSchema": 1,
        "homeCards": 1,
        "findCar": 1,
        "dynamicAds": 4,
        "nonMusic": 1,
        "myOrder": 1,
        "nearbyModules": 1,
        "searchContent": 1,
    }
    for mode, expected in expected_modes.items():
        count = source.count('compactAmapRucu6(')
        if source.count(', "' + mode + '");') != expected:
            raise ValueError("Amap Rucu6 callsite inventory changed for " + mode)
    if source.count("compactAmapRucu6(") != 12:
        raise ValueError("Amap Rucu6 specialized callsite count changed")
    if source.count("const length = items.length;") != 1:
        raise ValueError("Amap Rucu6 array-length snapshot is missing or duplicated")
    if source.count("if (write !== length) items.length = write;") != 1:
        raise ValueError("Amap Rucu6 conditional array shrink guard changed")
    return source


def optimize_source(source):
    if not isinstance(source, str):
        raise TypeError("Amap Rucu6 source must be text")
    if HELPER_MARKER in source or ROUTE_MARKER in source:
        return validate_source(source)

    if source.count(OLD_HELPER) != 1:
        raise ValueError("Amap Rucu6 compaction helper changed; refusing optimization")
    for old, new, expected, description in REWRITES:
        actual = source.count(old)
        if actual != expected:
            raise ValueError(
                "Amap Rucu6 " + description + " callsite inventory changed: "
                + str(actual) + " != " + str(expected)
            )
        source = source.replace(old, new, expected)

    source = source.replace(OLD_HELPER, HELPER, 1)
    first_call = '    compactAmapRucu6(obj.data.children, "withoutSchema");'
    if source.count(first_call) != 1:
        raise ValueError("Amap Rucu6 route marker anchor changed")
    source = source.replace(
        first_call,
        "    // loon-change: Amap rucu6 callback-free route calls v1\n" + first_call,
        1,
    )
    return validate_source(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, help="patched Romeo Rucu6 runtime path")
    args = parser.parse_args()
    path = Path(args.runtime)
    source = path.read_text(encoding="utf-8-sig")
    optimized = optimize_source(source)
    if optimized != source:
        path.write_text(optimized, encoding="utf-8")
    print("[amap-rucu6-optimizer] PASS: 11 callback callsites replaced by 8 mode-specialized loops")


if __name__ == "__main__":
    main()
