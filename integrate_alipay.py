#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integrate zirawell's Alipay mini-app Loon rules with a pinned, vendored JS dependency."""
import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {"Rule": 4, "Rewrite": 18, "Script": 1}
# aimai-guide.m.taobao.com is an upstream typo: no rule references it.
SKIP_HOSTS = {"aimai-guide.m.taobao.com"}
REQUIRED_HOSTS = {"creditcardapp.bankcomm.com"}  # 有明确 HTTPS Rewrite，但上游 MITM 漏列
UPSTREAM_JS = "https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/zirawell/alipayAdBlock/zirawell_eleme.js"


def parse(text):
    header, sections, current = [], {}, None
    for line in text.splitlines():
        m = re.match(r"^\[([^\]]+)\]\s*$", line.strip())
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
        elif current is None:
            header.append(line)
        else:
            sections[current].append(line)
    return header, sections


def real(lines):
    return [x.strip() for x in lines if x.strip() and not x.lstrip().startswith(("#", ";", "//"))]


def matcher_key(line):
    stage = re.match(r"^(request|response)\s+if\s+", line, re.I)
    if not stage:
        return None
    m = re.search(r"\$\{url\}\s*~=\s*/((?:\\.|[^/])*)/", line)
    if not m:
        return None
    return (stage.group(1).lower(), m.group(1).replace(r"\/", "/"), line.split(" then ", 1)[-1].strip())


def host_list(lines):
    result = []
    for line in lines:
        m = re.match(r"^\s*hostname\s*=\s*(.*)$", line, re.I)
        if m:
            result.extend(x.strip() for x in m.group(1).split(",") if x.strip())
    return result


def validate_source(source, js):
    _, sections = parse(source)
    for name, minimum in EXPECTED.items():
        count = len(real(sections.get(name, [])))
        if count < minimum:
            raise ValueError(f"上游 [{name}] 规则数量异常：{count} < {minimum}")
    hosts = host_list(sections.get("MITM", []))
    if len(hosts) < 8:
        raise ValueError(f"上游 MITM 主机数量异常：{len(hosts)}")
    if not any("zirawell_eleme.js" in x for x in real(sections["Script"])):
        raise ValueError("上游缺少预期的饿了么 JavaScript 依赖")
    if len(js.strip()) < 100 or "<html" in js[:500].lower():
        raise ValueError("饿了么 JavaScript 依赖为空或疑似 HTML 错误页")
    return sections


def integrate(plugin_path, source_path, js_path, repo_js_url, report_path=None, commit=None):
    plugin_path, source_path, js_path = map(Path, (plugin_path, source_path, js_path))
    plugin = plugin_path.read_text(encoding="utf-8-sig")
    source = source_path.read_text(encoding="utf-8-sig")
    js = js_path.read_text(encoding="utf-8-sig")
    incoming = validate_source(source, js)
    header, current = parse(plugin)
    for name in ("Rule", "Rewrite", "Script", "MITM"):
        if name not in current:
            raise ValueError(f"目标插件缺少 [{name}] 区块")

    stats = {"added": {}, "duplicates": {}, "skipped_hosts": sorted(SKIP_HOSTS)}
    for name in ("Rule", "Rewrite", "Script"):
        old = real(current[name])
        add, dup = [], 0
        existing_exact = set(old)
        existing_matchers = {matcher_key(x) for x in old if matcher_key(x)}
        for line in real(incoming.get(name, [])):
            if name == "Script":
                line = line.replace(UPSTREAM_JS, repo_js_url)
            key = matcher_key(line) if name in ("Rewrite", "Script") else None
            if line in existing_exact or (key is not None and key in existing_matchers):
                dup += 1
                continue
            add.append(line)
            existing_exact.add(line)
            if key is not None:
                existing_matchers.add(key)
        if add:
            current[name].extend(["", f"# ===== zirawell alipayAdBlock ({name}) =====", *add])
        stats["added"][name], stats["duplicates"][name] = len(add), dup

    old_hosts = host_list(current["MITM"])
    known = {x.lower() for x in old_hosts}
    declared_hosts = [x for x in host_list(incoming.get("MITM", []))
                      if x.lower() not in SKIP_HOSTS]
    incoming_hosts = list(dict.fromkeys(declared_hosts + sorted(REQUIRED_HOSTS)))
    new_hosts = [x for x in incoming_hosts if x.lower() not in known]
    if new_hosts:
        # Keep a single hostname declaration for this source and do not rewrite existing entries.
        idx = next((i for i in range(len(current["MITM"]) - 1, -1, -1)
                    if re.match(r"^\s*hostname\s*=", current["MITM"][i], re.I)), None)
        if idx is None:
            current["MITM"].append("hostname = " + ", ".join(new_hosts))
        else:
            current["MITM"][idx] = current["MITM"][idx].rstrip() + ", " + ", ".join(new_hosts)
    stats["added"]["MITM"] = len(new_hosts)
    stats["duplicates"]["MITM"] = sum(1 for x in incoming_hosts if x.lower() in known)
    stats["corrected_missing_hosts"] = sorted(REQUIRED_HOSTS - {x.lower() for x in declared_hosts})

    output = list(header)
    while output and not output[-1].strip():
        output.pop()
    for name, lines in current.items():
        normalized_lines = list(lines)
        while normalized_lines and not normalized_lines[-1].strip():
            normalized_lines.pop()
        output.extend(["", f"[{name}]", *normalized_lines])
    plugin_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")

    if report_path:
        report_file = Path(report_path)
        report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else {}
        report["AlipayAdBlock"] = {
            "upstream_repository": "https://github.com/ifflagged/Romeo",
            "upstream_path": "Modules/Loon/zirawell/Beta/alipayAdBlock.lpx",
            "upstream_commit": commit or "unresolved",
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "javascript_path": "sources/alipay/zirawell_eleme.js",
            "javascript_sha256": hashlib.sha256(js.encode()).hexdigest(),
            "integration": stats,
        }
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--js", required=True)
    ap.add_argument("--repo-js-url", required=True)
    ap.add_argument("--report")
    ap.add_argument("--commit")
    args = ap.parse_args()
    stats = integrate(args.plugin, args.source, args.js, args.repo_js_url, args.report, args.commit)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
