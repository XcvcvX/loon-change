#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reapply reviewed low-allocation transformations to the consolidated Goofish handler."""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "// loon-change: Goofish per-response allocation hot-path optimization v1"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError("Goofish %s anchor changed: expected 1, got %d" % (label, count))
    return source.replace(old, new, 1)


def validate_optimized_source(source: str) -> str:
    required = (
        MARKER,
        "const isSupportedPath =",
        "function hasEnumerableKeys(value)",
        "for (const key in node)",
        "AD_TEMPLATE_NAMES.has(templateName)",
        'index === "0" || index === "1" || index === "3"',
        'templateName !== "idlefish_search_card_category_select"',
    )
    forbidden = (
        "const supportedPaths = [",
        "supportedPaths.some(",
        "Object.keys(node)",
        "Object.keys(current)",
        "const keepIndexes = new Set([",
        "const excludedTemplates = new Set([",
        "const adTemplate =",
        "AD_TEMPLATE_RE.test(",
    )
    missing = [token for token in required if token not in source]
    stale = [token for token in forbidden if token in source]
    if missing or stale:
        raise ValueError("Goofish optimized source drift; missing=%r forbidden=%r" % (missing, stale))
    return source


def optimize_source(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("Goofish optimization marker count drift")
        return validate_optimized_source(source)

    source = replace_once(
        source,
        """  const supportedPaths = [
      "/mtop.taobao.idlehome.home.nextfresh",
      "/mtop.taobao.idle.local.home",
      "/mtop.taobao.idle.home.whale.modulet",
      "/mtop.idle.user.page.my.adapter",
      "/mtop.taobao.idlehome.home.circle.list",
      "/mtop.taobao.idle.local.nearby.itemdetail.enter",
      "/mtop.taobao.idlemtopsearch.search",
      "/mtop.taobao.idle.local.flow.plat.section"
    ];
    if (!supportedPaths.some(path => url.includes(path))) return $done({});""",
        """  const isSupportedPath =
    url.includes("/mtop.taobao.idlehome.home.nextfresh") ||
    url.includes("/mtop.taobao.idle.local.home") ||
    url.includes("/mtop.taobao.idle.home.whale.modulet") ||
    url.includes("/mtop.idle.user.page.my.adapter") ||
    url.includes("/mtop.taobao.idlehome.home.circle.list") ||
    url.includes("/mtop.taobao.idle.local.nearby.itemdetail.enter") ||
    url.includes("/mtop.taobao.idlemtopsearch.search") ||
    url.includes("/mtop.taobao.idle.local.flow.plat.section");
  if (!isSupportedPath) return $done({});""",
        "supported-path array",
    )
    source = replace_once(
        source,
        """      for (const key of Object.keys(node)) {
        if (key === "realTimeAd" && node[key] && typeof node[key] === "object") {
          delete node[key];
          removed++;
        } else {
          stack.push(node[key]);
        }
      }""",
        """      for (const key in node) {
        if (!Object.prototype.hasOwnProperty.call(node, key)) continue;
        const child = node[key];
        if (key === "realTimeAd" && child && typeof child === "object") {
          delete node[key];
          removed++;
        } else {
          stack.push(child);
        }
      }""",
        "splash object traversal",
    )
    source = replace_once(
        source,
        """    return items;
  }
  const body = $response && $response.body;""",
        """    return items;
  }

  function hasEnumerableKeys(value) {
    for (const key in value) {
      if (Object.prototype.hasOwnProperty.call(value, key)) return true;
    }
    return false;
  }

  const body = $response && $response.body;""",
        "enumerable-key helper",
    )
    source = replace_once(source, "Object.keys(current).length > 0", "hasEnumerableKeys(current)",
                          "recycle-card key check")
    source = replace_once(
        source,
        'const AD_TEMPLATE_RE = /^(fish_home_advertise_card_d[34]|fish_local_advertise_card_d4|idlefish_local_feed2_marketing|fish_home_feeds_pager_banner|detail_recommend_ad_card)$/;\n',
        "",
        "unused template regex",
    )
    source = replace_once(
        source,
        """        const excludedTemplates = new Set([
          "fish_home_yunying_card_d3",
          "idlefish_seafood_market",
          "fish_home_chat_room"
        ]);
""",
        "",
        "homepage excluded-template Set",
    )
    source = replace_once(
        source,
        "excludedTemplates.has(templateName) || AD_TEMPLATE_NAMES.has(templateName) ||",
        '(templateName === "fish_home_yunying_card_d3" ||\n'
        '             templateName === "idlefish_seafood_market" ||\n'
        '             templateName === "fish_home_chat_room") || AD_TEMPLATE_NAMES.has(templateName) ||',
        "homepage Set lookup",
    )
    source = replace_once(
        source,
        '        const adTemplate = /^(fish_home_advertise_card_d[34]|fish_local_advertise_card_d4|idlefish_local_feed2_marketing|fish_home_feeds_pager_banner|detail_recommend_ad_card)$/;\n',
        "",
        "unused local template regex",
    )
    source = replace_once(source, '!AD_TEMPLATE_RE.test(templateName || "")',
                          "!AD_TEMPLATE_NAMES.has(templateName)", "local-home template matcher")
    source = replace_once(source, '!AD_TEMPLATE_RE.test(dataTemplateName || "")',
                          "!AD_TEMPLATE_NAMES.has(dataTemplateName)", "local-home data-template matcher")
    source = replace_once(
        source,
        '''      const keepIndexes = new Set(["0", "1", "3"]);
      compactTracked(data.container.sections, item =>
        item && keepIndexes.has(String(item.index))
      );''',
        '''      compactTracked(data.container.sections, item => {
        const index = item && String(item.index);
        return index === "0" || index === "1" || index === "3";
      });''',
        "user-center index Set",
    )
    source = replace_once(
        source,
        '''      const excludedTemplates = new Set([
        "idlefish_search_card_category_select",
        "idlefish_search_spu_market_publish"
      ]);
''',
        "",
        "search excluded-template Set",
    )
    source = replace_once(
        source,
        "return !excludedTemplates.has(templateName);",
        'return templateName !== "idlefish_search_card_category_select" &&\n'
        '          templateName !== "idlefish_search_spu_market_publish";',
        "search Set lookup",
    )
    return validate_optimized_source(MARKER + "\n" + source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    path = args.runtime
    result = optimize_source(path.read_text(encoding="utf-8-sig"))
    path.write_text(result, encoding="utf-8")
    print("Applied/verified Goofish allocation fast paths: %s (%d bytes)" % (path, len(result)))


if __name__ == "__main__":
    main()
