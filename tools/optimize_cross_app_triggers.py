#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidate reviewed app triggers without widening URL coverage."""
import argparse
from pathlib import Path

MEITUAN_SCRIPT = "https://raw.githubusercontent.com/ifflagged/Romeo/1a724bb3c7ae08b3852a9ab94210d7f7fcb2e3a7/Modules/JavaScript/ZenmoFeiShi/MT/ZenmoFeiShi_MT.js"
MEITUAN_TAG = 'tag="MT"'
MEITUAN_MARKER = "# loon-change: Meituan legacy trigger consolidation v1"
PDD_MARKER = "# loon-change: Pinduoduo mrk matcher consolidation v1"
PDD_RULE = r'request if ${url} ~= /^https:\/\/(?:t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_|images\.pinduoduo\.com\/(?:mrk|marketing_api)\/)/i then reject(404)'

def _meituan_legacy(line):
    return MEITUAN_SCRIPT in line and MEITUAN_TAG in line and line.lstrip().startswith(("response if ", "http-response "))

def consolidate_meituan(text):
    lines = text.splitlines()
    legacy = [line for line in lines if _meituan_legacy(line)]
    if MEITUAN_MARKER in text:
        if text.count(MEITUAN_MARKER) != 1 or legacy:
            raise ValueError("Meituan consolidation marker/inventory drift")
        return text
    if len(legacy) != 8:
        raise ValueError("expected exactly 8 legacy Meituan upstream triggers; refusing cleanup (found %d)" % len(legacy))
    canonical = [line for line in lines if "scripts/meituan/meituan.js" in line and "MEITUAN-CONSOLIDATED" in line]
    if len(canonical) != 1:
        raise ValueError("canonical consolidated Meituan handler missing or duplicated")
    output = []
    inserted = False
    for line in lines:
        if _meituan_legacy(line):
            if not inserted:
                output.append(MEITUAN_MARKER)
                inserted = True
            continue
        output.append(line)
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")

def consolidate_pinduoduo_mrk(text):
    lines = text.splitlines()
    old = [
        r'request if ${url} ~= /^https:\/\/t-dsp\.pinduoduo\.com\/dspcb\/i\/mrk_/i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/mrk\//i then reject(404)',
        r'request if ${url} ~= /^https:\/\/images\.pinduoduo\.com\/marketing_api\//i then reject(404)',
    ]
    count = [text.count(x) for x in old]
    if PDD_MARKER in text:
        if text.count(PDD_MARKER) != 1 or any(count):
            raise ValueError("Pinduoduo mrk marker/inventory drift")
        if text.count(PDD_RULE) != 1:
            raise ValueError("Pinduoduo canonical mrk matcher missing or duplicated")
        return text
    if count != [1, 1, 1]:
        raise ValueError("Pinduoduo mrk rule inventory changed; expected one of each host/path matcher")
    for rule in old:
        text = text.replace(rule + "\n", "", 1) if rule + "\n" in text else text.replace(rule, "", 1)
    anchor = "[Rewrite]"
    if text.count(anchor) != 1:
        raise ValueError("expected one Rewrite section for Pinduoduo matcher insertion")
    text = text.replace(anchor, anchor + "\n" + PDD_MARKER + "\n" + PDD_RULE, 1)
    return text




