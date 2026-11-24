#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collapse overlapping Pinduoduo order response rewrites into one JSON pass."""
import argparse
from pathlib import Path

MARKER = "# loon-change: Pinduoduo order response single-pass JSON cleanup v1"
SHIPPING_RULE = "response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/order\\/\\d+-\\d+\\/shipping/i then response.json.jq(\"del(.shipping.banner_above_recommend)\")"
ORDER_RULE = "response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/order\\//i then response.json.delete([\"marketing_banner_vo\", \"shipping.banner_above_recommend\"])"


QUERY_MATCHER_MARKER = "# loon-change: Pinduoduo redundant query matcher consolidation v1"
EXPECTED_REDUNDANT_QUERY_MATCHERS = 7


def optimize_order_rules(plugin: str) -> str:
    if MARKER in plugin:
        if (plugin.count(MARKER) != 1
                or plugin.count(SHIPPING_RULE) != 0
                or plugin.count(ORDER_RULE) != 1):
            raise ValueError("Pinduoduo order single-pass marker/structure drift")
        return plugin
    if plugin.count(SHIPPING_RULE) != 1 or plugin.count(ORDER_RULE) != 1:
        raise ValueError("Pinduoduo order response rule inventory changed; refusing optimization")
    plugin = plugin.replace(SHIPPING_RULE + "\n", "", 1)
    plugin = plugin.replace(ORDER_RULE, MARKER + "\n" + ORDER_RULE, 1)
    if (plugin.count(MARKER) != 1 or plugin.count(SHIPPING_RULE) != 0
            or plugin.count(ORDER_RULE) != 1):
        raise ValueError("Pinduoduo order single-pass postcondition failed")
    return plugin


def optimize_redundant_query_matchers(plugin: str) -> str:
    lines = plugin.splitlines()
    narrow_rules = [
        line for line in lines
        if "pinduoduo" in line and "\\?/i then reject_dict(200)" in line
    ]
    if QUERY_MATCHER_MARKER in plugin:
        if plugin.count(QUERY_MATCHER_MARKER) != 1 or narrow_rules:
            raise ValueError("Pinduoduo query matcher marker/structure drift")
        return plugin
    if len(narrow_rules) != EXPECTED_REDUNDANT_QUERY_MATCHERS:
        raise ValueError("Pinduoduo query matcher inventory changed; refusing optimization")
    broad_rules = []
    for narrow in narrow_rules:
        broad = narrow.replace("\\?/i then reject_dict(200)", "/i then reject_dict(200)")
        if lines.count(broad) != 1:
            raise ValueError("Pinduoduo broad query matcher missing or duplicated")
        broad_rules.append(broad)
    result = []
    first_broad = broad_rules[0]
    for line in lines:
        if line in narrow_rules:
            continue
        if line == first_broad:
            result.append(QUERY_MATCHER_MARKER)
        result.append(line)
    optimized = "\n".join(result) + ("\n" if plugin.endswith("\n") else "")
    if (optimized.count(QUERY_MATCHER_MARKER) != 1
            or any(optimized.count(rule) != 1 for rule in broad_rules)
            or any(rule in optimized for rule in narrow_rules)):
        raise ValueError("Pinduoduo query matcher postcondition failed")
    return optimized


def optimize_plugin(plugin: str) -> str:
    return optimize_redundant_query_matchers(optimize_order_rules(plugin))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    path.write_text(optimize_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
    print("Pinduoduo order response cleanup consolidated to one native JSON transform")


if __name__ == "__main__":
    main()
