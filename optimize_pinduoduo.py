#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collapse overlapping Pinduoduo order response rewrites into one JSON pass."""
import argparse
from pathlib import Path

MARKER = "# loon-change: Pinduoduo order response single-pass JSON cleanup v1"
SHIPPING_RULE = "response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/order\\/\\d+-\\d+\\/shipping/i then response.json.jq(\"del(.shipping.banner_above_recommend)\")"
ORDER_RULE = "response if ${url} ~= /^https:\\/\\/api\\.pinduoduo\\.com\\/order\\//i then response.json.delete([\"marketing_banner_vo\", \"shipping.banner_above_recommend\"])"


def optimize_plugin(plugin: str) -> str:
    if MARKER in plugin:
        if (plugin.count(MARKER) != 1
                or plugin.count(SHIPPING_RULE) != 0
                or plugin.count(ORDER_RULE) != 1):
            raise ValueError("Pinduoduo order single-pass marker/structure drift")
        return plugin
    if plugin.count(SHIPPING_RULE) != 1 or plugin.count(ORDER_RULE) != 1:
        raise ValueError("Pinduoduo order response rule inventory changed; refusing optimization")
    # The broad /order/ handler already deletes shipping.banner_above_recommend.
    # Keeping the shipping-specific jq handler causes a second JSON transform for
    # the same response, so remove it and retain the existing native delete action.
    plugin = plugin.replace(SHIPPING_RULE + "\n", "", 1)
    plugin = plugin.replace(ORDER_RULE, MARKER + "\n" + ORDER_RULE, 1)
    if (plugin.count(MARKER) != 1 or plugin.count(SHIPPING_RULE) != 0
            or plugin.count(ORDER_RULE) != 1):
        raise ValueError("Pinduoduo order single-pass postcondition failed")
    return plugin


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    path.write_text(optimize_plugin(path.read_text(encoding="utf-8-sig")), encoding="utf-8")
    print("Pinduoduo order response cleanup consolidated to one native JSON transform")


if __name__ == "__main__":
    main()
