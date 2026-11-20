#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a lightweight, allocation-conscious local Soul response handler."""
from __future__ import annotations

import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/soul.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/soul/soul.js"
EXPECTED_TRIGGERS = 9
MARKER = "// loon-change: Soul lightweight response runtime and in-place cleanup v1; upstream zirawell/R-Store@"

HANDLER = r'''const GAME_TITLES_TO_REMOVE = [
  "异世界回响", "狼人魅影", "梦想海岛王", "幻想星球",
  "爆弹喵", "星球实验室", "兴趣群组", "群聊派对"
];

(function () {
  const request = typeof $request !== "undefined" && $request ? $request : {};
  const response = typeof $response !== "undefined" && $response ? $response : {};
  const req_url = request.url || "";
  const rsp_body = response.body;

  if (typeof rsp_body !== "string" || rsp_body.length === 0) {
    $done({});
    return;
  }

  let mod_rsp;
  try {
    mod_rsp = JSON.parse(rsp_body);
  } catch (error) {
    console.log("[Soul] invalid JSON; keeping original response: " + error.message);
    $done({});
    return;
  }

  let modified = false;
  try {
    const shouldDeleteData =
      req_url.includes("/post/homepage/guide/card") ||
      req_url.includes("/furion/position/content") ||
      req_url.includes("/hot/soul/rank") ||
      req_url.includes("/post/gift/list") ||
      req_url.includes("/mobile/app/version/queryIos") ||
      req_url.includes("/teenager/config") ||
      req_url.includes("/winterfell/v2/getIpByDomain") ||
      req_url.includes("/official/scene/module");

    const shouldModifyLimitInfo =
      req_url.includes("/chat/limitInfo") &&
      mod_rsp && mod_rsp.data &&
      mod_rsp.data.limit !== undefined;

    if (mod_rsp && mod_rsp.data && shouldDeleteData) {
      delete mod_rsp.data;
      modified = true;
    }

    if (shouldModifyLimitInfo && mod_rsp.data.limit !== false) {
      mod_rsp.data.limit = false;
      modified = true;
    }

    if (req_url.includes("/v6/planet/config") && mod_rsp && mod_rsp.data) {
      const data = mod_rsp.data;
      if (data.gameInfo && Array.isArray(data.gameInfo.gameCards)) {
        modified = compactInPlace(data.gameInfo.gameCards, card =>
          GAME_TITLES_TO_REMOVE.indexOf(card.title) === -1
        ) || modified;
      }

      if (Array.isArray(data.coreCards)) {
        modified = compactInPlace(data.coreCards, card =>
          GAME_TITLES_TO_REMOVE.indexOf(card.title) === -1
        ) || modified;

        for (let i = 0; i < data.coreCards.length; i++) {
          const card = data.coreCards[i];
          if (card && Array.isArray(card.secondCards)) {
            modified = compactInPlace(card.secondCards, item =>
              GAME_TITLES_TO_REMOVE.indexOf(item.title) === -1
            ) || modified;
          }
        }
      }
    }

    if (mod_rsp && mod_rsp.data && Array.isArray(mod_rsp.data.coreCards)) {
      const cards = mod_rsp.data.coreCards;
      for (let i = 0; i < cards.length; i++) {
        if (cards[i].style === 2) {
          cards[i].style = 1;
          modified = true;
        }
      }
    }
  } catch (error) {
    console.log("[Soul] response cleanup failed; keeping original response: " + error.message);
    $done({});
    return;
  }

  if (modified) {
    $done({body: JSON.stringify(mod_rsp)});
  } else {
    $done({});
  }
})();

function compactInPlace(items, keep) {
  const length = items.length;
  let write = 0;
  for (let read = 0; read < length; read++) {
    const item = items[read];
    if (keep(item)) {
      if (write !== read) items[write] = item;
      write++;
    }
  }
  if (write === length) return false;
  items.length = write;
  return true;
}

'''


def optimize_source(source: str, commit: str = "unknown") -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("Soul optimization marker count drift")
        for required in ("function compactInPlace(items, keep)", "const GAME_TITLES_TO_REMOVE = ["):
            if source.count(required) != 1:
                raise ValueError("Soul optimized runtime helper drift: " + required)
        if "function Env(" in source or "new Env(" in source:
            raise ValueError("Soul optimized snapshot still contains the unused Env framework")
        if ".filter(" in source or ".map(" in source:
            raise ValueError("Soul allocating Array.filter/map call remains")
        if "if (modified)" not in source:
            raise ValueError("Soul lazy serialization guard is missing")
        return source

    required_anchors = (
        'const $ = new Env("soul去广告");',
        "const shouldDeleteData =",
        "const shouldModifyLimitInfo =",
        "const gamesToRemove = [",
        "mod_rsp.data.gameInfo.gameCards = mod_rsp.data.gameInfo.gameCards.filter",
        "mod_rsp.data.coreCards = mod_rsp.data.coreCards.filter",
        "mod_rsp.data.coreCards = mod_rsp.data.coreCards.map",
        "function Env(t,e)",
        "/post/homepage/guide/card",
        "/furion/position/content",
        "/hot/soul/rank",
        "/post/gift/list",
        "/mobile/app/version/queryIos",
        "/teenager/config",
        "/winterfell/v2/getIpByDomain",
        "/official/scene/module",
    )
    missing = [anchor for anchor in required_anchors if anchor not in source]
    if missing:
        raise ValueError("Soul upstream behavior/runtime anchors changed: " + ", ".join(missing))
    return MARKER + commit + "\n" + HANDLER + "\n"


def rewrite_plugin(plugin: str) -> str:
    local_count = plugin.count(LOCAL)
    remote_count = plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote Soul script URLs")
    if local_count:
        if local_count != EXPECTED_TRIGGERS:
            raise ValueError("Soul local trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, local_count))
        return plugin
    if remote_count != EXPECTED_TRIGGERS:
        raise ValueError("Soul trigger inventory changed: expected %d, got %d" % (EXPECTED_TRIGGERS, remote_count))
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != EXPECTED_TRIGGERS:
        raise ValueError("Soul local trigger migration incomplete")
    return result


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
        result = optimize_source(Path(args.source).read_text(encoding="utf-8-sig"), args.upstream_commit)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized Soul response script: %s (%d bytes)" % (args.output, len(result.encode("utf-8"))))
    if args.plugin:
        path = Path(args.plugin)
        rewritten = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(rewritten, encoding="utf-8")
        print("Routed all %d Soul response triggers to the local optimized handler" % EXPECTED_TRIGGERS)
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
