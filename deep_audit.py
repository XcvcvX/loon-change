#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only deep audit for Loon Rewrite, MITM and Script risk candidates."""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def parse_sections(text):
    sections, current = defaultdict(list), None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\[([^\]]+)\]\s*$', line.strip())
        if match:
            current = match.group(1).strip()
        elif current is not None:
            sections[current].append((number, line))
    return sections


def rows(items):
    return [(n, line.strip()) for n, line in items
            if line.strip() and not line.lstrip().startswith('#')]


def parse_rewrite(line):
    modern = re.match(
        r'^(request|response)\s+if\s+\$\{url\}\s*~=?\s*/((?:\\.|[^/])*)/\s+then\s+(.+)$',
        line, re.I
    )
    if modern:
        return modern.group(1).lower(), modern.group(2), modern.group(3).strip()
    legacy = re.match(r'^(\S+)\s+([A-Za-z][A-Za-z0-9_-]*)(?:\s+(.*))?$', line)
    actions = {
        'reject','reject-200','reject-img','reject-dict','reject-array','reject-video',
        '302','307','header-add','header-del','header-replace','header-replace-regex',
        'request-body-replace-regex','request-body-json-add','request-body-json-replace',
        'request-body-json-del','request-body-json-jq','mock-request-body',
        'response-header-add','response-header-del','response-header-replace',
        'response-header-replace-regex','response-body-replace-regex',
        'response-body-json-add','response-body-json-replace','response-body-json-del',
        'response-body-json-jq','mock-response-body'
    }
    if legacy and legacy.group(2).lower() in actions:
        return 'legacy', legacy.group(1), legacy.group(2).lower()
    return None


def normalize_regex_literals(pattern):
    """Normalize escaped URL separators for conservative scope inspection only."""
    return re.sub(r'\\([./])', r'\1', pattern)


def has_domain_constraint(pattern):
    normalized = normalize_regex_literals(pattern)
    return bool(re.search(
        r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}', normalized, re.I
    ))


def classify_rewrite_scope(pattern):
    """Classify matcher scope; this is a review hint, never a rule-validity verdict."""
    normalized = normalize_regex_literals(pattern)
    if normalized.strip() in {'.*', '.+', '^.*$', '^.+$'}:
        return 'global_like'
    if not has_domain_constraint(pattern):
        if normalized.startswith(('^https://', '^http://', '^https?://')):
            return 'url_without_domain'
        if '.*' in normalized or '.+' in normalized:
            return 'unscoped_wildcard'
        if len(normalized) <= 5:
            return 'short_unscoped'
        return 'unscoped_other'

    authority = ''
    scheme = re.search(r'https?://', normalized, re.I)
    if scheme:
        authority = re.split(r'[/\?#]', normalized[scheme.end():], maxsplit=1)[0]
    if re.search(r'\.\*|\.\+|\([^)]*\)[*+]', authority):
        return 'domain_scoped_subdomain_wildcard'
    remainder = normalized[scheme.end():] if scheme else normalized
    if re.search(r'\.\*|\.\+|\([^)]*\)[*+]', remainder):
        return 'domain_scoped_path_wildcard'
    return 'domain_scoped'


def broad_reasons(pattern):
    reasons = []
    normalized = normalize_regex_literals(pattern)
    domain = has_domain_constraint(pattern)
    if normalized.strip() in {'.*', '.+', '^.*$', '^.+$'}:
        reasons.append('近似全量匹配')
    if len(normalized) <= 5 and not domain:
        reasons.append('表达式很短且没有明显域名约束')
    if ('.*' in normalized or '.+' in normalized) and not domain:
        reasons.append('含未限定域名的贪婪通配')
    if normalized.startswith(('^https://', '^http://', '^https?://')) and not domain:
        reasons.append('协议级 URL 匹配未见明确域名')
    return reasons


