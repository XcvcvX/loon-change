#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读运行时风险审计：Rewrite 宽泛/冲突候选、MITM 守卫候选、Script 与远程依赖。"""
import argparse
import concurrent.futures
import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*$')
URL_RE = re.compile(r'https?://([^/\s,?]+)', re.I)
SCRIPT_URL_RE = re.compile(r'''script\(\s*(["'])(https?://.*?)\1|script-path\s*=\s*(https?://[^,\s]+)''', re.I)
BROAD_REJECT_PATTERNS = {'.*', '.+', '^.*$', '^https?://.*', 'https?://.*', '^https://.*'}


def parse_sections(content):
    sections = defaultdict(list)
    current = None
    for number, raw in enumerate(content.splitlines(), 1):
        match = SECTION_RE.match(raw.strip())
        if match:
            current = match.group(1).strip().lower()
        elif current:
            line = raw.strip()
            if line and not line.startswith('#'):
                sections[current].append((number, line))
    return sections


def extract_remote_urls(line):
    found = []
    for match in SCRIPT_URL_RE.finditer(line):
        url = match.group(2) or match.group(3)
        if url:
            found.append(url.rstrip(','))
    return found


def extract_regex_and_action(line):
    """保守抽取 Rewrite 行的 URL 正则和末尾动作；无法确认时返回 None。"""
    match = re.search(r'~=?\s*/((?:\\.|[^/])*)/([a-z]*)', line, re.I)
    if match:
        pattern = match.group(1).replace('\\/', '/')
        tail = line[match.end():].strip()
        action_text = tail.split(' | ', 1)[0].strip()
        tail_parts = action_text.split()
        action = (tail_parts[1] if len(tail_parts) > 1 and tail_parts[0].lower() == 'then'
                  else (tail_parts[0] if tail_parts else '')).lower()
        return pattern, action
    # 旧式 Rewrite：pattern action
    parts = line.split()
    if len(parts) >= 2 and ('reject' in parts[-1].lower() or 'replace' in parts[-1].lower()
                            or parts[-1].lower() in {'302', '307', 'reject-img', 'reject-dict'}):
        return parts[0], parts[-1].lower()
    return None


def is_broad_reject(pattern, action):
    compact = re.sub(r'\s+', '', pattern).lower()
    rejecting = any(token in action for token in ('reject', 'block', 'deny'))
    if not rejecting:
        return False
    if compact in BROAD_REJECT_PATTERNS:
        return True
    # 仅报告非常宽的 URL 前缀拦截；不把一般通配符或长业务正则误判为宽泛。
    return compact in {'^https?://', 'https?://', '^http://', '^https://'}


def host_matches_pattern(host, pattern):
    host = host.lower().rstrip('.')
    pattern = pattern.lower().strip()
    if pattern.startswith('*.'):
        return host.endswith('.' + pattern[2:])
    return host == pattern


