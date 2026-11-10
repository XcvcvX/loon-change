#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读审计 Loon 插件的 UDP/443、MITM 通配覆盖与 Script 触发器。"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def parse_sections(text):
    sections = defaultdict(list)
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\[([^\]]+)\]\s*$', line.strip())
        if match:
            current = match.group(1).strip()
        elif current is not None:
            sections[current].append((number, line))
    return sections


def extract_script_url(line):
    """支持 script-path=URL 与 script("URL", ...) 两种写法。"""
    match = re.search(r'script-path=(https?://[^,\s]+)', line, re.I)
    if match:
        return match.group(1).rstrip(',')
    match = re.search(r'''script\(\s*(["'])(https?://.*?)\1''', line, re.I)
    return match.group(2).rstrip(',') if match else None


def is_global_udp_443(line):
    normalized = re.sub(r'\s+', '', line.upper())
    if 'PROTOCOL,UDP' not in normalized or 'DEST-PORT,443' not in normalized:
        return False
    scoped = ('DOMAIN,', 'DOMAIN-SUFFIX,', 'DOMAIN-KEYWORD,',
              'DOMAIN-WILDCARD,', 'URL-REGEX,')
    return not any(token in normalized for token in scoped)


def wildcard_covers(host, wildcard):
    host = host.lower().rstrip('.')
    suffix = wildcard.lower().strip()
    if not suffix.startswith('*.'):
        return False
    suffix = suffix[2:]
    return host.endswith('.' + suffix)


def audit_plugin(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    sections = parse_sections(text)

    rule_rows = [(n, line.strip()) for n, line in sections.get('Rule', [])
                 if line.strip() and not line.lstrip().startswith('#')]
    global_udp = [
        {'line': number, 'rule': line}
        for number, line in rule_rows if is_global_udp_443(line)
    ]

    host_entries = []
    for number, line in sections.get('MITM', []):
        if not re.match(r'^\s*hostname\s*=', line, re.I):
            continue
        host_entries.extend(
            {'line': number, 'host': value.strip()}
            for value in line.split('=', 1)[1].split(',')
            if value.strip()
        )

    positives = [item['host'] for item in host_entries
                 if not item['host'].startswith('-')]
    wildcards = sorted({host.lower() for host in positives
                        if host.startswith('*.')})
    exact_hosts = sorted({host.lower().rstrip('.') for host in positives
                          if not host.startswith('*.')})
    overlaps = sorted({
        host for host in exact_hosts
        if any(wildcard_covers(host, wildcard) for wildcard in wildcards)
    })
    wildcard_apex_missing = sorted({
        wildcard[2:] for wildcard in wildcards
        if wildcard[2:] not in exact_hosts
    })

    script_rows = [(n, line.strip()) for n, line in sections.get('Script', [])
                   if line.strip() and not line.lstrip().startswith('#')]
    trigger_types = Counter()
    script_path_lines = 0
    script_call_lines = 0
    urls = set()
    trigger_groups = defaultdict(list)
    lines_with_remote_url = 0
    for number, line in script_rows:
        match = re.match(
            r'^(http-request|http-response|cron|generic|request\s+if|response\s+if)\b',
            line, re.I
        )
        kind = re.sub(r'\s+', ' ', match.group(1).lower()) if match else 'unclassified'
        trigger_types[kind] += 1
        if re.search(r'script-path\\s*=', line, re.I):
            script_path_lines += 1
        if re.search(r'script\s*\(', line, re.I):
            script_call_lines += 1
        url = extract_script_url(line)
        if url:
            urls.add(url)
            lines_with_remote_url += 1
        trigger = re.match(r'^(http-request|http-response)\s+(\S+)', line, re.I)
        if trigger and url:
            key = (trigger.group(1).lower(), trigger.group(2), url)
            trigger_groups[key].append(number)

    duplicate_triggers = [
        {'phase': key[0], 'url_pattern': key[1], 'script_url': key[2],
         'lines': line_numbers}
        for key, line_numbers in sorted(trigger_groups.items())
        if len(line_numbers) > 1
    ]
    non_script_actions = [
        {'line': number, 'entry': line}
        for number, line in script_rows
        if re.match(r'^(?:request|response)\\s+if\\b', line)
        and ' then ' in line
        and not re.search(r'\\bscript\\s*\\(', line, re.I)
        and not re.search(r'\\bscript-path\\s*=', line, re.I)
    ]

    return {
        'plugin': str(path),
        'summary': {
            'rule_entries': len(rule_rows),
            'global_udp_443_rules': len(global_udp),
            'mitm_hostname_entries': len(host_entries),
            'mitm_unique_positive_hosts': len(set(positives)),
            'mitm_wildcards': len(wildcards),
            'mitm_exact_hosts_covered_by_wildcards': len(overlaps),
            'mitm_wildcard_apex_not_explicit': len(wildcard_apex_missing),
            'script_triggers': len(script_rows),
            'script_path_lines': script_path_lines,
            'script_call_lines': script_call_lines,
            'unique_remote_script_urls': len(urls),
            'script_lines_without_remote_url': len(script_rows) - lines_with_remote_url,
            'duplicate_script_trigger_groups': len(duplicate_triggers),\n            'script_entries_without_script_action': len(non_script_actions),
        },
        'global_udp_443_rules': global_udp,
        'mitm_wildcard_overlap_candidates': overlaps,
        'mitm_wildcard_apex_not_explicit': wildcard_apex_missing,
        'script_trigger_types': dict(sorted(trigger_types.items())),
        'duplicate_script_triggers': duplicate_triggers,\n        'script_entries_without_script_action': non_script_actions,
        'unique_remote_script_urls': sorted(urls),
        'notes': [
            '本报告只提供审计线索，不自动删除或改写任何规则。',
            '全局 UDP/443 可能影响 HTTP/3/QUIC；必须结合设备实测决定是否调整。',
            'MITM 通配覆盖候选不等于可直接删除项；需确认 Loon 实际匹配及来源意图。',
            '远程脚本 URL 可达性不代表脚本逻辑正确，也不代表脚本执行无性能开销。',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description='Read-only Loon plugin runtime risk audit')
    parser.add_argument('plugin')
    parser.add_argument('--output', help='可选 JSON 报告路径')
    parser.add_argument('--summary-only', action='store_true',
                        help='只打印摘要和少量风险样例，适合 CI 日志')
    args = parser.parse_args()
    report = audit_plugin(args.plugin)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    if args.summary_only:
        print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
        print('全局 UDP/443 规则：')
        for item in report['global_udp_443_rules']:
            print('  line %s: %s' % (item['line'], item['rule']))
        print('MITM 通配覆盖候选（前 15 项）：%s' %
              ', '.join(report['mitm_wildcard_overlap_candidates'][:15]))
    else:
        print(rendered)


if __name__ == '__main__':
    main()
