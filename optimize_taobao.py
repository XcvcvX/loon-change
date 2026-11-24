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

SPLASH_HOME_OBJECT_MARKER = "// loon-change: Taobao cached splash home object v1"
OLD_SPLASH_HOME_OBJECT_BLOCK = """  if (obj?.data?.containers?.splash_home_base) {
    const sections = obj.data.containers.splash_home_base.base?.sections;"""
NEW_SPLASH_HOME_OBJECT_BLOCK = """  // loon-change: Taobao cached splash home object v1
  const splashHome = obj?.data?.containers?.splash_home_base;
  if (splashHome) {
    const sections = splashHome.base?.sections;"""

def optimize_splash_home_object(source):
    if SPLASH_HOME_OBJECT_MARKER in source:
        required = (
            SPLASH_HOME_OBJECT_MARKER,
            "const splashHome = obj?.data?.containers?.splash_home_base;",
            "if (splashHome) {",
            "const sections = splashHome.base?.sections;",
        )
        if source.count(SPLASH_HOME_OBJECT_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Taobao cached splash home object drifted; refusing to overwrite")
        if OLD_SPLASH_HOME_OBJECT_BLOCK in source:
            raise ValueError("Repeated Taobao splash home object traversal remains")
        return source
    if source.count(OLD_SPLASH_HOME_OBJECT_BLOCK) != 1:
        raise ValueError("Expected exactly one Taobao splash home object block")
    source = source.replace(OLD_SPLASH_HOME_OBJECT_BLOCK, NEW_SPLASH_HOME_OBJECT_BLOCK, 1)
    if source.count(SPLASH_HOME_OBJECT_MARKER) != 1:
        raise ValueError("Taobao cached splash home object postcondition failed")
    return source


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


ROUTE_CLASSIFICATION_MARKER = "// loon-change: Taobao cached route classification v1"
OLD_ROUTE_GUARD = """  // loon-change: Taobao pre-parse supported-route guard v1
  const shouldProcess =
    url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query") ||
    url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get") ||
    url.includes("poplayer.template.alibaba.com/");
  if (!shouldProcess) {
    $done({});
  } else {"""
NEW_ROUTE_GUARD = """  // loon-change: Taobao pre-parse supported-route guard v1
  %s
  const isCloudVideo = url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query");
  const isSplash = url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get");
  const isPoplayer = url.includes("poplayer.template.alibaba.com/");
  const shouldProcess = isCloudVideo || isSplash || isPoplayer;
  if (!shouldProcess) {
    $done({});
  } else {""" % ROUTE_CLASSIFICATION_MARKER

def optimize_route_classification(source):
    if ROUTE_CLASSIFICATION_MARKER in source:
        required = (
            "const isCloudVideo = url.includes(",
            "const isSplash = url.includes(",
            "const isPoplayer = url.includes(",
            "const shouldProcess = isCloudVideo || isSplash || isPoplayer;",
            "if (isCloudVideo) {",
            "} else if (isSplash) {",
            "} else if (isPoplayer) {",
        )
        if any(token not in source for token in required):
            raise ValueError("Taobao cached route classification drifted; refusing to overwrite")
        for route in (
            'url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query")',
            'url.includes("guide-acs.m.taobao.com/gw/mtop.taobao.wireless.home.splash.awesome.get")',
            'url.includes("poplayer.template.alibaba.com/")',
        ):
            if source.count(route) != 1:
                raise ValueError("Taobao route must be classified exactly once")
        return source
    if source.count(OLD_ROUTE_GUARD) != 1:
        raise ValueError("Expected exactly one Taobao pre-parse route guard")
    source = source.replace(OLD_ROUTE_GUARD, NEW_ROUTE_GUARD, 1)
    replacements = (
        ('if (url.includes("mtop.taobao.cloudvideo.video.query")) {', "if (isCloudVideo) {"),
        ('} else if (url.includes("mtop.taobao.wireless.home.splash.awesome.get")) {', "} else if (isSplash) {"),
        ('} else if (url.includes("poplayer.template.alibaba.com")) {', "} else if (isPoplayer) {"),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError("Expected exactly one Taobao route branch: " + old)
        source = source.replace(old, new, 1)
    return source

OBJECT_CACHE_MARKER = "// loon-change: Taobao cached video response object v1"
OLD_VIDEO_OBJECT_BLOCK = "if (isCloudVideo) {\n  if (obj?.data?.duration) {\n    setIfDifferent(obj.data, \"duration\", \"0\");\n  }\n  clearArray(obj?.data || {}, \"resources\");\n  clearArray(obj?.data || {}, \"caches\");\n  if (obj?.data?.respTimeInMs) {\n    setIfDifferent(obj.data, \"respTimeInMs\", \"3818332800000\");\n  }\n}"
NEW_VIDEO_OBJECT_BLOCK = "if (isCloudVideo) {\n  // loon-change: Taobao cached video response object v1\n  const videoData = obj?.data;\n  if (videoData?.duration) {\n    setIfDifferent(videoData, \"duration\", \"0\");\n  }\n  clearArray(videoData || {}, \"resources\");\n  clearArray(videoData || {}, \"caches\");\n  if (videoData?.respTimeInMs) {\n    setIfDifferent(videoData, \"respTimeInMs\", \"3818332800000\");\n  }\n}"
OLD_POPLAYER_OBJECT_BLOCK = "} else if (isPoplayer) {\n  clearArray(obj?.res || {}, \"images\");\n  clearArray(obj?.res || {}, \"videos\");\n  if (obj?.enable) {\n    setIfDifferent(obj, \"enable\", false);\n  }\n  clearArray(obj?.mainRes || {}, \"images\");\n}"
NEW_POPLAYER_OBJECT_BLOCK = "} else if (isPoplayer) {\n  // loon-change: Taobao cached Poplayer response objects v1\n  const poplayerRes = obj?.res;\n  const mainRes = obj?.mainRes;\n  const poplayerEnabled = obj?.enable;\n  clearArray(poplayerRes || {}, \"images\");\n  clearArray(poplayerRes || {}, \"videos\");\n  if (poplayerEnabled) {\n    setIfDifferent(obj, \"enable\", false);\n  }\n  clearArray(mainRes || {}, \"images\");\n}"

def optimize_route_object_access(source):
    if OBJECT_CACHE_MARKER in source:
        required = (
            OBJECT_CACHE_MARKER,
            "const videoData = obj?.data;",
            "const poplayerRes = obj?.res;",
            "const mainRes = obj?.mainRes;",
            "const poplayerEnabled = obj?.enable;",
            'clearArray(poplayerRes, "images");',
            'clearArray(poplayerRes, "videos");',
            'clearArray(mainRes, "images");',
        )
        if any(token not in source for token in required):
            raise ValueError("Taobao cached response object access drifted; refusing to overwrite")
        if ("clearArray(obj?.res || {}, " in source or "clearArray(obj?.mainRes || {}, " in source
                or "clearArray(poplayerRes || {}, " in source or "clearArray(mainRes || {}, " in source):
            raise ValueError("Repeated Taobao Poplayer object access or fallback allocation remains")
        return source
    if source.count(OLD_VIDEO_OBJECT_BLOCK) != 1 or source.count(OLD_POPLAYER_OBJECT_BLOCK) != 1:
        raise ValueError("Expected exactly one Taobao video and Poplayer object access block")
    source = source.replace(OLD_VIDEO_OBJECT_BLOCK, NEW_VIDEO_OBJECT_BLOCK, 1)
    source = source.replace(OLD_POPLAYER_OBJECT_BLOCK, NEW_POPLAYER_OBJECT_BLOCK, 1)
    if (source.count(OBJECT_CACHE_MARKER) != 1
            or source.count("// loon-change: Taobao cached Poplayer response objects v1") != 1):
        raise ValueError("Taobao cached response object access postcondition failed")
    return source



CLEAR_ARRAY_PROPERTY_MARKER = "// loon-change: Taobao clearArray caches property value once v1"
OLD_CLEAR_ARRAY_HELPER = """  function clearArray(target, key) {
    if (Array.isArray(target[key]) && target[key].length > 0) {
      target[key] = [];
      modified = true;
    }
  }"""
NEW_CLEAR_ARRAY_HELPER = """  function clearArray(target, key) {
    // loon-change: Taobao clearArray caches property value once v1
    const current = target[key];
    if (Array.isArray(current) && current.length > 0) {
      target[key] = [];
      modified = true;
    }
  }"""

def optimize_clear_array_property_access(source):
    if CLEAR_ARRAY_PROPERTY_MARKER in source:
        required = (
            CLEAR_ARRAY_PROPERTY_MARKER,
            "const current = target[key];",
            "Array.isArray(current)",
            "current.length > 0",
            "target[key] = [];",
        )
        if source.count(CLEAR_ARRAY_PROPERTY_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Taobao clearArray cached property access drifted; refusing to overwrite")
        if "Array.isArray(target[key])" in source or "target[key].length > 0" in source:
            raise ValueError("Repeated Taobao clearArray property reads remain")
        return source
    if source.count(OLD_CLEAR_ARRAY_HELPER) != 1:
        raise ValueError("Expected exactly one Taobao clearArray helper")
    source = source.replace(OLD_CLEAR_ARRAY_HELPER, NEW_CLEAR_ARRAY_HELPER, 1)
    if source.count(CLEAR_ARRAY_PROPERTY_MARKER) != 1:
        raise ValueError("Taobao clearArray cached property access postcondition failed")
    return source

CLEAR_ARRAY_NULL_TARGET_MARKER = "// loon-change: Taobao clearArray null-target fast path v1"
OLD_CLEAR_ARRAY_NULL_TARGET_HELPER = """  function clearArray(target, key) {
    // loon-change: Taobao clearArray caches property value once v1
    const current = target[key];
    if (Array.isArray(current) && current.length > 0) {
      target[key] = [];
      modified = true;
    }
  }"""
NEW_CLEAR_ARRAY_NULL_TARGET_HELPER = """  function clearArray(target, key) {
    // loon-change: Taobao clearArray null-target fast path v1
    if (target == null) return;
    // loon-change: Taobao clearArray caches property value once v1
    const current = target[key];
    if (Array.isArray(current) && current.length > 0) {
      target[key] = [];
      modified = true;
    }
  }"""
CLEAR_ARRAY_NULL_TARGET_CALLS = (
    ('clearArray(videoData || {}, "resources");', 'clearArray(videoData, "resources");'),
    ('clearArray(videoData || {}, "caches");', 'clearArray(videoData, "caches");'),
    ('clearArray(poplayerRes || {}, "images");', 'clearArray(poplayerRes, "images");'),
    ('clearArray(poplayerRes || {}, "videos");', 'clearArray(poplayerRes, "videos");'),
    ('clearArray(mainRes || {}, "images");', 'clearArray(mainRes, "images");'),
)

def optimize_clear_array_null_targets(source):
    if CLEAR_ARRAY_NULL_TARGET_MARKER in source:
        required = (
            CLEAR_ARRAY_NULL_TARGET_MARKER,
            "if (target == null) return;",
            "const current = target[key];",
            'clearArray(videoData, "resources");',
            'clearArray(videoData, "caches");',
            'clearArray(poplayerRes, "images");',
            'clearArray(poplayerRes, "videos");',
            'clearArray(mainRes, "images");',
        )
        if source.count(CLEAR_ARRAY_NULL_TARGET_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Taobao null-target clearArray fast path drifted; refusing to overwrite")
        if " || {}, \"resources\"" in source or " || {}, \"caches\"" in source:
            raise ValueError("Taobao clearArray fallback object allocations remain")
        if " || {}, \"images\"" in source or " || {}, \"videos\"" in source:
            raise ValueError("Taobao clearArray fallback object allocations remain")
        return source
    if source.count(OLD_CLEAR_ARRAY_NULL_TARGET_HELPER) != 1:
        raise ValueError("Expected exactly one Taobao cached clearArray helper")
    source = source.replace(OLD_CLEAR_ARRAY_NULL_TARGET_HELPER, NEW_CLEAR_ARRAY_NULL_TARGET_HELPER, 1)
    for old, new in CLEAR_ARRAY_NULL_TARGET_CALLS:
        if source.count(old) != 1:
            raise ValueError("Expected exactly one Taobao null-target call site: " + old)
        source = source.replace(old, new, 1)
    if source.count(CLEAR_ARRAY_NULL_TARGET_MARKER) != 1:
        raise ValueError("Taobao null-target clearArray fast path postcondition failed")
    return source


SPLASH_ITEM_UPDATE_MARKER = "// loon-change: Taobao splash item specialized updates v1"
SPLASH_ITEM_UPDATE_HELPER = "  // loon-change: Taobao splash item specialized updates v1\n  function normalizeSplashItem(item) {\n    if (item.waitTime !== \"0\") { item.waitTime = \"0\"; modified = true; }\n    if (item.times !== \"0\") { item.times = \"0\"; modified = true; }\n    if (item.hotStart !== \"false\") { item.hotStart = \"false\"; modified = true; }\n    if (item.haveVoice !== \"false\") { item.haveVoice = \"false\"; modified = true; }\n    if (item.hideTBLogo !== \"false\") { item.hideTBLogo = \"false\"; modified = true; }\n    if (item.enable4G !== \"false\") { item.enable4G = \"false\"; modified = true; }\n    if (item.coldStart !== \"false\") { item.coldStart = \"false\"; modified = true; }\n    if (item.startTime !== \"3818332800000\") { item.startTime = \"3818332800000\"; modified = true; }\n    if (item.endTime !== \"3818419199000\") { item.endTime = \"3818419199000\"; modified = true; }\n    if (item.gmtStart !== \"2090-12-31 00:00:00\") { item.gmtStart = \"2090-12-31 00:00:00\"; modified = true; }\n    if (item.gmtEnd !== \"2090-12-31 23:59:59\") { item.gmtEnd = \"2090-12-31 23:59:59\"; modified = true; }\n    if (item.gmtStartMs !== \"3818332800000\") { item.gmtStartMs = \"3818332800000\"; modified = true; }\n    if (item.gmtEndMs !== \"3818419199000\") { item.gmtEndMs = \"3818419199000\"; modified = true; }\n    if (item?.imgUrl) { item.imgUrl = \"\"; modified = true; }\n    if (item?.videoUrl) { item.videoUrl = \"\"; modified = true; }\n  }\n"
OLD_SPLASH_ITEM_UPDATES = "          setIfDifferent(item, \"waitTime\", \"0\");\n          setIfDifferent(item, \"times\", \"0\");\n          setIfDifferent(item, \"hotStart\", \"false\");\n          setIfDifferent(item, \"haveVoice\", \"false\");\n          setIfDifferent(item, \"hideTBLogo\", \"false\");\n          setIfDifferent(item, \"enable4G\", \"false\");\n          setIfDifferent(item, \"coldStart\", \"false\");\n          setIfDifferent(item, \"startTime\", \"3818332800000\");\n          setIfDifferent(item, \"endTime\", \"3818419199000\");\n          setIfDifferent(item, \"gmtStart\", \"2090-12-31 00:00:00\");\n          setIfDifferent(item, \"gmtEnd\", \"2090-12-31 23:59:59\");\n          setIfDifferent(item, \"gmtStartMs\", \"3818332800000\");\n          setIfDifferent(item, \"gmtEndMs\", \"3818419199000\");\n          if (item?.imgUrl) setIfDifferent(item, \"imgUrl\", \"\");\n          if (item?.videoUrl) setIfDifferent(item, \"videoUrl\", \"\");"
NEW_SPLASH_ITEM_UPDATE = "          normalizeSplashItem(item);"


def optimize_splash_item_updates(source):
    if SPLASH_ITEM_UPDATE_MARKER in source:
        required = (
            SPLASH_ITEM_UPDATE_MARKER,
            "function normalizeSplashItem(item) {",
            'if (item.waitTime !== "0")',
            'if (item.gmtEndMs !== "3818419199000")',
            'if (item?.imgUrl) { item.imgUrl = ""; modified = true; }',
            'if (item?.videoUrl) { item.videoUrl = ""; modified = true; }',
            NEW_SPLASH_ITEM_UPDATE,
        )
        if source.count(SPLASH_ITEM_UPDATE_MARKER) != 1 or any(token not in source for token in required):
            raise ValueError("Taobao specialized splash item update drifted; refusing to overwrite")
        if OLD_SPLASH_ITEM_UPDATES in source:
            raise ValueError("Repeated Taobao splash setter calls remain beside specialized helper")
        return source
    if source.count(OLD_SPLASH_ITEM_UPDATES) != 1:
        raise ValueError("Expected exactly one Taobao splash item update block")
    if source.count("  // loon-change: Taobao pre-parse supported-route guard v1") != 1:
        raise ValueError("Expected exactly one Taobao helper insertion anchor")
    source = source.replace(OLD_SPLASH_ITEM_UPDATES, NEW_SPLASH_ITEM_UPDATE, 1)
    source = source.replace(
        "  // loon-change: Taobao pre-parse supported-route guard v1",
        SPLASH_ITEM_UPDATE_HELPER + "\\n  // loon-change: Taobao pre-parse supported-route guard v1",
        1,
    )
    if source.count(SPLASH_ITEM_UPDATE_MARKER) != 1 or OLD_SPLASH_ITEM_UPDATES in source:
        raise ValueError("Taobao specialized splash item update postcondition failed")
    return source


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
    source = optimize_splash_home_object(source)
    source = optimize_splash_item_updates(source)
    source = optimize_route_classification(source)
    source = optimize_route_object_access(source)
    source = optimize_clear_array_property_access(source)
    source = optimize_clear_array_null_targets(source)
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
