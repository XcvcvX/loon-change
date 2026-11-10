#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loon 插件静态质量门禁。只检查和报告，不自动删改规则。"""
import argparse
import concurrent.futures
import ipaddress
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

HOST_RE = re.compile(r'^(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z')
IP_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
PUBLIC_SUFFIX_2L = {'com.cn','net.cn','org.cn','gov.cn','edu.cn','ac.cn','mil.cn','com.hk','com.tw','com.au','com.sg','com.my','com.vn','com.ph','com.br','com.mx','com.tr','co.jp','or.jp','ne.jp','ac.jp','co.uk','org.uk','ac.uk','co.kr','or.kr','co.in','co.nz','co.th','co.id'}
LEGACY_ACTIONS = {'reject','reject-200','reject-img','reject-dict','reject-array','reject-video','302','307','header-add','header-del','header-replace','header-replace-regex','request-body-replace-regex','request-body-json-add','request-body-json-replace','request-body-json-del','request-body-json-jq','mock-request-body','response-header-add','response-header-del','response-header-replace','response-header-replace-regex','response-body-replace-regex','response-body-json-add','response-body-json-replace','response-body-json-del','response-body-json-jq','mock-response-body'}
RULE_TYPES = {'DOMAIN','DOMAIN-SUFFIX','DOMAIN-KEYWORD','DOMAIN-WILDCARD','IP-CIDR','IP-CIDR6','GEOIP','GEOIP6','USER-AGENT','URL-REGEX','PROCESS-NAME','PROCESS-PATH','DEST-PORT','SRC-PORT','PROTOCOL','NETWORK','INBOUND','SSID','WIFI-SSID','AND','OR','NOT','FINAL','MATCH'}
BINARY_BODY_SCRIPTS = {'youtube.js','bilibiliProtoA.js','tiebaProto.js','spotify.js','baiduMap.js'}
HOSTNAME_TYPOS = {'souhu':'sohu','aimai-guide':'waimai-guide'}
REQUIRED_COVERED_HOSTS = {'mcs-mimp-web.sf-express.com','ucmp-static.sf-express.com','outfliggys.m.taobao.com','suyun-guest.daojia.com','image.suning.cn','s1.api.tv.itc.cn','api.k.sohu.com','waimai-guide.ele.me'}
README_START = '<!-- AUTO_PLUGIN_STATS:START -->'
README_END = '<!-- AUTO_PLUGIN_STATS:END -->'


def parse_sections(text):
    sections, current, seen, duplicates = defaultdict(list), None, set(), []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\[([^\]]+)\]\s*$', line.strip())
        if match:
            current = match.group(1).strip()
            if current in seen:
                duplicates.append((number, current))
            seen.add(current)
        elif current is not None:
            sections[current].append((number, line))
    return sections, duplicates


def is_public_suffix(domain):
    labels = domain.split('.')
    return len(labels) == 1 or (len(labels) == 2 and domain.lower() in PUBLIC_SUFFIX_2L)


def check_hostname(host):
    raw = host.strip()
    candidate = raw[1:] if raw.startswith('-') else raw
    if not candidate:
        return '空 hostname / 排除项'
    if IP_RE.fullmatch(candidate):
        return '裸 IPv4 不应放入 MITM hostname'
    try:
        ipaddress.ip_address(candidate.strip('[]'))
        return '裸 IPv6 不应放入 MITM hostname'
    except ValueError:
        pass
    if '*' in candidate or '?' in candidate:
        if not re.fullmatch(r'\*\.[A-Za-z0-9.-]+', candidate):
            return '非标准通配符；仅允许 *.后缀'
        suffix = candidate[2:]
        if not HOST_RE.fullmatch(suffix):
            return '通配 hostname 后缀格式非法'
        if is_public_suffix(suffix):
            return '通配 hostname 是公共后缀'
        return None
    if not HOST_RE.fullmatch(candidate):
        return '域名格式非法或缺少有效 TLD'
    return None


def host_covered(host, hostset):
    host = host.lower().rstrip('.')
    for item in hostset:
        value = item.lower().strip()
        if value.startswith('-'):
            continue
        if value == host:
            return True
        if value.startswith('*.') and host.endswith('.' + value[2:]):
            return True
    return False


def count_entries(lines):
    return sum(1 for _, line in lines if line.strip() and not line.lstrip().startswith('#'))


def parse_argument_names(lines):
    names = set()
    for _, line in lines:
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        if match:
            names.add(match.group(1))
    return names


def extract_script_url(line):
    """提取 Loon Script 行中的远程脚本 URL，兼容 script-path= 与 script("URL")。"""
    match = re.search(r"script-path\s*=\s*(https?://[^,\s]+)", line, re.I)
    if match:
        return match.group(1).rstrip(',')
    match = re.search(r'''script\(\s*(["'])(https?://.*?)\1''', line, re.I)
    return match.group(2).rstrip(',') if match else None


