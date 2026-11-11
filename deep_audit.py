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
    # Modern conditional Rewrite: the regex body may contain unescaped URL slashes.
    # A closing delimiter is recognized by its syntactic context (flags/alias followed
    # by &&, ||, or then), rather than by stopping at the first slash.
    modern = re.match(
        r'^(request|response)\s+if\s+\$\{url\}\s*~=?\s*/',
        line, re.I
    )
    if modern:
        start = modern.end()
        closing = re.search(
            r'/([A-Za-z]*)\s+(?:(?:as\s+[A-Za-z_]\w*)\s+)?(?=(?:then\b|&&|\|\|))',
            line[start:], re.I
        )
        if closing:
            tail = line[start + closing.end():]
            action = re.search(r'\bthen\s+(.+)$', tail, re.I)
            if action:
                matcher = line[start:start + closing.start()]
                return modern.group(1).lower(), matcher, action.group(1).strip()

    # Legacy form: <matcher> <action> [argument]. Numeric actions such as 302
    # are valid and must not be rejected by an alphabetic-only token pattern.
    legacy = re.match(r'^(\S+)\s+([A-Za-z0-9_-]+)(?:\s+(.*))?$', line)
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
    return re.sub(r'\\+([./])', r'\1', pattern)


def extract_url_authority(pattern):
    """Read URL authority without treating regex character-class slashes as path separators."""
    marker = pattern.find('://')
    remainder = pattern[marker + 3:] if marker >= 0 else pattern
    chars, in_class, escaped = [], False, False
    for char in remainder:
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == '\\':
            chars.append(char)
            escaped = True
            continue
        if char == '[':
            in_class = True
        elif char == ']':
            in_class = False
        elif char == '/' and not in_class:
            break
        chars.append(char)
    return ''.join(chars)


def has_domain_constraint(pattern):
    """Recognize literal domains, constrained regex hostnames and explicit IP hosts."""
    normalized = normalize_regex_literals(pattern)
    authority = extract_url_authority(normalized)

    literal_domain = re.search(
        r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}', authority, re.I
    )
    known_tld = re.search(
        r'\.(?:com|cn|net|org|info|biz|tv|cc|io|app|me|co|xyz|top|site|online|mobi|name|pro|edu|gov|uk|jp|de|ru|ai|so|fun|club|live|store|tech|world|asia)(?=$|[:?#])',
        authority, re.I
    )
    tld_alternation = re.search(
        r'\.\((?:\?:)?(?:com|cn|net|org|info|biz|tv|cc|io|app|me|co|xyz|top|site|online|mobi|name|pro|edu|gov|uk|jp|de|ru|ai|so|fun|club|live|store|tech|world|asia)(?:\|(?:com|cn|net|org|info|biz|tv|cc|io|app|me|co|xyz|top|site|online|mobi|name|pro|edu|gov|uk|jp|de|ru|ai|so|fun|club|live|store|tech|world|asia))+\)',
        authority, re.I
    )
    ipv4_literal = re.search(
        r'(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?=$|[:?#])',
        authority
    )
    return bool(literal_domain or known_tld or tld_alternation or ipv4_literal)


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

    authority = extract_url_authority(normalized)
    scheme_marker = normalized.find('://')
    remainder = normalized[scheme_marker + 3:] if scheme_marker >= 0 else normalized
    if '*' in authority or '+' in authority or re.search(r'\([^)]*\)[*+]', authority):
        return 'domain_scoped_subdomain_wildcard'
    path_part = remainder[len(authority):] if scheme_marker >= 0 else remainder
    if '*' in path_part or '+' in path_part or re.search(r'\([^)]*\)[*+]', path_part):
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



