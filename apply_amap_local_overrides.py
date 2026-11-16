#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply narrowly scoped, fail-closed overrides to the vendored Amap plugin."""
import argparse
from pathlib import Path

# This standalone rule is already covered by the grouped rule below.
DUPLICATE_HOTWORD_RULE = (
    r'request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search\/new_hotword\?/i '
    r'then reject_dict(200)'
)
CANONICAL_GROUPED_RULE = (
    r'request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/(?:mapapi\/hint_text\/offline_data|message\/notice\/list|shield\/search\/new_hotword)/i '
    r'then reject_dict(200)'
)
HOTWORD_MARKER = "search/new_hotword"

MARKETING_OPERATION_OLD_RULE = "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/shield\\/search_business\\/process\\/marketingOperationStructured\\?/i then response.json.delete([\"data.tipsOperationLocation\", \"obj.data.resourcePlacement\"])"
MARKETING_OPERATION_NEW_RULE = "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/shield\\/search_business\\/process\\/marketingOperationStructured\\?/i then response.json.delete([\"data.tipsOperationLocation\", \"data.resourcePlacement\"])"
MARKETING_OPERATION_MARKER = "marketingOperationStructured"
NATIVE_RESPONSE_SCRIPT_RULES = (
    ("beforeNavi", "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/aos\\/perception\\/publicTravel\\/beforeNavi\\?/i then script(\"https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js\") with tag=\"[高德地图]移除路线规划推广\", requires_body=true", "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/aos\\/perception\\/publicTravel\\/beforeNavi\\?/i then response.json.jq(\"(if (try (.data.common_data.bus_plan_bottom_event.data | type) catch null) == \\\"array\\\" then .data.common_data.bus_plan_bottom_event.data = [] else . end) | (if (try (.data.common_data.bus_plan_bottom_tips.data | type) catch null) == \\\"array\\\" then .data.common_data.bus_plan_bottom_tips.data = [] else . end) | (if (try (.data.common_data.bus_plan_segment_event.data | type) catch null) == \\\"array\\\" then .data.common_data.bus_plan_segment_event.data = [] else . end) | (if (try (.data.front_end.assistant | type) catch null) == \\\"array\\\" then .data.front_end.assistant = [] else . end)\")"),
    ("bus/plan/integrate", "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/bus\\/plan\\/integrate\\?/i then script(\"https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js\") with tag=\"[高德地图]移除路线规划、导航结束页推广\", requires_body=true", "response if ${url} ~= /^https:\\/\\/m5\\.amap\\.com\\/ws\\/bus\\/plan\\/integrate\\?/i then response.json.jq(\"(if (try (.data.banner_lists.data | type) catch null) == \\\"array\\\" then .data.banner_lists.data = [] else . end) | (if (try (.data.banner_lists.tips | type) catch null) == \\\"array\\\" then .data.banner_lists.tips = [] else . end) | (if (try (.data.mixed_plans.data.taxiPlans | type) catch null) == \\\"array\\\" then .data.mixed_plans.data.taxiPlans = [] else . end)\")"),
)



def _normalize(line):
    # Loon plugin serialization may vary the number of backslashes around regex escapes.
    return line.strip().replace("\\", "")


def apply(text):
    """Deduplicate Amap hotword and migrate two safe route response scripts to native JSON."""
    lines = text.splitlines()
    output = []
    section = ""
    duplicate_count = 0
    grouped_count = 0
    marketing_old_count = 0
    marketing_new_count = 0
    unexpected = []
    marketing_unexpected = []
    native_old_counts = {marker: 0 for marker, _old, _new in NATIVE_RESPONSE_SCRIPT_RULES}
    native_new_counts = {marker: 0 for marker, _old, _new in NATIVE_RESPONSE_SCRIPT_RULES}
    native_unexpected = []
    native_to_insert = []
    duplicate_normalized = _normalize(DUPLICATE_HOTWORD_RULE)
    grouped_normalized = _normalize(CANONICAL_GROUPED_RULE)
    marketing_old_normalized = _normalize(MARKETING_OPERATION_OLD_RULE)
    marketing_new_normalized = _normalize(MARKETING_OPERATION_NEW_RULE)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        normalized = _normalize(stripped)
        if stripped.startswith("#"):
            output.append(line)
            continue
        native_matched = False
        for marker, old_rule, native_rule in NATIVE_RESPONSE_SCRIPT_RULES:
            if marker.lower() not in normalized.lower():
                continue
            native_matched = True
            if section == "Script" and normalized == _normalize(old_rule):
                native_old_counts[marker] += 1
            elif section == "Rewrite" and normalized == _normalize(native_rule):
                native_new_counts[marker] += 1
                output.append(line)
            else:
                native_unexpected.append(stripped)
                output.append(line)
            break
        if native_matched:
            continue
        if section != "Rewrite":
            output.append(line)
            continue
        if MARKETING_OPERATION_MARKER.lower() in normalized.lower():
            if normalized == marketing_old_normalized:
                output.append(line.replace("obj.data.resourcePlacement", "data.resourcePlacement"))
                marketing_old_count += 1
            elif normalized == marketing_new_normalized:
                output.append(line)
                marketing_new_count += 1
            else:
                marketing_unexpected.append(stripped)
                output.append(line)
            continue
        if HOTWORD_MARKER not in normalized:
            output.append(line)
            continue
        if normalized == duplicate_normalized:
            duplicate_count += 1
            continue
        if normalized == grouped_normalized:
            grouped_count += 1
            output.append(line)
            continue
        unexpected.append(stripped)
        output.append(line)

    if native_unexpected:
        raise ValueError("Amap route response script changed; refusing an unreviewed native conversion")
    for marker, _old_rule, native_rule in NATIVE_RESPONSE_SCRIPT_RULES:
        old_count = native_old_counts[marker]
        new_count = native_new_counts[marker]
        if old_count > 1 or new_count > 1:
            raise ValueError("duplicate Amap route response rules; refusing ambiguous conversion: " + marker)
        if old_count + new_count != 1:
            raise ValueError("Amap route response rule inventory changed; expected exactly one: " + marker)
        if old_count == 1:
            native_to_insert.append(native_rule)
    if native_to_insert:
        script_index = next((i for i, line in enumerate(output) if line.strip() == "[Script]"), None)
        if script_index is None:
            raise ValueError("Amap plugin missing [Script] section for native route rules")
        output[script_index:script_index] = native_to_insert
    if marketing_unexpected:
        raise ValueError("Amap marketingOperationStructured rule changed; refusing an unreviewed override")
    if marketing_old_count > 1 or marketing_new_count > 1:
        raise ValueError("duplicate Amap marketingOperationStructured rules; refusing ambiguous correction")
    if marketing_old_count + marketing_new_count != 1:
        raise ValueError("Amap marketingOperationStructured rule inventory changed; expected exactly one")
    if unexpected:
        raise ValueError("Amap hotword rule changed; refusing an unreviewed override")
    if grouped_count != 1:
        raise ValueError("Amap grouped hotword rule inventory changed; expected exactly one")
    if duplicate_count > 1:
        raise ValueError("duplicate standalone Amap hotword rules; refusing ambiguous cleanup")
    return "\n".join(output) + ("\n" if text.endswith("\n") else ""), duplicate_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    original = path.read_text(encoding="utf-8-sig")
    updated, removed = apply(original)
    path.write_text(updated, encoding="utf-8")
    print("[amap-local-overrides] PASS: duplicate hotword removed; route response JSON rules normalized; marketing field path corrected")


if __name__ == "__main__":
    main()
