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



AMAP_YOUTUBE_MARKER = "# loon-change: Amap/YouTube processor ownership split v1"
AMAP_DUPLICATE_PATHS = (
    ("beforeNavi", r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/aos\/perception\/publicTravel\/beforeNavi\?/i then response.json.jq('),
    ("busPlan", r'response if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/bus\/plan\/integrate\?/i then response.json.jq('),
)
YOUTUBE_RSTORE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/youtube.js"
YOUTUBE_ENHANCED = "https://raw.githubusercontent.com/devchristian1337/loon-plugins/refs/heads/main/Scripts/YouTube/response.min.js"

def consolidate_amap_youtube_ownership(text):
    lines = text.splitlines()
    if AMAP_YOUTUBE_MARKER in text:
        if text.count(AMAP_YOUTUBE_MARKER) != 1:
            raise ValueError("Amap/YouTube ownership marker duplicated")
        if any(r"m\d\.amap\.com" in line and "scripts/amap/amap.js" in line and
               any(path in line for path in ("beforeNavi", r"bus\/plan\/integrate")) for line in lines):
            raise ValueError("Amap ownership split drifted; legacy broad matcher remains")
        rstore = [line for line in lines if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line]
        if len(rstore) != 1 or "v[2-9]" not in rstore[0]:
            raise ValueError("YouTube version ownership split drifted")
        return text

    output = []
    amap_seen = {"beforeNavi": 0, "busPlan": 0}
    for line in lines:
        if line.startswith("http-response ") and "scripts/amap/amap.js" in line:
            if "beforeNavi" in line or r"bus\/plan\/integrate" in line:
                key = "beforeNavi" if "beforeNavi" in line else "busPlan"
                if r"m\d\.amap\.com" not in line:
                    raise ValueError("Amap broad matcher changed unexpectedly: " + key)
                amap_seen[key] += 1
                line = line.replace(r"m\d\.amap\.com", r"m[0-46-9]\.amap\.com", 1)
        if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line:
            if r"youtubei\/v\d\/" not in line:
                raise ValueError("R-Store YouTube matcher changed unexpectedly")
            if line.count(YOUTUBE_RSTORE) != 1:
                raise ValueError("R-Store YouTube handler duplicated")
            line = line.replace(r"youtubei\/v\d\/", r"youtubei\/v[2-9]\/", 1)
        output.append(line)

    if amap_seen != {"beforeNavi": 1, "busPlan": 1}:
        raise ValueError("Amap duplicate processor inventory changed: " + repr(amap_seen))
    for _key, matcher in AMAP_DUPLICATE_PATHS:
        if sum(matcher in line for line in lines) != 1:
            raise ValueError("Amap native JSON owner missing or duplicated")
    rstore = [line for line in output if YOUTUBE_RSTORE in line and "tag=YOUTUBE" in line]
    if len(rstore) != 1 or "v[2-9]" not in rstore[0]:
        raise ValueError("R-Store YouTube owner missing or duplicated")
    enhanced_feed = [line for line in output if YOUTUBE_ENHANCED in line and r"youtubei\/v1\/(browse|next|search)" in line]
    enhanced_player = [line for line in output if YOUTUBE_ENHANCED in line and r"youtubei\/v1\/(player|get_watch)" in line]
    if len(enhanced_feed) != 1 or len(enhanced_player) != 1:
        raise ValueError("YouTube v1 enhanced response owners missing or duplicated")
    marker_index = next((i for i, line in enumerate(output) if line.strip() == "[Script]"), None)
    if marker_index is None:
        raise ValueError("missing [Script] section for ownership marker")
    output.insert(marker_index + 1, AMAP_YOUTUBE_MARKER)
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")

def validate_amap_ownership(text):
    lines = text.splitlines()
    amap = [x for x in lines if x.startswith(("response if ", "http-response ")) and "amap" in x.lower() and "com" in x.lower() and ("script(" in x or "script-path=" in x)]
    if not amap:
        raise ValueError("Amap response handler inventory unexpectedly empty")
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
    print("[cross-app-trigger-optimizer] PASS: Meituan triggers consolidated; Pinduoduo mrk merged; Amap/YouTube ownership split applied; Amap=%d YouTube=%d handlers checked" % (amap_count, youtube_count))

if __name__ == "__main__":
    main()