ACTION_FAMILIES = {
    'block': {
        'reject', 'reject-200', 'reject-img', 'reject-dict', 'reject-array',
        'reject-video', 'reject_dict', 'reject_img', 'reject_video'
    },
    'redirect': {'302', '307', 'redirect'},
    'response_mock': {
        'response.body.mock', 'response.body.mock_file', 'mock-response-body'
    },
    'response_body_rewrite': {
        'response.body.replace', 'response-body-replace-regex'
    },
    'response_json_rewrite': {
        'response.json.delete', 'response.json.replace', 'response.json.jq',
        'response.json.jq_file', 'response-body-json-add',
        'response-body-json-replace', 'response-body-json-del',
        'response-body-json-delete', 'response-body-json-jq'
    },
    'request_body_rewrite': {'request-body-replace-regex'},
    'header_rewrite': {
        'header-add', 'header-del', 'header-replace', 'header-replace-regex',
        'response.header.add', 'response.header.del', 'response.header.replace',
        'response-header-add', 'response-header-del', 'response-header-replace',
        'response-header-replace-regex'
    }
}

ACTION_REVIEW = {
    'response_mock': ('high_review', '替换或模拟整个响应，需确认状态码、内容结构和目标 App 兼容性'),
    'response_body_rewrite': ('high_review', '直接改写响应正文，需确认替换范围不会误伤正常内容'),
    'request_body_rewrite': ('high_review', '改写请求正文，可能改变请求参数或业务行为'),
    'response_json_rewrite': ('medium_review', '修改响应 JSON 字段或结构，需确认字段路径和空值/类型处理'),
    'header_rewrite': ('medium_review', '修改请求或响应头，需确认不会影响缓存、鉴权、内容协商或协议行为'),
    'redirect': ('medium_review', '重定向请求，需确认目标地址、参数保留及跳转范围')
}


def classify_rewrite_action(action):
    """Return a conservative semantic family for old and modern Loon action syntax."""
    value = action.strip()
    # Modern rules may chain multiple operations with '|'. Find known action
    # identifiers anywhere in the expression; jq expressions themselves are not
    # classified as Loon actions unless they match one of these exact identifiers.
    known = sorted(
        (name for names in ACTION_FAMILIES.values() for name in names),
        key=len, reverse=True
    )
    found = []
    for name in known:
        if re.search(r'(?<![A-Za-z0-9_.-])' + re.escape(name) +
                     r'(?![A-Za-z0-9_.-])', value, re.I):
            found.append(name)
    if not found:
        # Legacy parser returns the action token only, while modern parser returns
        # the full action expression. Preserve unknown actions for manual review.
        token = re.match(r'^([A-Za-z0-9_.-]+)', value)
        found = [token.group(1).lower()] if token else []
    families = sorted({
        family for family, names in ACTION_FAMILIES.items()
        if any(name.lower() in {x.lower() for x in found} for name in names)
    })
    if not families:
        return {'families': ['unknown'], 'operations': found or ['<unrecognized>']}
    return {'families': families, 'operations': sorted(found)}


def action_review_priority(families):
    priorities = [ACTION_REVIEW[x][0] for x in families if x in ACTION_REVIEW]
    if 'high_review' in priorities:
        return 'high_review'
    if 'medium_review' in priorities:
        return 'medium_review'
    return 'no_special_review'


def action_review_reasons(families):
    return [ACTION_REVIEW[x][1] for x in families if x in ACTION_REVIEW]


def overlap_pattern_is_safe(pattern):
    """Conservative guard: only run Python regexes with bounded, simple structure."""
    if len(pattern) > 240:
        return False, 'pattern_too_long'
    if re.search(r'\\[1-9]|\\k<|\(\?[=!<]', pattern):
        return False, 'backreference_or_lookaround'
    if re.search(r'\([^)]*[+*][^)]*\)[+*{]', pattern):
        return False, 'nested_quantifier'
    if re.search(r'\([^)]*\|[^)]*\)[+*{]', pattern):
        return False, 'quantified_alternation'
    if len(re.findall(r'(?<!\\)[*+{]', pattern)) > 8:
        return False, 'too_many_quantifiers'
    if pattern.count('|') > 8:
        return False, 'too_many_alternatives'
    return True, 'safe_subset'


