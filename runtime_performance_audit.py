#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only runtime cost audit for Loon Script triggers, JSON parsing and remote assets."""
from __future__ import annotations
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
SCRIPT_URL_RE = re.compile(r"""(?:script-path\s*=\s*|script\(\s*["'])(https?://[^,\s"')]+)""", re.I)
SCRIPT_TRIGGER_RE = re.compile(r"^(http-request|http-response|cron|generic)\s+(\S+)", re.I)
INLINE_SCRIPT_TRIGGER_RE = re.compile(r"^(request|response)\s+if\s+\$\{url\}\s*~=\s*(.+?)\s+then\s+script\(", re.I)
JSON_PARSE_RE = re.compile(r"\bJSON\.parse\s*\(\s*([^()\n]{1,240}?)\s*\)")
COMMIT_RE = re.compile(r"/[0-9a-f]{40}(?:/|$)", re.I)

def parse_sections(text):
    sections, current = defaultdict(list), None
    for number, raw in enumerate(text.splitlines(), 1):
        match = SECTION_RE.match(raw.strip())
        if match:
            current = match.group(1).strip().lower()
        elif current:
            sections[current].append((number, raw.strip()))
    return sections

def parse_script_trigger(line):
    legacy = SCRIPT_TRIGGER_RE.match(line)
    if legacy:
        return legacy.group(1).lower(), legacy.group(2)
    inline = INLINE_SCRIPT_TRIGGER_RE.match(line)
    if inline:
        return inline.group(1).lower(), inline.group(2).strip()
    return None, None


def is_mutable_remote_url(url):
    if COMMIT_RE.search(url):
        return False
    return bool(re.search(r"/(?:main|master|develop|latest|refs/heads/[^/]+)(?:/|$)", url, re.I))

def audit_plugin(plugin_path, repo_root="."):
    plugin_path, root = Path(plugin_path), Path(repo_root)
    sections = parse_sections(plugin_path.read_text(encoding="utf-8-sig"))
    script_rows = [(n, line) for n, line in sections.get("script", []) if line and not line.startswith("#")]
    trigger_types, response_body = Counter(), []
    trigger_groups, url_usage = defaultdict(list), defaultdict(list)
    response_pattern_groups = defaultdict(list)
    script_url_count = 0
    for line_no, line in script_rows:
        kind, url_pattern = parse_script_trigger(line)
        kind = kind or "unclassified"
        trigger_types[kind] += 1
        url_match = SCRIPT_URL_RE.search(line)
        if not url_match:
            continue
        url = url_match.group(1).rstrip(",")
        script_url_count += 1
        url_usage[url].append({"line": line_no, "trigger": kind})
        if url_pattern:
            trigger_groups[(kind, url_pattern, url)].append(line_no)
        if kind in {"http-response", "response"}:
            item = {
                "line": line_no, "trigger_kind": kind, "url_pattern": url_pattern,
                "script_url": url,
                "requires_body": bool(re.search(r"\brequires[-_]body\s*=\s*true\b", line, re.I)),
            }
            response_body.append(item)
            response_pattern_groups[url_pattern].append(item)
    duplicates = [
        {"trigger": key[0], "url_pattern": key[1], "script_url": key[2], "lines": nums}
        for key, nums in sorted(trigger_groups.items()) if len(nums) > 1
    ]
    cross_script_overlaps = [
        {"url_pattern": pattern, "script_urls": sorted({x["script_url"] for x in items}),
         "lines": [x["line"] for x in items]}
        for pattern, items in sorted(response_pattern_groups.items())
        if len({x["script_url"] for x in items}) > 1
    ]
    high_fanout = [
        {"script_url": url, "trigger_count": len(items),
         "response_count": sum(x["trigger"] in {"http-response", "response"} for x in items),
         "lines": [x["line"] for x in items]}
        for url, items in sorted(url_usage.items(), key=lambda item: (-len(item[1]), item[0]))
        if len(items) >= 5
    ]
    mutable = sorted(url for url in url_usage if is_mutable_remote_url(url))
    non_github = sorted(url for url in url_usage if
        (urlparse(url).hostname or "").lower() not in
        {"github.com", "raw.githubusercontent.com", "gist.githubusercontent.com"})
    local_urls = sorted(url for url in url_usage if
        "raw.githubusercontent.com/xcvcvx/loon-change/" in url.lower())
    missing_local = []
    for url in local_urls:
        match = re.search(r"raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/(.+)$", url, re.I)
        if match and not (root / match.group(1)).is_file():
            missing_local.append({"url": url, "path": match.group(1)})
    js_parse = []
    for path in sorted(root.rglob("*.js")):
        if ".git" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        matches = list(JSON_PARSE_RE.finditer(source))
        expressions = Counter(re.sub(r"\s+", " ", m.group(1).strip()) for m in matches)
        repeated = [{"expression": expr, "count": count}
                    for expr, count in sorted(expressions.items()) if count > 1]
        if matches:
            js_parse.append({"path": str(path), "json_parse_calls": len(matches),
                             "repeated_parse_expressions": repeated,
                             "bytes": len(source.encode("utf-8"))})
    summary = {
        "script_entries": len(script_rows),
        "script_trigger_types": dict(sorted(trigger_types.items())),
        "response_script_triggers": len(response_body),
        "http_response_script_triggers": sum(x["trigger_kind"] == "http-response" for x in response_body),
        "inline_response_script_triggers": sum(x["trigger_kind"] == "response" for x in response_body),
        "response_script_requires_body_true": sum(x["requires_body"] for x in response_body),
        "http_response_requires_body_true": sum(x["requires_body"] and x["trigger_kind"] == "http-response" for x in response_body),
        "inline_response_requires_body_true": sum(x["requires_body"] and x["trigger_kind"] == "response" for x in response_body),
        "duplicate_response_patterns_across_scripts": len(cross_script_overlaps),
        "unique_remote_script_urls": len(url_usage),
        "remote_script_url_references": script_url_count,
        "duplicate_script_trigger_groups": len(duplicates),
        "high_fanout_script_urls_ge_5_triggers": len(high_fanout),
        "mutable_branch_remote_urls": len(mutable),
        "non_github_remote_urls": len(non_github),
        "local_repo_remote_urls": len(local_urls),
        "missing_local_repo_assets": len(missing_local),
        "local_js_files_with_json_parse": len(js_parse),
        "local_js_json_parse_calls": sum(x["json_parse_calls"] for x in js_parse),
        "repeated_json_parse_expressions": sum(len(x["repeated_parse_expressions"]) for x in js_parse),
    }
    return {
        "plugin": str(plugin_path), "summary": summary,
        "response_body_script_triggers": response_body, "duplicate_script_triggers": duplicates,
        "duplicate_response_patterns_across_scripts": cross_script_overlaps,
        "high_fanout_script_urls": high_fanout, "mutable_branch_remote_urls": mutable,
        "non_github_remote_urls": non_github, "missing_local_repo_assets": missing_local,
        "local_js_json_parse": js_parse,
        "notes": [
            "只读静态审计，不自动删除脚本、requires-body 或远程依赖。",
            "http-response 与 response if ... then script(...) 都是响应脚本；requires-body=true 表示需要读取响应体，触发次数不等于实际请求次数。",
            "相同响应 URL pattern 被不同脚本处理会列为跨脚本重叠候选；需确认逻辑等价后再移除。",
            "JSON.parse 统计是静态文本计数；重复表达式是优化候选，需结合脚本控制流确认。",
            "分支型 URL 可能是有意跟随上游更新；固定 commit 的 URL 更可复现，但不自动保证运行性能。",
        ],
    }

