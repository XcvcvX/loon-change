#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducibly optimize Zhihu's high-fanout response script."""
import argparse
from pathlib import Path

REMOTE="https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Scripts/AntiAd/zhihu.js"
LOCAL="https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/zhihu/zhihu.js"
MARKER="// loon-change: Zhihu response hot-path optimization v1; upstream zirawell/R-Store@"

def once(src,old,new,label):
    count=src.count(old)
    if count!=1: raise ValueError(f"{label}: expected one source match, got {count}")
    return src.replace(old,new,1)

HELPERS=r'''
function compactInPlace(items, keep) {
  let write = 0;
  for (let read = 0, length = items.length; read < length; read++) {
    const item = items[read];
    if (keep(item)) { if (write !== read) items[write] = item; write++; }
  }
  items.length = write;
  return items;
}
'''

GET_URL_PARAM=r'''function getUrlParamValue(url, queryName) {
  if (typeof url !== "string") return undefined;
  const question = url.indexOf("?");
  if (question < 0) return undefined;
  const query = url.slice(question + 1).split("#", 1)[0];
  let value;
  for (const part of query.split("&")) {
    const equal = part.indexOf("=");
    const key = equal < 0 ? part : part.slice(0, equal);
    if (key === queryName) value = equal < 0 ? undefined : part.slice(equal + 1);
  }
  return value;
}'''


def optimize_source(src, commit="unknown"):
    if MARKER in src: return src
    src=once(src,"if (!$response.body) $done({});",
             "if (!$response.body) {\n  $done({});\n} else {","body guard")
    src=once(src,"const url = $request.url;","const url = $request.url;\n"+HELPERS.strip(),"in-place helper")
    transforms=[
      ("obj.config.homepage_feed_tab.tab_infos = obj.config.homepage_feed_tab.tab_infos.filter(",
       "compactInPlace(obj.config.homepage_feed_tab.tab_infos, ","homepage tabs",1),
      ("obj.selected_sections = obj.selected_sections.filter(",
       "compactInPlace(obj.selected_sections, ","selected sections",1),
      ("obj.data = obj.data.filter(","compactInPlace(obj.data, ","data arrays",6),
      ("obj.data.data = obj.data.data.filter(","compactInPlace(obj.data.data, ","nested data arrays",2),
      ("obj.tab_list = obj.tab_list.filter(","compactInPlace(obj.tab_list, ","tab list",1),
    ]
    for old,new,label,expected in transforms:
        count=src.count(old)
        if count!=expected: raise ValueError(f"{label}: expected {expected} matches, got {count}")
        src=src.replace(old,new)
    src=src.replace(
      '!["activity", "live"]?.includes(i?.tab_type)',
      '(i?.tab_type !== "activity" && i?.tab_type !== "live")')
    src=src.replace(
      '!["故事", "活动", "想法"]?.includes(i?.tab_name)',
      '(i?.tab_name !== "故事" && i?.tab_name !== "活动" && i?.tab_name !== "想法")')
    src=once(src,
      'let videoID = getUrlParamValue(item.fields.header.url, "videoID");',
      'let videoID = getUrlParamValue(i.fields.header.url, "videoID");',
      "market card variable")
    src=once(src,
      '} else if (url.includes("/topstory/recommend")) {',
      '''} else if (url.includes("/topstory/recommend")) {
  const fallbackSearch = '"feed_content":{"video":{"id":';
  const fallbackIndex = $response.body.indexOf(fallbackSearch);
  const fallbackVideoID = fallbackIndex >= 0
    ? $response.body.slice(fallbackIndex + fallbackSearch.length).split(",", 1)[0]
    : undefined;''',
      "precompute response fallback video id")
    src=once(src,
      '''          let search = '"feed_content":{"video":{"id":';
          let str = $response.body.substring($response.body.indexOf(search) + search.length);
          let videoID = str.substring(0, str.indexOf(","));
          i.common_card.feed_content.video.id = videoID;''',
      '''          if (fallbackVideoID !== undefined) {
            i.common_card.feed_content.video.id = fallbackVideoID;
          }''',
      "avoid repeated full-body scan")
    src=once(src,
      """function getUrlParamValue(url, queryName) {
  return Object.fromEntries(
      url
          .substring(url.indexOf("?") + 1)
          .split("&")
          .map((pair) => pair.split("="))
  )[queryName];
}""",
      GET_URL_PARAM,
      "allocation-free URL parameter parser")
    if src.count("function getUrlParamValue(url, queryName) {") != 1:
        raise ValueError("URL parser definition count drift")
    # Close the response-body guard opened near the top of the script.
    src=src.rstrip()+"\n}\n"
    result=MARKER+commit+"\n"+src
    if (result.count("compactInPlace(")-1)!=11:
        raise ValueError("expected all 11 Zhihu filters to use stable in-place compaction")
    if "Object.fromEntries(" in result or ".map((pair) => pair.split" in result:
        raise ValueError("allocating URL parameter parser remains")
    if "getUrlParamValue(item.fields.header.url" in result:
        raise ValueError("market card undefined variable remains")
    if result.count("fallbackSearch")!=3:
        raise ValueError("fallback response scan was not hoisted exactly once")
    return result


def rewrite_plugin(plugin):
    if LOCAL in plugin:
        if REMOTE in plugin: raise ValueError("mixed local and remote Zhihu script URLs")
        return plugin
    section=None;count=0;out=[]
    for line in plugin.splitlines():
        stripped=line.strip()
        if stripped.startswith("[") and stripped.endswith("]"): section=stripped[1:-1].strip().lower()
        if section=="script" and REMOTE in line:
            count+=line.count(REMOTE)
            line=line.replace(REMOTE,LOCAL)
        out.append(line)
    if count!=8: raise ValueError(f"Zhihu trigger inventory changed: expected 8, got {count}")
    result="\n".join(out)
    if REMOTE in result: raise ValueError("upstream Zhihu URL remains")
    return result+("\n" if plugin.endswith("\n") else "")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source");p.add_argument("--output");p.add_argument("--upstream-commit",default="unknown");p.add_argument("--plugin")
    a=p.parse_args()
    if a.source or a.output:
        if not a.source or not a.output:p.error("--source and --output must be supplied together")
        out=optimize_source(Path(a.source).read_text(encoding="utf-8-sig"),a.upstream_commit)
        Path(a.output).parent.mkdir(parents=True,exist_ok=True)
        Path(a.output).write_text(out,encoding="utf-8")
        print(f"Optimized Zhihu response script: {a.output} ({len(out)} bytes)")
    if a.plugin:
        path=Path(a.plugin)
        path.write_text(rewrite_plugin(path.read_text(encoding="utf-8-sig")),encoding="utf-8")
        print("Routed eight Zhihu response triggers to local optimized script")
    if not(a.source or a.output or a.plugin):p.error("provide source/output and/or plugin")

if __name__=="__main__":main()