def build_overlap_sample(pattern):
    """Build one bounded representative URL from a deliberately small regex subset."""
    value = re.sub(r'\\+/', '/', pattern)
    value = value.removeprefix('^').removesuffix('$')
    value = re.sub(r'https\??://', 'https://', value, flags=re.I)
    for _ in range(4):
        updated = re.sub(r'\((?:\?:)?([^()|]+)(?:\|[^()]*)+\)',
                         lambda m: m.group(1), value)
        if updated == value:
            break
        value = updated
    value = re.sub(r'\\[dD]', '1', value)
    value = re.sub(r'\\[wW]', 'a', value)
    value = re.sub(r'\\[sS]', '-', value)
    value = re.sub(r'\[\^?[^]]+\][*+?]?', 'x', value)
    value = re.sub(r'\\[.^$*+?{}[\]|()]', lambda m: m.group(0)[1:], value)
    value = re.sub(r'\.\*|\.\+', 'sample', value)
    value = re.sub(r'\{[0-9]+(?:,[0-9]*)?\}', '', value)
    value = re.sub(r'[*+?]+', '', value)
    value = value.replace('(?:', '(').replace('(?i:', '(')
    value = value.replace('(', '').replace(')', '').replace('|', '')
    value = value.strip()
    if not value.startswith(('http://', 'https://')):
        return None
    if len(value) > 320 or any(ch in value for ch in '\r\n\t '):
        return None
    return value


def audit_rewrite_overlaps(rewrite_rows, sample_cap=600, candidate_cap=500):
    """Sample-driven overlap hints; deliberately not a proof of regex intersection."""
    rules, skipped = [], []
    for line_no, line in rewrite_rows:
        parsed = parse_rewrite(line)
        if not parsed:
            skipped.append({'line': line_no, 'reason': 'unparsed_rule'})
            continue
        phase, matcher, action = parsed
        safe, reason = overlap_pattern_is_safe(matcher)
        if not safe:
            skipped.append({'line': line_no, 'phase': phase, 'pattern': matcher,
                            'reason': reason})
            continue
        try:
            compiled = re.compile(re.sub(r'\\+/', '/', matcher), re.I)
        except re.error:
            skipped.append({'line': line_no, 'phase': phase, 'pattern': matcher,
                            'reason': 'python_regex_compile_error'})
            continue
        sample = build_overlap_sample(matcher)
        if not sample:
            skipped.append({'line': line_no, 'phase': phase, 'pattern': matcher,
                            'reason': 'no_safe_url_sample'})
            continue
        host = sample.split('://', 1)[1].split('/', 1)[0].split(':', 1)[0].lower()
        info = classify_rewrite_action(action)
        rules.append({'line': line_no, 'phase': phase, 'pattern': matcher,
                      'action': action, 'families': info['families'],
                      'compiled': compiled, 'sample': sample, 'host': host})

    host_index = defaultdict(list)
    for index, rule in enumerate(rules):
        labels = rule['host'].split('.')
        for offset in range(len(labels)):
            host_index['.'.join(labels[offset:])].append(index)

    samples = list(dict.fromkeys(rule['sample'] for rule in rules))[:sample_cap]
    groups, seen = [], set()
    for url in samples:
        host = url.split('://', 1)[1].split('/', 1)[0].split(':', 1)[0].lower()
        indices = set()
        labels = host.split('.')
        for offset in range(len(labels)):
            indices.update(host_index.get('.'.join(labels[offset:]), []))
        matched = []
        for index in sorted(indices):
            rule = rules[index]
            try:
                if rule['compiled'].search(url):
                    matched.append(rule)
            except (re.error, RecursionError):
                continue
        if len(matched) < 2:
            continue
        signature = tuple(sorted((x['line'], x['phase'], x['pattern']) for x in matched))
        if signature in seen:
            continue
        seen.add(signature)
        same_phase_pairs = []
        for i, left in enumerate(matched):
            for right in matched[i + 1:]:
                if left['phase'] == right['phase']:
                    same_phase_pairs.append((left, right))
        same_phase_families = {
            family for left, right in same_phase_pairs
            for family in left['families'] + right['families']
        }
        if not same_phase_pairs:
            kind = 'cross_phase_only'
        elif len(same_phase_families) > 1:
            kind = 'cross_action_overlap'
        else:
            kind = 'likely_duplicate_overlap'
        groups.append({
            'sample_url': url, 'overlap_type': kind,
            'phases': sorted({x['phase'] for x in matched}),
            'lines': [x['line'] for x in matched],
            'rules': [{'line': x['line'], 'phase': x['phase'],
                       'pattern': x['pattern'], 'action': x['action'],
                       'action_families': x['families']} for x in matched]
        })
        if len(groups) >= candidate_cap:
            break

    return {
        'rewrite_overlap_sampled_rules': len(rules),
        'rewrite_overlap_sampled_urls': len(samples),
        'rewrite_overlap_candidate_groups': groups,
        'rewrite_overlap_manual_review_candidates': skipped[:candidate_cap],
        'rewrite_overlap_sample_cap': sample_cap,
        'rewrite_overlap_skipped_rules': len(skipped),
    }