def render_markdown(report):
    lines = ["# Loon runtime performance audit", "", "## Summary", "",
             "| Metric | Count |", "|---|---:|"]
    lines.extend(f"| {key} | {value} |" for key, value in report["summary"].items())
    lines += ["", "## Response-body script triggers", "",
              "| Line | Trigger | URL pattern | Script | requires-body |", "|---:|---|---|---|---|"]
    for item in report["response_body_script_triggers"]:
        lines.append(f"| {item['line']} | {item['trigger_kind']} | {item['url_pattern']} | {item['script_url']} | {item['requires_body']} |")
    lines += ["", "## Duplicate response patterns across scripts", "",
              "| URL pattern | Script URLs | Lines |", "|---|---|---:|"]
    for item in report["duplicate_response_patterns_across_scripts"]:
        lines.append(f"| {item['url_pattern']} | {'; '.join(item['script_urls'])} | {', '.join(map(str, item['lines']))} |")
    lines += ["", "## High fan-out script URLs (5+ triggers)", "",
              "| Trigger count | Response count | Script URL |", "|---:|---:|---|"]
    for item in report["high_fanout_script_urls"]:
        lines.append(f"| {item['trigger_count']} | {item['response_count']} | {item['script_url']} |")
    lines += ["", "## Mutable branch URLs", ""]
    lines.extend(f"- {url}" for url in report["mutable_branch_remote_urls"])
    lines += ["", "## Local JavaScript JSON.parse hotspots", "",
              "| File | Bytes | JSON.parse calls | Repeated expressions |", "|---|---:|---:|---:|"]
    for item in report["local_js_json_parse"]:
        lines.append(f"| {item['path']} | {item['bytes']} | {item['json_parse_calls']} | {len(item['repeated_parse_expressions'])} |")
    lines += ["", "## Interpretation", ""]
    lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    report = audit_plugin(args.plugin, args.repo_root)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_path:
        Path(args.markdown_path).write_text(render_markdown(report), encoding="utf-8")
    if args.summary_only:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        print("高频脚本 URL（前 15 项）：")
        for item in report["high_fanout_script_urls"][:15]:
            print(f"  {item['trigger_count']} triggers / {item['response_count']} responses: {item['script_url']}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
