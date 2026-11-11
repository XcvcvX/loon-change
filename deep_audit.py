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
        action = legacy.group(2).lower()
        if legacy.group(3):
            action += ' ' + legacy.group(3).strip()
        return 'legacy', legacy.group(1), action
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


def infer_rewrite_phase(phase, action):
    """Infer legacy request/response phase only when the action semantics are explicit."""
    if phase in {'request', 'response'}:
        return phase
    info = classify_rewrite_action(action)
    families = set(info['families'])
    if families & {'response_mock', 'response_body_rewrite', 'response_json_rewrite'}:
        return 'response'
    if families & {'block', 'redirect', 'request_body_rewrite'}:
        return 'request'
    token = action.strip().lower()
    if token.startswith(('response-header-', 'response.header.')):
        return 'response'
    # Generic header edits and unknown legacy actions do not identify a phase safely.
    return 'legacy'


def audit_rewrite_overlaps(rewrite_rows, sample_cap=600, candidate_cap=500):
    """Sample-driven overlap hints; deliberately not a proof of regex intersection."""
    rules, skipped = [], []
    for line_no, line in rewrite_rows:
        parsed = parse_rewrite(line)
        if not parsed:
            skipped.append({'line': line_no, 'reason': 'unparsed_rule'})
            continue
        phase, matcher, action = parsed
        phase = infer_rewrite_phase(phase, action)
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
        if not same_phase_pairs and 'legacy' in {x['phase'] for x in matched}:
            kind = 'phase_ambiguous_overlap'
        elif not same_phase_pairs:
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


def extract_literal_matcher_host(matcher):
    """Return a literal hostname or a conservative stable suffix from a URL matcher."""
    # Normalize escaped scheme/path slashes, but preserve escaped dots so a regex
    # wildcard dot can never be mistaken for a literal hostname label separator.
    scheme_normalized = re.sub(r'\\+/', '/', matcher)
    if '://' not in scheme_normalized:
        return None, 'no_explicit_scheme'

    authority = extract_url_authority(scheme_normalized).lstrip('^')
    authority = authority.split('@')[-1].lower().rstrip('.')

    # Literal numeric ports and regex-based optional/variable ports do not
    # make the hostname itself dynamic.
    literal_port = re.search(r':\d{1,5}$', authority)
    if literal_port:
        authority = authority[:literal_port.start()]
    else:
        port_suffixes = sorted((
            r'(?::\d+)?', r'(:\d+)?', r'(?::443)?', r'(:443)?',
            r'(?::\d{2,5})?', r'(:\d{2,5})?',
            r'\:\w+', r':\w+', r'\:\d+', r':\d+'
        ), key=len, reverse=True)
        for suffix in port_suffixes:
            if authority.endswith(suffix):
                authority = authority[:-len(suffix)]
                break
    authority = authority.rstrip('.')
    if not authority:
        return None, 'empty_authority'

    normalized_authority = normalize_regex_literals(authority)
    has_regex_meta = bool(re.search(r'[\[\]()*+?{}|\\]', normalized_authority))
    if not has_regex_meta:
        if re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', normalized_authority):
            return normalized_authority, 'literal_host'
        return None, 'non_literal_or_invalid_host'

    # Use a sentinel for escaped dots. Only these are safe label boundaries;
    # unescaped regex dots remain wildcards and cannot establish MITM coverage.
    separator = '\x01'
    safe_authority = re.sub(r'\\+([.])', separator, authority)

    # Remove only leading regex groups that explicitly contribute a complete
    # optional/repeated subdomain label, e.g. (?:www\.)? or (?:label\.)*.
    while True:
        prefix = re.match(
            r'^\((?:\?:)?[^()]*' + re.escape(separator) + r'\)[*+?]?',
            safe_authority
        )
        if not prefix:
            break
        safe_authority = safe_authority[prefix.end():]

    suffix_pattern = (
        r'(?:^|' + re.escape(separator) + r')'
        r'((?:[a-z0-9-]+' + re.escape(separator) + r')+[a-z]{2,})$'
    )
    candidates = list(re.finditer(suffix_pattern, safe_authority, re.I))
    if candidates:
        suffix = candidates[-1].group(1).replace(separator, '.').lower().rstrip('.')
        public_suffixes = {
            'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'ac.cn', 'mil.cn',
            'com.hk', 'com.tw', 'com.au', 'com.sg', 'com.my', 'com.vn', 'com.ph',
            'com.br', 'com.mx', 'com.tr', 'co.jp', 'or.jp', 'ne.jp', 'ac.jp',
            'co.uk', 'org.uk', 'ac.uk', 'co.kr', 'or.kr', 'co.in', 'co.nz',
            'co.th', 'co.id'
        }
        if len(suffix.split('.')) >= 2 and suffix not in public_suffixes:
            return suffix, 'regex_host_suffix'

    return None, 'regex_host_authority'