def inspect_plugin(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    sections, duplicate_sections = parse_sections(text)
    errors, warnings = [], []
    required = ('Argument','Rule','Rewrite','Script','MITM')
    for name in required:
        if name not in sections:
            errors.append('缺少必要区块 [%s]' % name)
    for line, name in duplicate_sections:
        errors.append('第 %d 行重复定义区块 [%s]' % (line, name))

    hostset, host_locations = set(), defaultdict(list)
    for number, line in sections.get('MITM', []):
        value = line.strip()
        if not value or value.startswith('#'):
            continue
        if not re.match(r'^hostname\s*=', value, re.I):
            warnings.append('MITM 第 %d 行不是 hostname 声明：%s' % (number, value[:120]))
            continue
        for host in value.split('=', 1)[1].split(','):
            host = host.strip()
            if not host:
                continue
            hostset.add(host)
            host_locations[host.lower()].append(number)
            problem = check_hostname(host)
            if problem:
                errors.append('MITM 第 %d 行 %s：%s' % (number, host, problem))
            core = host.lstrip('-').lower()
            for bad, good in HOSTNAME_TYPOS.items():
                if bad in core.split('.'):
                    errors.append('MITM 第 %d 行存在已知拼写错误 %r（请核实 %r）：%s' % (number, bad, good, host))
    for host, locations in host_locations.items():
        if len(locations) > 1:
            warnings.append('MITM hostname 重复 %s（行 %s）' % (host, ','.join(map(str, locations))))
    for host in sorted(REQUIRED_COVERED_HOSTS):
        if not host_covered(host, hostset):
            errors.append('已知规则主机 %s 未被 MITM 覆盖' % host)

    rule_lines = sections.get('Rule', [])
    for number, line in rule_lines:
        value = line.strip()
        if not value or value.startswith('#'):
            continue
        rule_type = value.split(',', 1)[0].strip()
        if rule_type.upper() not in RULE_TYPES:
            warnings.append('Rule 第 %d 行未知/自定义类型 %r，请对照 Loon 文档核实' % (number, rule_type))
        elif rule_type != rule_type.upper():
            warnings.append('Rule 第 %d 行类型大小写不统一：%s' % (number, rule_type))
        if value.endswith(','):
            errors.append('Rule 第 %d 行末尾存在空字段' % number)

    rewrite_seen = {}
    for number, line in sections.get('Rewrite', []):
        value = line.strip()
        if not value or value.startswith('#'):
            continue
        if re.match(r'^(request|response)\s+if\b', value):
            if ' then ' not in value:
                errors.append('Rewrite 第 %d 行新版语法缺少 then' % number)
            guard = re.search(r'\$\{url\}\s*~=\s*/((?:\\.|[^/])*)/', value)
            if not guard:
                errors.append('Rewrite 第 %d 行无法识别 URL 正则守卫' % number)
            else:
                pattern = guard.group(1).replace(r'\/', '/')
                try:
                    re.compile(pattern)
                except re.error as exc:
                    warnings.append('Rewrite 第 %d 行正则不符合 Python re（需用 Loon/ICU 实测）：%s' % (number, exc))
            continue
        tokens = value.split()
        if len(tokens) < 2:
            errors.append('Rewrite 第 %d 行字段不足：%s' % (number, value[:160]))
            continue
        action = tokens[1]
        if action not in LEGACY_ACTIONS:
            errors.append('Rewrite 第 %d 行未知旧版动作 %r' % (number, action))
        key = (tokens[0], action, ' '.join(tokens[2:]))
        if key in rewrite_seen:
            warnings.append('Rewrite 第 %d 行与第 %d 行完全重复' % (number, rewrite_seen[key]))
        else:
            rewrite_seen[key] = number

    args = parse_argument_names(sections.get('Argument', []))
    script_seen, script_urls, referenced_args = {}, set(), set()
    for number, line in sections.get('Script', []):
        value = line.strip()
        if not value or value.startswith('#'):
            continue
        if not re.match(r'^(?:http-request|http-response|cron\b|generic\b|request\s+if\b|response\s+if\b)', value):
            warnings.append('Script 第 %d 行无法识别脚本触发器：%s' % (number, value[:140]))
        if (re.match(r'^(?:request|response)\s+if\b', value)
                and ' then ' in value
                and not re.search(r'\bscript\s*\(', value, re.I)
                and not re.search(r'\bscript-path\s*=', value, re.I)):
            errors.append('Script 第 %d 行是 Rewrite Action 而不是 Script 调用；应移入 [Rewrite]：%s'
                          % (number, value[:140]))
        url = extract_script_url(value)
        if url:
            script_urls.add(url)
            base = url.split('?',1)[0].rsplit('/',1)[-1]
            if base in BINARY_BODY_SCRIPTS and not re.search(r'binary-body-mode[ ]*=[ ]*true([ ]|$)', value, re.I):
                errors.append('Script 第 %d 行二进制脚本 %s 缺少 binary-body-mode=true' % (number, base))
            trigger = re.match(r'^(http-request|http-response)[ ]+([^ ]+)', value)
            if trigger:
                key = (trigger.group(1), trigger.group(2), url)
                if key in script_seen:
                    warnings.append('Script 第 %d 行与第 %d 行存在相同触发器和脚本 URL' % (number, script_seen[key]))
                else:
                    script_seen[key] = number
        for option in re.findall(r'(?:enable|argument)\s*=\s*(?:\[[^\]]*\])?', value):
            referenced_args.update(re.findall(r'\{([A-Za-z_][A-Za-z0-9_]*)\}', option))
    for name in sorted(referenced_args - args):
        errors.append('Script 引用了未定义的 Argument：%s' % name)

    for number, line in rule_lines:
        normalized = re.sub(r'\s+', '', line.upper())
        if 'PROTOCOL,UDP' in normalized and 'DEST-PORT,443' in normalized:
            if not any(token in normalized for token in ('DOMAIN,','DOMAIN-SUFFIX,','DOMAIN-KEYWORD,','URL-REGEX,')):
                warnings.append('Rule 第 %d 行是全局 UDP/443 拦截，可能影响 HTTP/3/QUIC 正常连接' % number)

    stats = {name: count_entries(sections.get(name, [])) for name in required}
    stats['mitm_hostnames'] = sum(len(line.split('=',1)[1].split(',')) for _,line in sections.get('MITM',[]) if re.match(r'^\s*hostname\s*=',line,re.I))
    stats['unique_script_urls'] = len(script_urls)
    stats['argument_definitions'] = len(args)
    for warning in warnings:
        print('[警告] ' + warning)
    for error in errors:
        print('[错误] ' + error)
    print('\n校验 %s：错误 %d，警告 %d' % (path, len(errors), len(warnings)))
    print('统计：' + ' | '.join('%s=%s' % (k,v) for k,v in stats.items()))
    return errors, warnings, stats


def update_readme(path, stats):
    readme = Path(path)
    text = readme.read_text(encoding='utf-8')
    block = '\n'.join([README_START, '**由 GitHub Actions 自动更新的最新产物统计**', '',
        '| 区块 | 条目数 |', '|---|---:|',
        '| [Argument] | %d |' % stats['Argument'],
        '| [Rule] | %d |' % stats['Rule'],
        '| [Rewrite] | %d |' % stats['Rewrite'],
        '| [Script] | %d |' % stats['Script'],
        '| [MITM] hostname 条目 | %d |' % stats['mitm_hostnames'],
        '| 唯一远程脚本 URL | %d |' % stats['unique_script_urls'], README_END])
    pattern = re.compile(re.escape(README_START) + r'.*?' + re.escape(README_END), re.S)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text, count=1)
    else:
        anchor = re.search(r'当前产物统计由工作流自动维护：\s*\n', text)
        if not anchor:
            raise ValueError('README 找不到产物统计插入位置')
        text = text[:anchor.end()] + '\n' + block + '\n' + text[anchor.end():]
    readme.write_text(text, encoding='utf-8')