def audit_deep(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    sec = parse_sections(text)
    rewrite = rows(sec.get('Rewrite', []))
    script = rows(sec.get('Script', []))
    mitm = rows(sec.get('MITM', []))

    groups, broad, unknown = defaultdict(list), [], []
    scope_counts, scope_candidates = Counter(), []
    action_family_counts, action_review_candidates, unknown_action_candidates = Counter(), [], []
    for n, line in rewrite:
        parsed = parse_rewrite(line)
        if not parsed:
            unknown.append({'line': n, 'entry': line[:220]})
            continue
        phase, matcher, action = parsed
        groups[(phase, matcher)].append({'line': n, 'action': action})
        action_info = classify_rewrite_action(action)
        families = action_info['families']
        for family in families:
            action_family_counts[family] += 1
        priority = action_review_priority(families)
        if priority != 'no_special_review':
            action_review_candidates.append({
                'line': n, 'phase': phase, 'pattern': matcher, 'action': action,
                'action_families': families, 'operations': action_info['operations'],
                'review_priority': priority,
                'reasons': action_review_reasons(families)
            })
        if 'unknown' in families:
            unknown_action_candidates.append({
                'line': n, 'phase': phase, 'pattern': matcher, 'action': action
            })
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
            'rewrite_action_family_counts': dict(sorted(action_family_counts.items())),
            'rewrite_action_semantic_review_candidates': len(action_review_candidates),
            'rewrite_unknown_action_candidates': len(unknown_action_candidates),
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
        'rewrite_action_semantic_review_candidates': action_review_candidates,
        'rewrite_unknown_action_candidates': unknown_action_candidates,
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
        'rewrite_action_semantic_review_candidates':'动作语义复核候选',
        'rewrite_unknown_action_candidates':'未分类动作候选',
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
        ('rewrite_action_semantic_review_candidates','Rewrite 动作语义复核候选'),
        ('rewrite_unknown_action_candidates','未分类 Rewrite 动作候选'),
        ('mitm_without_obvious_literal_guard','未发现明显字面守卫的 MITM 候选'),
        ('script_repeated_remote_urls','重复使用的远程脚本 URL'),
        ('script_generic_trigger_candidates','通用/条件触发器候选')
    ]:
        lines += ['', '## ' + title, '']
        values = report[key]
        lines += ['- ' + json.dumps(x, ensure_ascii=False) for x in values[:100]] if values else ['未发现。']
        if len(values) > 100:
            lines.append('其余 %d 项见 JSON 报告。' % (len(values) - 100))
    lines += ['', '## Rewrite 动作语义分类', '',
              '| 动作类别 | 条目数 |', '|---|---:|']
    for family, count in report['summary']['rewrite_action_family_counts'].items():
        lines.append('| %s | %s |' % (family, count))
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
