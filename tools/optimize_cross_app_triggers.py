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
    print("[cross-app-trigger-optimizer] PASS: Meituan legacy triggers consolidated; Pinduoduo mrk rules merged; Amap=%d YouTube=%d handlers ownership-checked" % (amap_count, youtube_count))

if __name__ == "__main__":
    main()