AMAP_YOUTUBE_MARKER = "# loon-change: Amap/YouTube processor ownership split v2"
AMAP_CANONICAL_RULE = r'http-response ^https?:\/\/(?:(?:m[0-46-9]\.amap\.com\/ws\/(?:aos\/perception\/publicTravel\/beforeNavi|bus\/plan\/integrate))|(?:m\d\.amap\.com\/ws\/(?:c3frontend\/(?:af-(?:hotel|launch)\/page\/main|af-nearby\/nearby)|perception\/drive\/(?:routeInfo|routePlan)|shield\/(?:search\/(?:common\/coupon\/info|poi\/detail|nearbyrec_smart)|search_poi\/(?:homepage|mps|search\/sp|sug|tips_operation_location)|search_bff\/hotword|search_business\/process\/marketingOperationStructured|dsp\/profile\/index\/nodefaasv3|frogserver\/aocs\/updatable\/1)|faas\/amap-navigation\/(?:card-service-plan-home|main-page)|valueadded\/alimama\/splash_screen))|(?:m\d-zb\.amap\.com\/ws\/(?:boss\/(?:car\/order\/content_info|order_web\/friendly_information)|promotion-web\/resource(?:\/home)?|sharedtrip\/taxi\/order_detail_car_tips))|(?:info\.amap\.com\/ws\/shield\/search\/(?:common\/coupon\/info|poi\/detail))) script-path=https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/amap/amap.js,tag=AMAP-CONSOLIDATED,requires-body=true'
AMAP_SCRIPT_COUNTS = {
    "scripts/amap/amap.js": 7,
    "ishowshu_amap.js": 5,
    "rucu6_amap.js": 10,
}
AMAP_REQUIRED_PATHS = (
    r"beforeNavi",
    r"bus\/plan\/integrate",
    r"af-(?:hotel|launch)",
    r"af-nearby\/nearby",
    r"routeInfo",
    r"routePlan",
    r"search_poi\/(?:homepage|mps|search\/sp|sug|tips_operation_location)",
    r"card-service-plan-home",
    r"main-page",
    r"updatable\/1",
    r"nearbyrec_smart",
    r"alimama\/splash_screen",
    r"car\/order\/content_info",
    r"order_web\/friendly_information",
    r"promotion-web\/resource",
    r"common\/coupon\/info",
    r"poi\/detail",
    r"search_bff\/hotword",
    r"marketingOperationStructured",
    r"nodefaasv3",
    r"sharedtrip\/taxi\/order_detail_car_tips",
)
AMAP_NATIVE_JQ_PATHS = (
    "search_poi/homepage",
    "dsp/profile/index/nodefaasv3",
    "search_bff/hotword",
    "search_business/process/marketingOperationStructured",
    "sharedtrip/taxi/order_detail_car_tips",
)
YOUTUBE_RSTORE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/youtube.js"
YOUTUBE_ENHANCED = "https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/YouTube/response.min.js"

def consolidate_amap_youtube_ownership(text):
    lines = text.splitlines()
    if AMAP_YOUTUBE_MARKER in text:
        if text.count(AMAP_YOUTUBE_MARKER) != 1 or text.count(AMAP_CANONICAL_RULE) != 1:
            raise ValueError("Amap/YouTube ownership marker/canonical handler drift")
        if any(name in line for line in lines for name in ("ishowshu_amap.js", "rucu6_amap.js")):
            raise ValueError("Amap legacy script owner remains after consolidation")
        if any(line.startswith(("response if ", "http-response ")) and
               "scripts/amap/amap.js" in line and "AMAP-CONSOLIDATED" not in line for line in lines):
            raise ValueError("Amap duplicate local script handler remains")
        for path in AMAP_NATIVE_JQ_PATHS:
            if any(line.startswith("response if ") and path in line.replace(r"\/", "/") and "response.json" in line for line in lines):
                raise ValueError("Amap native rule shadowed by canonical script remains: " + path)
        rstore = [line for line in lines if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line]
        if len(rstore) != 1 or "v[2-9]" not in rstore[0]:
            raise ValueError("YouTube version ownership split drifted")
        return text

    missing_paths = [path for path in AMAP_REQUIRED_PATHS if path not in AMAP_CANONICAL_RULE]
    if missing_paths:
        raise ValueError("Amap canonical matcher does not cover all source routes: " + repr(missing_paths))
    output = []
    amap_seen = {name: 0 for name in AMAP_SCRIPT_COUNTS}
    native_seen = {path: 0 for path in AMAP_NATIVE_JQ_PATHS}
    for line in lines:
        if line.startswith(("http-response ", "response if ")):
            matched_owner = next((name for name in AMAP_SCRIPT_COUNTS if name in line), None)
            if matched_owner:
                amap_seen[matched_owner] += 1
                continue
            normalized_line = line.replace(r"\/", "/")
            matched_native = next((path for path in AMAP_NATIVE_JQ_PATHS
                                   if path in normalized_line and "response.json" in line), None)
            if matched_native:
                native_seen[matched_native] += 1
                continue
        if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line:
            if r"youtubei\/v\d\/" not in line:
                raise ValueError("R-Store YouTube matcher changed unexpectedly")
            if line.count(YOUTUBE_RSTORE) != 1:
                raise ValueError("R-Store YouTube handler duplicated")
            line = line.replace(r"youtubei\/v\d\/", r"youtubei\/v[2-9]\/", 1)
        output.append(line)

    if amap_seen != AMAP_SCRIPT_COUNTS:
        raise ValueError("Amap three-source script inventory changed: " + repr(amap_seen))
    if any(count != 1 for count in native_seen.values()):
        raise ValueError("Amap duplicate native JSON owner inventory changed: " + repr(native_seen))
    rstore = [line for line in output if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line]
    if len(rstore) != 1 or "v[2-9]" not in rstore[0]:
        raise ValueError("R-Store YouTube owner missing or duplicated")
    enhanced_feed = [line for line in output if YOUTUBE_ENHANCED in line and r"youtubei\/v1\/(browse|next|search)" in line]
    enhanced_player = [line for line in output if YOUTUBE_ENHANCED in line and r"youtubei\/v1\/(player|get_watch)" in line]
    if len(enhanced_feed) != 1 or len(enhanced_player) != 1:
        raise ValueError("YouTube v1 enhanced response owners missing or duplicated")
    script_index = next((i for i, line in enumerate(output) if line.strip() == "[Script]"), None)
    if script_index is None:
        raise ValueError("missing [Script] section for ownership marker")
    output[script_index + 1:script_index + 1] = [AMAP_YOUTUBE_MARKER, AMAP_CANONICAL_RULE]
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")