def audit_runtime(path):
    content = Path(path).read_text(encoding='utf-8-sig')
    sections = parse_sections(content)
    rewrite_rows = sections.get('rewrite', [])
    script_rows = sections.get('script', [])
    mitm_rows = sections.get('mitm', [])

    parsed_rewrites = []
    broad_rejects = []
    pattern_actions = defaultdict(list)
    for number, line in rewrite_rows:
        parsed = extract_regex_and_action(line)
        if not parsed:
            continue
        pattern, action = parsed
        parsed_rewrites.append((number, pattern, action, line))
        phase_match = re.match(r'^(request|response)\s+if\b', line, re.I)
        phase = phase_match.group(1).lower() if phase_match else 'rewrite'
        pattern_actions[(phase, pattern)].append({'line': number, 'phase': phase, 'action': action, 'entry': line})
        if is_broad_reject(pattern, action):
            broad_rejects.append({'line': number, 'pattern': pattern, 'action': action, 'entry': line})

    rewrite_conflicts = []
    for (phase, pattern), entries in sorted(pattern_actions.items()):
        actions = sorted({entry['action'] for entry in entries})
        if len(actions) > 1:
            rewrite_conflicts.append({'phase': phase, 'pattern': pattern, 'actions': actions, 'entries': entries})

    # 从 Rewrite/Script 守卫中提取可识别的 URL hostname；只作为 MITM 覆盖候选依据。
    guarded_hosts = set()
    for _, line in rewrite_rows + script_rows:
        normalized_line = line.replace('\\/', '/')
        for host in URL_RE.findall(normalized_line.split(' then ', 1)[0]):
            host = host.lower().rstrip('.')
            if host and not host.replace('.', '').isdigit():
                guarded_hosts.add(host)

    mitm_hosts = []
    for number, line in mitm_rows:
        if not re.match(r'^hostname\s*=', line, re.I):
            continue
        for raw_host in line.split('=', 1)[1].split(','):
            host = raw_host.strip().lower()
            if host:
                mitm_hosts.append({'line': number, 'host': host})

    mitm_without_literal_guard = []
    for item in mitm_hosts:
        host = item['host']
        if host.startswith('-'):
            continue
        # wildcard host requires a literal exact/suffix URL guard; do not infer broad wildcard equivalence.
        if not any(host_matches_pattern(g, host) or
                   (host.startswith('*.') and g.endswith('.' + host[2:]))
                   for g in guarded_hosts):
            mitm_without_literal_guard.append(item)

    trigger_counts = defaultdict(list)
    remote_urls = set()
    for number, line in script_rows:
        for url in extract_remote_urls(line):
            remote_urls.add(url)
        match = re.match(r'^(http-request|http-response|request|response)\b', line, re.I)
        if match:
            phase = match.group(1).lower().replace('http-', '')
            guard = re.search(r'~=?\s*/((?:\\.|[^/])*)/', line, re.I)
            pattern = guard.group(1).replace('\\/', '/') if guard else line.split(' then ', 1)[0]
            key = (phase, pattern, tuple(extract_remote_urls(line)))
            trigger_counts[key].append(number)
    duplicate_script_triggers = [
        {'phase': key[0], 'url_pattern': key[1], 'script_urls': list(key[2]), 'lines': lines}
        for key, lines in sorted(trigger_counts.items(), key=lambda item: str(item[0]))
        if len(lines) > 1
    ]

    return {
        'plugin': str(path),
        'summary': {
            'rewrite_entries': len(rewrite_rows),
            'rewrite_patterns_parsed': len(parsed_rewrites),
            'broad_reject_candidates': len(broad_rejects),
            'rewrite_conflict_patterns': len(rewrite_conflicts),
            'mitm_hostname_entries': len(mitm_hosts),
            'mitm_without_literal_guard_candidates': len(mitm_without_literal_guard),
            'script_entries': len(script_rows),
            'duplicate_script_trigger_groups': len(duplicate_script_triggers),
            'unique_remote_script_urls': len(remote_urls),
        },
        'broad_reject_candidates': broad_rejects,
        'rewrite_conflicts': rewrite_conflicts,
        'mitm_without_literal_guard_candidates': mitm_without_literal_guard,
        'duplicate_script_triggers': duplicate_script_triggers,
        'remote_script_urls': sorted(remote_urls),
        'remote_script_health': [],
        'notes': [
            '所有条目均为静态候选，不代表确认误伤、无用 MITM 或可安全删除。',
            'MITM 守卫匹配仅识别字面 URL hostname；复杂正则、Argument 和动态脚本请求可能造成漏报。',
            '远程 HEAD 成功只代表端点响应，不代表脚本内容或运行逻辑正确。',
            '审计器不会修改插件规则、MITM、Script 或远程依赖。',
        ],
    }


def check_url(url, timeout):
    request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'loon-change-audit/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {'url': url, 'status': response.status, 'final_url': response.geturl()}
    except urllib.error.HTTPError as error:
        return {'url': url, 'status': error.code, 'error': 'HTTPError'}
    except Exception as error:
        return {'url': url, 'status': None, 'error': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description='Read-only Loon runtime risk audit')
    parser.add_argument('plugin')
    parser.add_argument('--output', help='JSON 报告输出路径')
    parser.add_argument('--check-remote', action='store_true', help='对远程 Script URL 发起 HEAD 检查')
    parser.add_argument('--limit', type=int, default=80, help='最多检查多少个唯一 URL（默认 80）')
    parser.add_argument('--timeout', type=float, default=8.0, help='单个 HEAD 超时秒数')
    args = parser.parse_args()
    report = audit_runtime(args.plugin)
    if args.check_remote:
        urls = report['remote_script_urls'][:max(0, args.limit)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            report['remote_script_health'] = list(pool.map(lambda url: check_url(url, args.timeout), urls))
        report['remote_script_health_summary'] = {
            'checked': len(urls),
            'ok': sum(1 for item in report['remote_script_health'] if item['status'] is not None and 200 <= item['status'] < 400),
            'failed_or_unconfirmed': sum(1 for item in report['remote_script_health'] if item['status'] is None or item['status'] >= 400),
            'not_checked': max(0, len(report['remote_script_urls']) - len(urls)),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    if args.check_remote:
        print('远程脚本健康检查：', json.dumps(report['remote_script_health_summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
