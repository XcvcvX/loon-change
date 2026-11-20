#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a lightweight, allocation-conscious local RRTV response handler."""
from __future__ import annotations

import argparse
from pathlib import Path

REMOTE = "https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/rrtv.js"
LOCAL = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/rrtv/rrtv.js"
EXPECTED_TRIGGERS = 9
MARKER = "// loon-change: RRTV lightweight runtime and response fast paths v1; upstream zirawell/R-Store@"

RUNTIME = '''function createLoonRuntime(name) {
  return {
    isResponse: typeof $response !== "undefined" && $response !== null,
    request: typeof $request !== "undefined" ? $request : {},
    response: typeof $response !== "undefined" ? $response : {},
    logError(error) {
      console.log("[" + name + "] " + error);
    },
    logWarning(message) {
      console.log("[" + name + "] " + message);
    },
    done(value) {
      if (arguments.length === 0) $done();
      else $done(value);
    }
  };
}

function compactInPlace(items, keep) {
  let write = 0;
  const length = items.length;
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

const playbackFlags = /currentQuality":"\\w+|canPlay":false|canShowVip":true|externalAds":true/g;
function rewritePlaybackFlags(body) {
  const rewritten = body.replace(playbackFlags, match => {
    if (match.startsWith('currentQuality":"')) return 'currentQuality":"AI_OD';
    if (match === 'canPlay":false') return 'canPlay":true';
    if (match === 'canShowVip":true') return 'canShowVip":false';
    return 'externalAds":false';
  });
  return rewritten === body ? null : rewritten;
}
'''

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError("RRTV upstream %s anchor changed: expected 1, got %d" % (label, count))
    return source.replace(old, new, 1)


def optimize_source(source: str, commit: str = "unknown") -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("RRTV optimization marker count drift")
        if "function MagicJS(" in source or "new MagicJS(" in source:
            raise ValueError("RRTV optimized snapshot still contains the unused MagicJS framework")
        if source.count("function createLoonRuntime(name)") != 1:
            raise ValueError("RRTV lightweight runtime helper count drift")
        if source.count("function rewritePlaybackFlags(body)") != 1:
            raise ValueError("RRTV playback rewrite helper count drift")
        if source.count("rewritePlaybackFlags(magicJS.response.body)") != 2:
            raise ValueError("RRTV playback rewrite call count drift")
        if ".replace(/currentQuality" in source:
            raise ValueError("RRTV repeated playback regex chain remains")
        if not source.rstrip().endswith("}"):
            raise ValueError("RRTV terminal response guard is missing")
        return source

    # The upstream helper is much larger than the response-only surface used by
    # this script. Retain only the five methods referenced by the rule body.
    runtime_anchor = 'const scriptName = "RRTV";'
    source = replace_once(
        source,
        runtime_anchor,
        RUNTIME + runtime_anchor + '\nif (!$response || !$response.body) {\n  $done({});\n} else {',
        "runtime initialization",
    )
    source = replace_once(
        source,
        'const magicJS = new MagicJS(scriptName, "INFO");',
        'const magicJS = createLoonRuntime(scriptName);',
        "MagicJS construction",
    )

    old_home = '''          for (i = 0; i < obj.data.sections.length; i++) {
            if (obj.data.sections[i].sectionType === "AD" ||
                obj.data.sections[i].sectionType === "SINGLE_IMAGE" ||
                obj.data.sections[i].sectionType === "SHORT_VIDEO") {
              delete obj.data.sections[i];
            }
          }
          body = JSON.stringify(obj);'''
    new_home = '''          const sectionsChanged = compactInPlace(obj.data.sections, section =>
            section.sectionType !== "AD" &&
            section.sectionType !== "SINGLE_IMAGE" &&
            section.sectionType !== "SHORT_VIDEO"
          );
          if (sectionsChanged) body = JSON.stringify(obj);'''
    source = replace_once(source, old_home, new_home, "homepage section filtering")

    old_ad_list = '''          obj.data.adList = [];
          body = JSON.stringify(obj);'''
    new_ad_list = '''          if (obj.data.adList.length !== 0) {
            obj.data.adList = [];
            body = JSON.stringify(obj);
          }'''
    source = replace_once(source, old_ad_list, new_ad_list, "ad list no-op fast path")

    old_playback = '''magicJS.response.body.replace(/currentQuality":"\\w+/g, 'currentQuality":"AI_OD').replace(/canPlay":false/g, 'canPlay":true').replace(/canShowVip":true/g, 'canShowVip":false').replace(/externalAds":true/g, 'externalAds":false')'''
    if source.count(old_playback) != 2:
        raise ValueError("RRTV playback replacement inventory changed: expected 2, got %d" % source.count(old_playback))
    source = source.replace(old_playback, "rewritePlaybackFlags(magicJS.response.body)")

    helper_anchor = '\n// @formatter:off\nfunction MagicJS('
    if source.count(helper_anchor) != 1:
        raise ValueError("RRTV MagicJS framework boundary changed")
    source = source.split(helper_anchor, 1)[0].rstrip() + "\n}\n"
    source = MARKER + commit + "\n" + source

    if "function MagicJS(" in source or "new MagicJS(" in source:
        raise ValueError("RRTV MagicJS framework removal incomplete")
    if source.count("rewritePlaybackFlags(magicJS.response.body)") != 2:
        raise ValueError("RRTV playback rewrite migration incomplete")
    if source.count("compactInPlace(obj.data.sections") != 1:
        raise ValueError("RRTV homepage in-place compaction missing")
    if "if (!$response || !$response.body)" not in source:
        raise ValueError("RRTV empty-body guard missing")
    return source


def rewrite_plugin(plugin: str) -> str:
    local_count = plugin.count(LOCAL)
    remote_count = plugin.count(REMOTE)
    if local_count and remote_count:
        raise ValueError("mixed local and remote RRTV script URLs")
    if local_count:
        if local_count != EXPECTED_TRIGGERS:
            raise ValueError(
                "RRTV local trigger inventory changed: expected %d, got %d"
                % (EXPECTED_TRIGGERS, local_count)
            )
        return plugin
    if remote_count != EXPECTED_TRIGGERS:
        raise ValueError(
            "RRTV trigger inventory changed: expected %d, got %d"
            % (EXPECTED_TRIGGERS, remote_count)
        )
    result = plugin.replace(REMOTE, LOCAL)
    if REMOTE in result or result.count(LOCAL) != EXPECTED_TRIGGERS:
        raise ValueError("RRTV local trigger migration incomplete")
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
        result = optimize_source(
            Path(args.source).read_text(encoding="utf-8-sig"), args.upstream_commit
        )
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result, encoding="utf-8")
        print("Optimized RRTV response script: %s (%d bytes)" % (args.output, len(result)))
    if args.plugin:
        path = Path(args.plugin)
        rewritten = rewrite_plugin(path.read_text(encoding="utf-8-sig"))
        path.write_text(rewritten, encoding="utf-8")
        print("Routed all %d RRTV response triggers to the local handler" % EXPECTED_TRIGGERS)
    if not (args.source or args.output or args.plugin):
        parser.error("provide source/output and/or plugin")


if __name__ == "__main__":
    main()
