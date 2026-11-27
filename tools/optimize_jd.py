#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the local Jingdong response cleaner and route the aggregate trigger to it."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/jd.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js"
LOCAL_FULL_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|welcomeHome|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js,tag=JD,requires-body=true"
LOCAL_CORE_TRIGGER = r"http-response ^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=(?:deliverLayer|getTabHomeInfo|myOrderInfo|orderTrackBusiness|personinfoBusiness|start|readCustomSurfaceList) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js,tag=JD-CONSOLIDATED,requires-body=true"
LOCAL_OPTIONAL_WELCOME_TRIGGER = r'response if ${url} ~= /^https:\/\/api\.m\.jd\.com\/client\.action\?functionId=welcomeHome/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/jingdong/jd.js", {${jkds_enable}}) with tag="JD-CONSOLIDATED-WELCOME", timeout=60, requires_body=true'
MARKER_PREFIX = "// loon-change: Jingdong in-place response compaction and lazy serialization v1; upstream zirawell/R-Store@"
ROUTES = (
    "start",
    "welcomeHome",
    "readCustomSurfaceList",
    "deliverLayer",
    "orderTrackBusiness",
    "getTabHomeInfo",
    "myOrderInfo",
    "personinfoBusiness",
)

HEADER = """{marker}
(function () {{
  const url = ($request && $request.url) || "";
  const body = $response && $response.body;
  const argument = typeof $argument !== "undefined" ? $argument : null;
  const welcomeExtraEnabled = Boolean(
    argument && typeof argument === "object" && argument.jkds_enable === true
  );

  const shouldProcess =
    url.includes("functionId=start") ||
    url.includes("functionId=welcomeHome") ||
    url.includes("functionId=readCustomSurfaceList") ||
    url.includes("functionId=deliverLayer") ||
    url.includes("functionId=orderTrackBusiness") ||
    url.includes("functionId=getTabHomeInfo") ||
    url.includes("functionId=myOrderInfo") ||
    url.includes("functionId=personinfoBusiness");
  if (!shouldProcess || typeof body !== "string" || !body) {{
    $done({{}});
    return;
  }}

  let obj;
  try {{
    obj = JSON.parse(body);
  }} catch (_) {{
    $done({{}});
    return;
  }}
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {{
    $done({{}});
    return;
  }}

  let modified = false;

  function compactJdServiceList(items) {{
    const length = items.length;
    let write = 0;
    for (let read = 0; read < length; read++) {{
      const card = items[read];
      if (!(card && card.serviceTitle === "精选特惠")) {{
        if (write !== read) items[write] = card;
        write++;
      }}
    }}
    if (write !== length) {{
      items.length = write;
      modified = true;
    }}
  }}

  // Dispatch once per array, then walk by index without per-item predicate callbacks.
  function compactJdInPlace(items, mode, welcomeExtraEnabled) {{
    if (!Array.isArray(items)) return items;
    const length = items.length;
    let write = 0;
    if (mode === "welcome") {{
      for (let read = 0; read < length; read++) {{
        const item = items[read];
        const type = item && item.type;
        const included = type === "topTab" || type === "searchC" || type === "dynamicIcon" ||
          type === "locPermission" || type === "login" || type === "hybrid" || type === "recommend";
        const extraExcluded = type === "bottomXview" || type === "float" || type === "photoCeiling" ||
          type === "ruleFloat" || type === "searchIcon" || type === "topRotate" || type === "tabBarAtmosphere";
        if (included && (!welcomeExtraEnabled || !extraExcluded)) {{
          if (write !== read) items[write] = item;
          write++;
        }}
      }}
    }} else if (mode === "custom") {{
      for (let read = 0; read < length; read++) {{
        const item = items[read];
        const name = item && item.functionId;
        if (name === "index" || name === "messagenew" || name === "cart" || name === "home") {{
          if (write !== read) items[write] = item;
          write++;
        }}
      }}
    }} else if (mode === "delivery") {{
      for (let read = 0; read < length; read++) {{
        const item = items[read];
        const id = item && item.mId;
        if (id !== "banner" && id !== "jdDeliveryBanner") {{
          if (write !== read) items[write] = item;
          write++;
        }}
      }}
    }} else if (mode === "order") {{
      for (let read = 0; read < length; read++) {{
        const floor = items[read];
        const id = floor && floor.mId;
        if (id === "bannerFloor" || id === "bpDynamicFloor" || id === "plusFloor") continue;
        if (id === "virtualServiceCenter") {{
          const data = floor.data;
          const centers = data && data.virtualServiceCenters;
          if (Array.isArray(centers)) {{
            const centerLength = centers.length;
            for (let centerIndex = 0; centerIndex < centerLength; centerIndex++) {{
              const center = centers[centerIndex];
              const serviceList = center && center.serviceList;
              if (Array.isArray(serviceList) && serviceList.length > 0) compactJdServiceList(serviceList);
            }}
          }}
        }} else if (id === "customerServiceFloor") {{
          const data = floor.data;
          if (data && data.moreText) {{
            deleteIfPresent(data, "moreIcon");
            deleteIfPresent(data, "moreIcon_dark");
            if (data.moreText !== " ") {{ data.moreText = " "; modified = true; }}
          }}
        }}
        if (write !== read) items[write] = floor;
        write++;
      }}
    }} else return items;
    if (write !== length) {{
      items.length = write;
      modified = true;
    }}
    return items;
  }}
  function deleteIfPresent(target, key) {{
    if (target && Object.prototype.hasOwnProperty.call(target, key)) {{
      delete target[key];
      modified = true;
    }}
  }}

  function clearArrayIfNeeded(target, key) {{
    if (target && Array.isArray(target[key]) && target[key].length > 0) {{
      target[key] = [];
      modified = true;
    }}
  }}



"""
 
def replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError("%s anchor count changed: expected 1, got %d" % (description, count))
    return source.replace(old, new, 1)


def _replace_array_constant(source: str, name: str, function: str) -> str:
    pattern = re.compile(r"const " + re.escape(name) + r"\s*=\s*\[[\s\S]*?\];")
    source, count = pattern.subn(function, source, count=1)
    if count != 1:
        raise ValueError("%s upstream allowlist changed; refusing optimization" % name)
    return source


def _remove_array_constant(source: str, name: str) -> str:
    pattern = re.compile(r"const " + re.escape(name) + r"\s*=\s*\[[\s\S]*?\];")
    source, count = pattern.subn("", source, count=1)
    if count != 1:
        raise ValueError("%s upstream allowlist changed; refusing optimization" % name)
    return source

def _validate_upstream(source: str) -> None:
    for route in ROUTES:
        token = "functionId=" + route
        if source.count(token) != 1:
            raise ValueError("Jingdong route inventory changed: %s count != 1" % route)
    if source.count(".filter(") != 4:
        raise ValueError("Jingdong array-filter inventory changed; expected four reviewed filters")
    expected_arrays = {
        "newFloors": 2,
        "newItems": 1,
        "newCards": 1,
    }
    for name, expected in expected_arrays.items():
        count = len(re.findall(r"\b(?:let|const)\s+" + name + r"\s*=\s*\[\]", source))
        if count != expected:
            raise ValueError("Jingdong %s allocation inventory changed: expected %d, got %d"
                             % (name, expected, count))
    for token in (
        'obj.floorList = obj.floorList.filter((i) => WELCOME_HOME_TYPE_INCLUDE.includes(i?.type));',
        'obj.result.modeMap.dark.navigationAll = obj.result.modeMap.dark.navigationAll.filter((i) => CUSTOM_SURFACE_NAME_INCLUDE.includes(i?.functionId));',
        'obj.result.modeMap.normal.navigationAll = obj.result.modeMap.normal.navigationAll.filter((i) => CUSTOM_SURFACE_NAME_INCLUDE.includes(i?.functionId));',
        'obj.floors = obj.floors.filter((i) => !["banner", "jdDeliveryBanner"]?.includes(i?.mId));',
        'if (card?.serviceTitle === "精选特惠") {',
        'floor.data.virtualServiceCenters = newItems;',
        'floor.data.moreText = " ";',
        'newFloors.push(floor);',
        'floor.data?.commonPopup_dynamic;',
        'floor.data?.commonWindows?.length',
        'floor.data?.newPlusBlackCard;',
    ):
        if token not in source:
            raise ValueError("Jingdong upstream behavior marker missing: " + token)