def audit_deep(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    sec = parse_sections(text)
    rewrite = rows(sec.get('Rewrite', []))
    script = rows(sec.get('Script', []))
    mitm = rows(sec.get('MITM', []))

    groups, broad, unknown = defaultdict(list), [], []
    scope_counts, scope_candidates = Counter(), []
    for n, line in rewrite:
        parsed = parse_rewrite(line)
        if not parsed:
            unknown.append({'line': n, 'entry': line[:220]})
            continue
        phase, matcher, action = parsed
        groups[(phase, matcher)].append({'line': n, 'action': action})
        scope = classify_rewrite_scope(matcher)
        scope_counts[scope] += 1
        if scope != 'domain_scoped':
            scope_candidates.append({'line': n, 'phase': phase, 'pattern': matcher,
                                     'action': action, 'scope': scope})
        reasons = broad_reasons(matcher)
        if reasons:
            broad.append({'line': n, 'phase': phase, 'pattern': matcher,
                          'action': action, 'reasons': reasons, 'scope': scope})
    duplicates, conflicts = [], []
    for (phase, matcher), entries in sorted(groups.items()):
        actions = sorted({x['action'] for x in entries})
        if len(entries) > 1:
            duplicates.append({'phase': phase, 'pattern': matcher, 'actions': actions,
                               'lines': [x['line'] for x in entries]})
        if len(actions) > 1:
            conflicts.append({'phase': phase, 'pattern': matcher, 'actions': actions,
                              'lines': [x['line'] for x in entries]})

    positive, negative = set(), []
    for n, line in mitm:
        if re.match(r'^hostname\s*=', line, re.I):
            for value in line.split('=', 1)[1].split(','):
                host = value.strip().lower().rstrip('.')
                if host.startswith('-'):
                    negative.append({'host': host[1:], 'line': n})
                elif host:
                    positive.add(host)
    wild = sorted(x for x in positive if x.startswith('*.'))
    exact = sorted(x for x in positive if not x.startswith('*.'))
    overlaps = sorted(h for h in exact if any(h.endswith('.' + w[2:]) for w in wild))
    apex_missing = sorted(w[2:] for w in wild if w[2:] not in exact)

    guard_text = '\n'.join(x for _, x in rewrite + script).replace(r'\.', '.')
    literal_hosts = set(re.findall(
        r'(?<![A-Za-z0-9_-])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?![A-Za-z0-9_-])',
        guard_text, re.I
    ))
    unreferenced = sorted(h for h in positive if not any(
        ref == (h[2:] if h.startswith('*.') else h)
        or ref.endswith('.' + (h[2:] if h.startswith('*.') else h))
        or (h[2:] if h.startswith('*.') else h).endswith('.' + ref)
        for ref in literal_hosts
    ))

    url_counts, trigger_types = Counter(), Counter()
    no_url, generic = [], []
    for n, line in script:
        m = re.search(r'script-path\s*=\s*(https?://[^,\s]+)', line, re.I)
        if not m:
            m = re.search(r'''script\(\s*(["'])(https?://.*?)\1''', line, re.I)
        if m:
            url = m.group(1) if m.lastindex == 1 else m.group(2)
            url_counts[url.rstrip(',')] += 1
        else:
            no_url.append({'line': n, 'entry': line[:200]})
        t = re.match(r'^(http-request|http-response|cron|generic|request\s+if|response\s+if)\b', line, re.I)
        kind = re.sub(r'\s+', ' ', t.group(1).lower()) if t else 'unclassified'
        trigger_types[kind] += 1
        if kind in {'generic', 'request if', 'response if'}:
            generic.append({'line': n, 'type': kind, 'entry': line[:200]})
    repeated = [{'url': u, 'count': c} for u, c in sorted(url_counts.items()) if c > 1]

    report = {
        'plugin': str(path),
        'summary': {
            'rewrite_entries': len(rewrite),
            'rewrite_unparsed': len(unknown),
            'rewrite_broad_candidates': len(broad),
            'rewrite_scope_counts': dict(sorted(scope_counts.items())),
            'rewrite_scope_review_candidates': len(scope_candidates),
            'rewrite_duplicate_matcher_groups': len(duplicates),
            'rewrite_action_conflict_groups': len(conflicts),
            'mitm_positive_unique_hosts': len(positive),
            'mitm_wildcards': len(wild),
            'mitm_exact_hosts_covered_by_wildcards': len(overlaps),
            'mitm_wildcard_apex_not_explicit': len(apex_missing),
            'mitm_without_obvious_literal_guard': len(unreferenced),
            'script_entries': len(script),
            'script_unique_remote_urls': len(url_counts),
            'script_urls_reused': len(repeated),
            'script_entries_without_detected_url': len(no_url),
            'script_generic_trigger_candidates': len(generic)
        },
        'rewrite_broad_candidates': broad,
        'rewrite_scope_review_candidates': scope_candidates,
        'rewrite_duplicate_matcher_groups': duplicates,
        'rewrite_action_conflict_groups': conflicts,
        'rewrite_unparsed_entries': unknown,
        'mitm_wildcard_overlap_candidates': overlaps,
        'mitm_wildcard_apex_not_explicit': apex_missing,
        'mitm_without_obvious_literal_guard': unreferenced,
        'mitm_negative_exclusions': negative,
        'script_trigger_types': dict(sorted(trigger_types.items())),
        'script_repeated_remote_urls': repeated,
        'script_entries_without_detected_url': no_url,
        'script_generic_trigger_candidates': generic,
        'safety_notes': [
            '本报告只读，不会删除、改写或禁用任何规则。',
            '宽泛正则、同匹配器多动作和未发现字面守卫均为人工复核候选，不等于错误。',
            'MITM 可能由复杂正则、变量或间接脚本引用；未发现字面域名不代表无用。',
            '重复脚本 URL 不等于重复执行有害；需结合触发频率和 Loon 日志。',
            '静态审计无法测量真实耗电、温度或延迟，也不能替代 iPhone 真机回归。',
            '远程脚本 HEAD 失败可能是 CDN 不支持或限流，不应据此直接删除脚本。'
        ]
    }
    return report


def render_markdown(report):
    labels = {
        'rewrite_entries':'Rewrite 条目','rewrite_unparsed':'未解析 Rewrite',
        'rewrite_broad_candidates':'宽泛匹配候选',
        'rewrite_duplicate_matcher_groups':'重复匹配器组',
        'rewrite_action_conflict_groups':'同匹配器多动作组',
        'mitm_positive_unique_hosts':'MITM 正向唯一主机',
        'mitm_wildcards':'MITM 通配主机',
        'mitm_exact_hosts_covered_by_wildcards':'被通配覆盖的精确主机候选',
        'mitm_wildcard_apex_not_explicit':'未显式包含 apex 的通配域',
        'mitm_without_obvious_literal_guard':'未发现明显字面守卫的 MITM 候选',
        'script_entries':'Script 条目','script_unique_remote_urls':'唯一远程脚本 URL',
        'script_urls_reused':'被多个触发器复用的脚本 URL',
        'script_entries_without_detected_url':'未识别远程 URL 的 Script 条目',
        'script_generic_trigger_candidates':'通用/条件触发器候选'
    }
    lines = ['# Loon 插件深度只读审计报告', '',
             '本报告只提供人工复核线索，不会自动修改任何规则。', '',
             '| 检查项 | 数量 |', '|---|---:|']
    for key, label in labels.items():
        lines.append('| %s | %s |' % (label, report['summary'][key]))
    for key, title in [
        ('rewrite_broad_candidates','宽泛 Rewrite 候选'),
        ('rewrite_action_conflict_groups','同匹配器多动作候选'),
        ('mitm_without_obvious_literal_guard','未发现明显字面守卫的 MITM 候选'),
        ('script_repeated_remote_urls','重复使用的远程脚本 URL'),
        ('script_generic_trigger_candidates','通用/条件触发器候选')
    ]:
        lines += ['', '## ' + title, '']
        values = report[key]
        lines += ['- ' + json.dumps(x, ensure_ascii=False) for x in values[:100]] if values else ['未发现。']
        if len(values) > 100:
            lines.append('其余 %d 项见 JSON 报告。' % (len(values) - 100))
    lines += ['', '## Rewrite 匹配范围分类', '',
              '| 分类 | 数量 |', '|---|---:|']
    for scope, count in report['summary']['rewrite_scope_counts'].items():
        lines.append('| %s | %s |' % (scope, count))
    lines += ['', '## Rewrite 范围复核候选（前 100 项）', '']
    candidates = report['rewrite_scope_review_candidates']
    lines += ['- ' + json.dumps(x, ensure_ascii=False) for x in candidates[:100]] if candidates else ['未发现范围复核候选。']
    if len(candidates) > 100:
        lines.append('其余 %d 项见 JSON 报告。' % (len(candidates) - 100))
    lines += ['', '## 安全边界', ''] + ['- ' + x for x in report['safety_notes']]
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description='Read-only deep Loon plugin audit')
    p.add_argument('plugin')
    p.add_argument('--json', dest='json_path')
    p.add_argument('--markdown')
    p.add_argument('--summary-only', action='store_true')
    a = p.parse_args()
    report = audit_deep(a.plugin)
    if a.json_path:
        Path(a.json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if a.markdown:
        Path(a.markdown).write_text(render_markdown(report), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2) if a.summary_only
          else render_markdown(report))


if __name__ == '__main__':
    main()