def validate_amap_ownership(text):
    lines = text.splitlines()
    amap = [x for x in lines if x.startswith(("response if ", "http-response ")) and "amap" in x.lower() and "com" in x.lower() and ("script(" in x or "script-path=" in x)]
    if not amap:
        raise ValueError("Amap response handler inventory unexpectedly empty")
    if AMAP_YOUTUBE_MARKER in text and (len(amap) != 1 or amap[0] != AMAP_CANONICAL_RULE):
        raise ValueError("Amap handlers must resolve to the single canonical processor")
    # Every handler must have one explicit processor. This catches accidental
    # multiple processor declarations on a single matcher, not legitimate
    # independent matchers handled by different scripts.
    for line in amap:
        if line.count("script(") + line.count("script-path=") != 1:
            raise ValueError("ambiguous Amap processor ownership: " + line)
    return len(amap)

def validate_youtube_ownership(text):
    lines = text.splitlines()
    youtube = [x for x in lines if x.startswith(("response if ", "request if ", "http-response ", "http-request ")) and
               ("youtubei" in x or "googlevideo" in x or "youtube.com" in x) and
               ("script(" in x or "script-path=" in x)]
    if not youtube:
        raise ValueError("YouTube processor inventory unexpectedly empty")
    for line in youtube:
        if line.count("script(") + line.count("script-path=") != 1:
            raise ValueError("ambiguous YouTube processor ownership: " + line)
    return len(youtube)

def optimize(text):
    text = consolidate_meituan(text)
    text = consolidate_pinduoduo_mrk(text)
    text = consolidate_amap_youtube_ownership(text)
    amap_count = validate_amap_ownership(text)
    youtube_count = validate_youtube_ownership(text)
    return text, amap_count, youtube_count

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    original = path.read_text(encoding="utf-8-sig")
    updated, amap_count, youtube_count = optimize(original)
    path.write_text(updated, encoding="utf-8")
    print("[cross-app-trigger-optimizer] PASS: Meituan triggers consolidated; Pinduoduo mrk merged; Amap three-source ownership consolidated and YouTube version split applied; Amap=%d YouTube=%d handlers checked" % (amap_count, youtube_count))

if __name__ == "__main__":
    main()