def optimize_source(source: str, upstream_commit: str = "unknown") -> str:
    if MARKER_PREFIX in source:
        required = (
            "function compactJdInPlace(items, mode, welcomeExtraEnabled)",
            "function compactJdServiceList(items)",
            "function processFloors(floors)",
            'compactJdInPlace(obj.floorList, "welcome", welcomeExtraEnabled);',
            'compactJdInPlace(darkNavigation, "custom");',
            'compactJdInPlace(normalNavigation, "custom");',
            'compactJdInPlace(obj.floors, "delivery");',
            'compactJdInPlace(obj.floors, "order");',
            "compactJdServiceList(serviceList);",
            '$done(modified ? { body: JSON.stringify(obj) } : {});',
        )
        if any(token not in source for token in required):
            raise ValueError("Jingdong optimization marker exists but required behavior is incomplete")
        if any(token in source for token in ("compactInPlace(", ".filter(", ".map(", ".forEach(", "newFloors = []", "newItems = []", "newCards = []")):
            raise ValueError("Jingdong optimization marker exists but allocation regression remains")
        if "readCustomSurfaceList\").*forEach" in source:
            raise ValueError("Jingdong custom-surface callback traversal remains")
        return source

    _validate_upstream(source)
    head = (
        'const url = $request.url;\n'
        'if (!$response.body) $done({});\n'
        'let obj = JSON.parse($response.body);'
    )
    if source.count(head) != 1:
        raise ValueError("Jingdong response entry point changed; refusing optimization")
    source = replace_once(
        source, head, HEADER.format(marker=MARKER_PREFIX + upstream_commit),
        "Jingdong response entry point",
    )

    source = _remove_array_constant(source, "PERSON_INFO_BUSINESS_MID_EXCLUDE")
    source = _remove_array_constant(source, "WELCOME_HOME_TYPE_INCLUDE")
    source = _remove_array_constant(source, "CUSTOM_SURFACE_NAME_INCLUDE")

    source = replace_once(
        source,
        "obj.images = [];",
        "obj.images = [];\n    modified = true;",
        "Jingdong splash image clear",
    )
    source = replace_once(
        source,
        "obj.showTimesDaily = 0;",
        "obj.showTimesDaily = 0;\n    modified = true;",
        "Jingdong splash daily count",
    )
    source = replace_once(
        source,
        "obj.floorList = obj.floorList.filter((i) => WELCOME_HOME_TYPE_INCLUDE.includes(i?.type));",
        "compactJdInPlace(obj.floorList, \"welcome\", welcomeExtraEnabled);",
        "Jingdong welcomeHome floor filter",
    )
    source = replace_once(
        source, "obj.webViewFloorList = [];",
        "clearArrayIfNeeded(obj, \"webViewFloorList\");",
        "Jingdong welcomeHome webview clear",
    )
    source = replace_once(
        source, "delete obj.promotionTabs;",
        "deleteIfPresent(obj, \"promotionTabs\");",
        "Jingdong welcomeHome promotion delete",
    )
    read_start = '} else if (url.includes("functionId=readCustomSurfaceList")) {'
    deliver_start = '}else if (url.includes("functionId=deliverLayer")'
    if source.count(read_start) != 1 or source.count(deliver_start) != 1:
        raise ValueError("Jingdong custom-surface route boundaries changed")
    start = source.index(read_start)
    end = source.index(deliver_start, start)
    read_branch = """} else if (url.includes("functionId=readCustomSurfaceList")) {
  const modeMap = obj.result && obj.result.modeMap;
  const darkNavigation = modeMap && modeMap.dark && modeMap.dark.navigationAll;
  if (Array.isArray(darkNavigation) && darkNavigation.length > 0) {
    compactJdInPlace(darkNavigation, "custom");
  }
  const normalNavigation = modeMap && modeMap.normal && modeMap.normal.navigationAll;
  if (Array.isArray(normalNavigation) && normalNavigation.length > 0) {
    compactJdInPlace(normalNavigation, "custom");
  }
"""
    source = source[:start] + read_branch + "} else if (url.includes(\"functionId=deliverLayer\")" + source[end + len(deliver_start):]

    source = replace_once(
        source, "delete obj.bannerInfo;",
        "deleteIfPresent(obj, \"bannerInfo\");",
        "Jingdong delivery banner delete",
    )
    source = replace_once(
        source,
        'obj.floors = obj.floors.filter((i) => !["banner", "jdDeliveryBanner"]?.includes(i?.mId));',
        "compactJdInPlace(obj.floors, \"delivery\");",
        "Jingdong delivery floor filter",
    )
    source = replace_once(
        source, "delete obj.result.iconInfo;",
        'deleteIfPresent(obj.result, "iconInfo");',
        "Jingdong new-products floating icon delete",
    )
    source = replace_once(
        source, "delete obj.result.roofTop;",
        'deleteIfPresent(obj.result, "roofTop");',
        "Jingdong new-products roof delete",
    )

    my_order_start = '} else if (url.includes("functionId=myOrderInfo")) {'
    person_start = '} else if (url.includes("functionId=personinfoBusiness")) {'
    if source.count(my_order_start) != 1 or source.count(person_start) != 1:
        raise ValueError("Jingdong order/profile route boundaries changed")
    start = source.index(my_order_start)
    end = source.index(person_start, start)
    my_order = """} else if (url.includes("functionId=myOrderInfo")) {
  if (Array.isArray(obj.floors) && obj.floors.length > 0) {
    compactJdInPlace(obj.floors, "order");
  }
"""
    source = source[:start] + my_order + source[end:]

    source = replace_once(
        source,
        "$done({body: JSON.stringify(obj)});",
        "$done(modified ? { body: JSON.stringify(obj) } : {});",
        "Jingdong lazy serialization",
    )

    clean_start = "/**\n * 清理单个楼层数据"
    process_start = "/**\n * 过滤并处理楼层数组"
    if source.count(clean_start) != 1 or source.count(process_start) != 1:
        raise ValueError("Jingdong floor helper boundaries changed")
    start = source.index(clean_start)
    end = source.index(process_start, start)
    clean_helper = """function cleanFloorData(floor) {
  if (!floor || !floor.mId) return;
  const data = floor.data;

  if (floor.mId === "basefloorinfo") {
    deleteIfPresent(data, "commonPopup");
    deleteIfPresent(data, "commonPopup_dynamic");
    clearArrayIfNeeded(data, "commonTips");
    clearArrayIfNeeded(data, "commonWindows");
    deleteIfPresent(data, "floatLayer");
  } else if (floor.mId === "orderIdFloor") {
    const infos = data && data.commentRemindInfo && data.commentRemindInfo.infos;
    if (Array.isArray(infos) && infos.length > 0) {
      data.commentRemindInfo.infos = [];
      modified = true;
    }
  } else if (floor.mId === "userinfo") {
    deleteIfPresent(data, "newPlusBlackCard");
  }
}

"""
    source = source[:start] + clean_helper + source[end:]

    process_start = "/**\n * 过滤并处理楼层数组"
    if source.count(process_start) != 1:
        raise ValueError("Jingdong processFloors helper missing")
    start = source.index(process_start)
    process_helper = """function processFloors(floors) {
  if (!Array.isArray(floors) || floors.length === 0) return floors;
  const length = floors.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const floor = floors[read];
    const id = floor && floor.mId;
    if (
      id === "bigSaleFloor" || id === "buyOften" || id === "newAttentionCard" ||
      id === "newBigSaleFloor" || id === "newStyleAttentionCard" ||
      id === "newsFloor" || id === "noticeFloor" || id === "recommendfloor"
    ) continue;
    cleanFloorData(floor);
    if (write !== read) floors[write] = floor;
    write++;
  }
  if (write !== length) {
    floors.length = write;
    modified = true;
  }
  return floors;
}"""
    source = source[:start] + process_helper

    source = source.rstrip() + "\n})();\n"
    required = (
        MARKER_PREFIX + upstream_commit,
        "function compactJdInPlace(items, mode, welcomeExtraEnabled)",
        "function compactJdServiceList(items)",
        "function processFloors(floors)",
        "const modeMap = obj.result && obj.result.modeMap;",
        "const shouldProcess =",
        'compactJdInPlace(obj.floorList, "welcome", welcomeExtraEnabled);',
        'compactJdInPlace(darkNavigation, "custom");',
        'compactJdInPlace(normalNavigation, "custom");',
        'compactJdInPlace(obj.floors, "delivery");',
        'compactJdInPlace(obj.floors, "order");',
        "compactJdServiceList(serviceList);",
        "$done(modified ? { body: JSON.stringify(obj) } : {});",
    )
    if any(token not in source for token in required):
        raise ValueError("Jingdong generated runtime is missing a required optimization marker")
    if any(token in source for token in ("compactInPlace(", ".filter(", ".map(", ".forEach(", "newFloors = []", "newItems = []", "newCards = []")):
        raise ValueError("Jingdong generated runtime retains allocating array transforms")
    if ".forEach(" in source or ".map(" in source:
        raise ValueError("Jingdong generated runtime retains callback array traversals")
    return source