def check_remote_scripts(urls, limit=80, timeout=8):
    selected = sorted(urls)[:limit]
    def check(url):
        request = urllib.request.Request(url, headers={'User-Agent':'loon-plugin-validator/1.0'}, method='HEAD')
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return url, response.status, None
        except Exception as exc:
            return url, None, str(exc)
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for url, status, error in pool.map(check, selected):
            if error or (status and status >= 400):
                failed.append((url, status, error))
    print('远程脚本检查：检查 %d 个 URL，失败/不可验证 %d 个（仅警告）' % (len(selected), len(failed)))
    for url, status, error in failed:
        print('[远程警告] %s status=%s error=%s' % (url, status, error))


def main():
    parser = argparse.ArgumentParser(description='Loon plugin static validator')
    parser.add_argument('plugin')
    parser.add_argument('--update-readme', metavar='README')
    parser.add_argument('--check-remote', action='store_true')
    args = parser.parse_args()
    errors, warnings, stats = inspect_plugin(args.plugin)
    if args.update_readme:
        update_readme(args.update_readme, stats)
        print('已更新 README 统计：%s' % args.update_readme)
    if args.check_remote:
        sections, _ = parse_sections(Path(args.plugin).read_text(encoding='utf-8-sig'))
        urls = set()
        for _, line in sections.get('Script', []):
            url = extract_script_url(line)
            if url:
                urls.add(url)
        check_remote_scripts(urls)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