def host_matches_mitm(host, positive_hosts, negative_hosts, dynamic_suffix=False):
    """Return coverage state using exact entries and *.suffix entries."""
    host = host.lower().rstrip('.')
    def matches(entry):
        entry = entry.lower().rstrip('.')
        if entry.startswith('*.'):
            suffix = entry[2:]
            return (host == suffix or host.endswith('.' + suffix)) if dynamic_suffix else host.endswith('.' + suffix)
        return False if dynamic_suffix else host == entry
    excluded = sorted(x for x in negative_hosts if matches(x))
    covered_by = sorted(x for x in positive_hosts if matches(x))
    if excluded:
        return 'negative_excluded', covered_by, excluded
    if covered_by:
        return ('covered_by_parent_wildcard' if dynamic_suffix else 'covered'), covered_by, []
    return 'not_listed', [], []


def matcher_scheme_kind(matcher):
    normalized = normalize_regex_literals(matcher).lower()
    prefix = normalized.split('://', 1)[0]
    if 'https?' in prefix:
        return 'http_or_https'
    if 'https' in prefix:
        return 'https_only'
    if 'http' in prefix:
        return 'http_only'
    return 'unknown'


def is_ipv4_literal(host):
    return bool(re.fullmatch(r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}', host))


def audit_mitm_script_coverage(rewrite_rows, script_rows, mitm_rows):
    """Correlate literal Rewrite/Script trigger hosts with MITM entries; read-only."""
    positive, negative = set(), set()
    for number, line in mitm_rows:
        match = re.match(r'^hostname\s*=\s*(.*)$', line, re.I)
        if not match:
            continue
        for raw in match.group(1).split(','):
            host = raw.strip().lower().rstrip('.')
            if not host:
                continue
            if host.startswith('-'):
                negative.add(host[1:])
            else:
                positive.add(host)

    references, ambiguous = [], []
    for source, entries in (('rewrite', rewrite_rows), ('script_trigger', script_rows)):
        for number, line in entries:
            if source == 'rewrite':
                parsed = parse_rewrite(line)
                if not parsed:
                    ambiguous.append({'source': source, 'line': number,
                                      'reason': 'unparsed_rewrite_matcher'})
                    continue
                phase, matcher, action = parsed
            else:
                parts = line.split(None, 1)
                if len(parts) < 2 or parts[0].lower() not in {
                    'http-request', 'http-response', 'request', 'response'
                }:
                    ambiguous.append({'source': source, 'line': number,
                                      'reason': 'generic_or_unrecognized_script_trigger'})
                    continue
                phase = parts[0].lower()
                matcher = parts[1].split('script-path=', 1)[0].strip()
                matcher = re.sub(r'\s+(?:tag|requires-body|timeout|argument)\s*=.*$', '', matcher, flags=re.I)
            host, reason = extract_literal_matcher_host(matcher)
            if not host:
                ambiguous.append({'source': source, 'line': number,
                                  'matcher': matcher[:200], 'reason': reason})
                continue
            dynamic_suffix = reason == 'regex_host_suffix'
            scheme = matcher_scheme_kind(matcher)
            if scheme == 'http_only':
                state, covered_by, excluded_by = 'http_only_no_mitm_required', [], []
            elif is_ipv4_literal(host):
                state, covered_by, excluded_by = 'ip_literal_not_for_mitm', [], []
            else:
                state, covered_by, excluded_by = host_matches_mitm(host, positive, negative, dynamic_suffix)
                if dynamic_suffix and state == 'not_listed':
                    state = 'dynamic_unresolved'
            reference = {
                'source': source, 'line': number, 'phase': phase,
                'matcher': matcher[:240], 'host': host, 'scheme': scheme,
                'host_kind': 'regex_suffix_candidate' if dynamic_suffix else ('ipv4_literal' if is_ipv4_literal(host) else 'literal'),
                'action': action if source == 'rewrite' else None, 'coverage': state,
                'mitm_entries': covered_by, 'negative_exclusions': excluded_by
            }
            references.append(reference)
            if state == 'dynamic_unresolved':
                ambiguous.append({**reference, 'reason': 'regex_host_suffix_without_matching_wildcard'})

    missing = [x for x in references if x['coverage'] == 'not_listed']
    excluded = [x for x in references if x['coverage'] == 'negative_excluded']
    covered = [x for x in references if x['coverage'] in {'covered', 'covered_by_parent_wildcard'}]
    http_only = [x for x in references if x['coverage'] == 'http_only_no_mitm_required']
    ip_literals = [x for x in references if x['coverage'] == 'ip_literal_not_for_mitm']
    referenced_hosts = {x['host'] for x in references}
    unreferenced = []
    for entry in sorted(positive):
        suffix = entry[2:] if entry.startswith('*.') else entry
        if not any(h == suffix or h.endswith('.' + suffix) or suffix.endswith('.' + h)
                   for h in referenced_hosts):
            unreferenced.append(entry)

    return {
        'mitm_script_coverage_summary': {
            'positive_entries': len(positive),
            'negative_entries': len(negative),
            'literal_references': len(references),
            'covered_references': len(covered),
            'http_only_references': len(http_only),
            'ip_literal_references': len(ip_literals),
            'dynamic_suffix_references': sum(x['host_kind'] == 'regex_suffix_candidate' for x in references),
            'missing_rewrite_references': sum(x['source'] == 'rewrite' for x in missing),
            'missing_script_trigger_references': sum(x['source'] == 'script_trigger' for x in missing),
            'missing_mitm_references': len(missing),
            'negative_excluded_references': len(excluded),
            'ambiguous_references': len(ambiguous),
            'ambiguous_rewrite_references': sum(x['source'] == 'rewrite' for x in ambiguous),
            'ambiguous_script_trigger_references': sum(x['source'] == 'script_trigger' for x in ambiguous),
            'unreferenced_positive_entries': len(unreferenced)
        },
        'mitm_missing_rewrite_script_coverage': missing,
        'mitm_negative_excluded_rewrite_script_coverage': excluded,
        'mitm_http_only_no_mitm_references': http_only,
        'mitm_ip_literal_not_for_mitm_references': ip_literals,
        'mitm_ambiguous_rewrite_script_references': ambiguous,
        'mitm_unreferenced_positive_candidates': unreferenced,
        'mitm_literal_rewrite_script_host_references': references
    }





def audit_mitm_necessity(mitm_rows, coverage_report, rewrite_rows, script_rows):
    """Classify MITM entries by evidence strength; never infer deletion safety."""
    entries = {}
    for number, line in mitm_rows:
        match = re.match(r'^hostname\s*=\s*(.*)', line, re.I)
        if not match:
            continue
        for raw in match.group(1).split(','):
            host = raw.strip().lower().rstrip('.')
            if not host:
                continue
            negative = host.startswith('-')
            key = host[1:] if negative else host
            item = entries.setdefault((negative, key), {'host': key, 'negative': negative,
                                                         'lines': [], 'references': []})
            item['lines'].append(number)

    references = coverage_report['mitm_literal_rewrite_script_host_references']
    ambiguous = coverage_report['mitm_ambiguous_rewrite_script_references']
    source_rows = rewrite_rows + script_rows
    source_text = re.sub(r'\\+([.])', r'\1', chr(10).join(line for _, line in source_rows))
    generic_script = [
        {'line': number, 'entry': line[:200]}
        for number, line in script_rows
        if re.match(r'^(?:generic|cron)\b', line, re.I)
    ]

    classified = []
    for (negative, host), item in sorted(entries.items()):
        if negative:
            item['classification'] = 'negative_exclusion'
            item['evidence'] = '显式负向 hostname；需结合业务意图核对'
            classified.append(item)
            continue

        matched = [ref for ref in references if host in ref.get('mitm_entries', [])]
        item['references'] = [
            {'source': ref['source'], 'line': ref['line'], 'host': ref['host'],
             'coverage': ref['coverage']} for ref in matched
        ]
        if matched:
            item['classification'] = 'referenced_by_literal_trigger'
            item['evidence'] = '至少一个 Rewrite/Script 业务触发器明确由该 MITM 项覆盖'
        else:
            token = re.compile(r'(?<![A-Za-z0-9_-])' + re.escape(host) +
                               r'(?![A-Za-z0-9_-])', re.I)
            mentioned = bool(token.search(source_text))
            related_ambiguous = []
            for ref in ambiguous:
                context = re.sub(r'\\+([.])', r'\1',
                                 (ref.get('matcher', '') + ' ' + ref.get('entry', '')).lower())
                if host in context or (host.startswith('*.') and host[2:] in context):
                    related_ambiguous.append(ref)
            if mentioned:
                item['classification'] = 'possible_indirect_or_embedded_reference'
                item['evidence'] = '在规则文本中出现，但未能证明是业务触发器主机（可能是脚本/CDN/响应地址）'
            elif related_ambiguous or (host.startswith('*.') and generic_script):
                item['classification'] = 'insufficient_dynamic_or_generic_evidence'
                item['evidence'] = '通配域或相关动态/通用触发器可能存在静态分析无法解析的引用'
            else:
                item['classification'] = 'no_literal_reference_candidate'
                item['evidence'] = '当前可识别的 Rewrite/Script 文本中未发现字面触发器引用；不构成可删除结论'
        classified.append(item)

    missing_classified = []
    for ref in coverage_report['mitm_missing_rewrite_script_coverage']:
        row = dict(ref)
        if ref['scheme'] == 'https_only':
            row['classification'] = 'https_literal_missing'
            row['evidence'] = 'HTTPS 字面触发器未被正向 MITM 覆盖；仍需确认 Loon 语法、证书与实际请求'
        else:
            row['classification'] = 'scheme_or_matcher_ambiguous_missing'
            row['evidence'] = '协议或 matcher 范围不够明确，不能直接判定必须补入 MITM'
        missing_classified.append(row)

    counts = Counter(x['classification'] for x in classified)
    return {
        'mitm_necessity_summary': {
            'positive_entries': sum(not x['negative'] for x in classified),
            'negative_entries': sum(x['negative'] for x in classified),
            'referenced_by_literal_trigger': counts['referenced_by_literal_trigger'],
            'possible_indirect_or_embedded_reference': counts['possible_indirect_or_embedded_reference'],
            'insufficient_dynamic_or_generic_evidence': counts['insufficient_dynamic_or_generic_evidence'],
            'no_literal_reference_candidates': counts['no_literal_reference_candidate'],
            'https_literal_missing': sum(x['classification'] == 'https_literal_missing' for x in missing_classified),
            'scheme_or_matcher_ambiguous_missing': sum(x['classification'] == 'scheme_or_matcher_ambiguous_missing' for x in missing_classified),
            'generic_script_triggers': len(generic_script)
        },
        'mitm_necessity_classifications': classified,
        'mitm_missing_necessity_classifications': missing_classified,
        'mitm_generic_script_trigger_context': generic_script,
        'mitm_necessity_safety_note': '未发现字面引用不等于 MITM 冗余；本分类不建议自动删除、添加或调整任何 hostname。'
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
    overlap_report = audit_rewrite_overlaps(rewrite)

    duplicates, conflicts, exact_action_duplicates, cross_family_conflicts = [], [], [], []
    for (phase, matcher), entries in sorted(groups.items()):
        action_counts = Counter(x['action'] for x in entries)
        actions = sorted(action_counts)
        families = sorted({
            family
            for entry in entries
            for family in classify_rewrite_action(entry['action'])['families']
        })
        detail = [
            {
                'line': entry['line'],
                'action': entry['action'],
                'action_families': classify_rewrite_action(entry['action'])['families'],
                'operations': classify_rewrite_action(entry['action'])['operations']
            }
            for entry in entries
        ]
        if len(entries) > 1:
            duplicates.append({
                'phase': phase, 'pattern': matcher, 'actions': actions,
                'lines': [x['line'] for x in entries], 'entries': detail,
                'exact_duplicate_actions': sorted(
                    action for action, count in action_counts.items() if count > 1
                ),
                'action_families': families
            })
        if any(count > 1 for count in action_counts.values()):
            exact_action_duplicates.append({
                'phase': phase, 'pattern': matcher,
                'actions': sorted(action for action, count in action_counts.items() if count > 1),
                'lines': [x['line'] for x in entries]
            })
        if len(actions) > 1:
            conflicts.append({
                'phase': phase, 'pattern': matcher, 'actions': actions,
                'lines': [x['line'] for x in entries], 'entries': detail,
                'action_families': families
            })
            if len(families) > 1:
                cross_family_conflicts.append({
                    'phase': phase, 'pattern': matcher, 'actions': actions,
                    'lines': [x['line'] for x in entries], 'action_families': families
                })

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
    coverage_report = audit_mitm_script_coverage(rewrite, script, mitm)
    necessity_report = audit_mitm_necessity(mitm, coverage_report, rewrite, script)

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
            'rewrite_exact_duplicate_action_groups': len(exact_action_duplicates),
            'rewrite_cross_family_conflict_groups': len(cross_family_conflicts),
            'rewrite_action_family_counts': dict(sorted(action_family_counts.items())),
            'rewrite_action_semantic_review_candidates': len(action_review_candidates),
            'rewrite_unknown_action_candidates': len(unknown_action_candidates),
            'rewrite_overlap_sampled_rules': overlap_report['rewrite_overlap_sampled_rules'],
            'rewrite_overlap_sampled_urls': overlap_report['rewrite_overlap_sampled_urls'],
            'rewrite_overlap_candidate_groups': len(overlap_report['rewrite_overlap_candidate_groups']),
            'rewrite_overlap_manual_review_candidates': len(overlap_report['rewrite_overlap_manual_review_candidates']),
            'rewrite_overlap_skipped_rules': overlap_report['rewrite_overlap_skipped_rules'],
            'mitm_positive_unique_hosts': len(positive),
            'mitm_wildcards': len(wild),
            'mitm_exact_hosts_covered_by_wildcards': len(overlaps),
            'mitm_wildcard_apex_not_explicit': len(apex_missing),
            'mitm_without_obvious_literal_guard': len(unreferenced),
            'script_entries': len(script),
            'script_unique_remote_urls': len(url_counts),
            'script_urls_reused': len(repeated),
            'script_entries_without_detected_url': len(no_url),
            'script_generic_trigger_candidates': len(generic),
            **coverage_report['mitm_script_coverage_summary'],
            **necessity_report['mitm_necessity_summary']
        },
        'rewrite_broad_candidates': broad,
        'rewrite_scope_review_candidates': scope_candidates,
        'rewrite_duplicate_matcher_groups': duplicates,
        'rewrite_action_conflict_groups': conflicts,
        'rewrite_exact_duplicate_action_groups': exact_action_duplicates,
        'rewrite_cross_family_conflict_groups': cross_family_conflicts,
        'rewrite_action_semantic_review_candidates': action_review_candidates,
        'rewrite_unknown_action_candidates': unknown_action_candidates,
        'rewrite_overlap_candidate_groups': overlap_report['rewrite_overlap_candidate_groups'],
        'rewrite_overlap_manual_review_candidates': overlap_report['rewrite_overlap_manual_review_candidates'],
        'rewrite_overlap_sample_cap': overlap_report['rewrite_overlap_sample_cap'],
        'rewrite_overlap_sampled_rules': overlap_report['rewrite_overlap_sampled_rules'],
        'rewrite_overlap_sampled_urls': overlap_report['rewrite_overlap_sampled_urls'],
        'rewrite_overlap_skipped_rules': overlap_report['rewrite_overlap_skipped_rules'],
        'rewrite_unparsed_entries': unknown,
        'mitm_wildcard_overlap_candidates': overlaps,
        'mitm_wildcard_apex_not_explicit': apex_missing,
        'mitm_without_obvious_literal_guard': unreferenced,
        'mitm_negative_exclusions': negative,
        'script_trigger_types': dict(sorted(trigger_types.items())),
        'script_repeated_remote_urls': repeated,
        'script_entries_without_detected_url': no_url,
        'script_generic_trigger_candidates': generic,
        'mitm_missing_rewrite_script_coverage': coverage_report['mitm_missing_rewrite_script_coverage'],
        'mitm_negative_excluded_rewrite_script_coverage': coverage_report['mitm_negative_excluded_rewrite_script_coverage'],
        'mitm_http_only_no_mitm_references': coverage_report['mitm_http_only_no_mitm_references'],
        'mitm_ip_literal_not_for_mitm_references': coverage_report['mitm_ip_literal_not_for_mitm_references'],
        'mitm_ambiguous_rewrite_script_references': coverage_report['mitm_ambiguous_rewrite_script_references'],
        'mitm_unreferenced_positive_candidates': coverage_report['mitm_unreferenced_positive_candidates'],
        'mitm_literal_rewrite_script_host_references': coverage_report['mitm_literal_rewrite_script_host_references'],
        'mitm_necessity_classifications': necessity_report['mitm_necessity_classifications'],
        'mitm_missing_necessity_classifications': necessity_report['mitm_missing_necessity_classifications'],
        'mitm_generic_script_trigger_context': necessity_report['mitm_generic_script_trigger_context'],
        'mitm_necessity_safety_note': necessity_report['mitm_necessity_safety_note'],
        'safety_notes': [
            '本报告只读，不会删除、改写或禁用任何规则。',
            '宽泛正则、同匹配器多动作和未发现字面守卫均为人工复核候选，不等于错误。',
            'MITM 可能由复杂正则、变量或间接脚本引用；未发现字面域名不代表无用。',
            'MITM 必要性分级只区分证据强弱；未发现字面引用不等于冗余，绝不自动删除或补入 hostname。',
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
        'rewrite_action_conflict_groups':'同匹配器多操作组',
        'rewrite_exact_duplicate_action_groups':'同匹配器完全重复动作组',
        'rewrite_cross_family_conflict_groups':'同匹配器跨动作类别冲突组',
        'rewrite_action_semantic_review_candidates':'动作语义复核候选',
        'rewrite_unknown_action_candidates':'未分类动作候选',
        'rewrite_overlap_candidate_groups':'交叉命中候选组',
        'rewrite_overlap_manual_review_candidates':'跳过/人工复核候选',
        'mitm_positive_unique_hosts':'MITM 正向唯一主机',
        'mitm_wildcards':'MITM 通配主机',
        'mitm_exact_hosts_covered_by_wildcards':'被通配覆盖的精确主机候选',
        'mitm_wildcard_apex_not_explicit':'未显式包含 apex 的通配域',
        'mitm_without_obvious_literal_guard':'未发现明显字面守卫的 MITM 候选',
        'script_entries':'Script 条目','script_unique_remote_urls':'唯一远程脚本 URL',
        'script_urls_reused':'被多个触发器复用的脚本 URL',
        'script_entries_without_detected_url':'未识别远程 URL 的 Script 条目',
        'script_generic_trigger_candidates':'通用/条件触发器候选',
        'literal_references':'MITM 关联字面主机引用',
        'covered_references':'MITM 已覆盖引用',
        'http_only_references':'纯 HTTP 无需 MITM 的引用',
        'ip_literal_references':'裸 IPv4 不建议加入 MITM 的引用',
        'dynamic_suffix_references':'动态主机后缀候选',
        'missing_rewrite_references':'Rewrite 未覆盖引用',
        'missing_script_trigger_references':'Script 触发器未覆盖引用',
        'missing_mitm_references':'MITM 未覆盖引用候选',
        'negative_excluded_references':'被负向 MITM 排除的引用',
        'ambiguous_references':'无法静态识别的主机引用',
        'ambiguous_rewrite_references':'无法识别主机的 Rewrite',
        'ambiguous_script_trigger_references':'无法识别主机的 Script 触发器',
        'unreferenced_positive_entries':'未关联到字面触发器的 MITM 正向项候选'
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
        ('rewrite_overlap_candidate_groups','Rewrite 样本交叉命中候选'),
        ('rewrite_overlap_manual_review_candidates','Rewrite 交叉审计跳过/人工复核候选'),
        ('mitm_without_obvious_literal_guard','未发现明显字面守卫的 MITM 候选'),
        ('script_repeated_remote_urls','重复使用的远程脚本 URL'),
        ('script_generic_trigger_candidates','通用/条件触发器候选'),
        ('mitm_missing_rewrite_script_coverage','MITM 未覆盖的 Rewrite/Script 触发器'),
        ('mitm_negative_excluded_rewrite_script_coverage','被负向 MITM 排除的 Rewrite/Script 触发器'),
        ('mitm_http_only_no_mitm_references','纯 HTTP 引用（无需 MITM）'),
        ('mitm_ip_literal_not_for_mitm_references','裸 IPv4 引用（不建议加入 MITM）'),
        ('mitm_ambiguous_rewrite_script_references','无法静态识别主机的 Rewrite/Script 引用'),
        ('mitm_unreferenced_positive_candidates','未关联到字面触发器的 MITM 正向项候选')
    ]:
        lines += ['', '## ' + title, '']
        values = report[key]
        lines += ['- ' + json.dumps(x, ensure_ascii=False) for x in values[:100]] if values else ['未发现。']
        if len(values) > 100:
            lines.append('其余 %d 项见 JSON 报告。' % (len(values) - 100))
    lines += ['', '## Rewrite 交叉命中审计说明', '',
              '本节基于有限代表性 URL 样本；不是正则交集的数学证明。仅对受限安全子集执行匹配，复杂表达式跳过并列入人工复核。请求与响应阶段分开标记；同 URL 命中不代表 Loon 执行顺序或真实冲突。', '',
              '| 指标 | 数量 |', '|---|---:|',
              '| 可采样规则 | %s |' % report['rewrite_overlap_sampled_rules'],
              '| 唯一样本 URL | %s |' % report['rewrite_overlap_sampled_urls'],
              '| 命中候选组 | %s |' % report['summary']['rewrite_overlap_candidate_groups'],
              '| 跳过/人工复核规则 | %s |' % report['rewrite_overlap_skipped_rules']]
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