def rewrite_plugin(plugin: str) -> str:
    lines = plugin.splitlines(keepends=True)
    section = ""
    script_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
        elif section == "script":
            script_lines.append(stripped)

    remote_full_count = sum(line.count(REMOTE) for line in script_lines)
    local_path_count = sum(line.count(LOCAL) for line in script_lines)
    full_local_count = script_lines.count(LOCAL_FULL_TRIGGER)
    core_count = script_lines.count(LOCAL_CORE_TRIGGER)
    optional_count = script_lines.count(LOCAL_OPTIONAL_WELCOME_TRIGGER)

    # The checked-in snapshot uses one combined local matcher; the build-time
    # JD consolidation emits a core matcher plus the switch-gated welcome route.
    # Both reviewed layouts are already optimized and must remain unchanged.
    if local_path_count == 1 and not (remote_full_count or core_count or optional_count):
        return plugin
    if core_count == 1 and optional_count == 1 and not (remote_full_count or full_local_count):
        return plugin

    if remote_full_count == 1 and not (full_local_count or core_count or optional_count):
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
        if REMOTE in result or result.count(LOCAL) != 1:
            raise ValueError("Jingdong local script route migration incomplete")
        return result

    if not (remote_full_count or local_path_count or core_count or optional_count):
        raise ValueError("Jingdong response trigger not found in [Script]")
    raise ValueError("Jingdong trigger inventory changed: expected one reviewed local layout")


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
        source = Path(args.source).read_text(encoding="utf-8-sig")
        result = optimize_source(source, args.upstream_commit)
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding="utf-8")
        print("Generated optimized Jingdong runtime: %s (%d bytes)" % (target, len(result)))
    if args.plugin:
        path = Path(args.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
        print("Routed the Jingdong response trigger to the protected local runtime")
    if not (args.source or args.output or args.plugin):
        parser.error("provide --source/--output and/or --plugin")


if __name__ == "__main__":
    main()
