#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantumult X 分流规则 (.list) -> Loon 原生规则

QuanX 用小写类型名(host/host-suffix/host-keyword/ip-cidr/ip6-cidr)、小写策略(reject)；
Loon 用 Surge 风格的大写类型名(DOMAIN/DOMAIN-SUFFIX/DOMAIN-KEYWORD/IP-CIDR/IP-CIDR6)、
大写策略(REJECT)。类型名不认识，Loon 就会整条忽略 —— 这就是"导入后只识别一部分"的原因。

注意：作者自己的 Surge 版带了 `extended-matching, pre-matching`，这两个是 Surge 专有参数，
Loon 并不支持，照抄反而会让规则解析失败。这里只加 Loon 官方文档明确支持的 `no-resolve`。

用法：
  python3 convert_filter_qx2loon.py                     # 拉取上游，输出 list + plugin
  python3 convert_filter_qx2loon.py -i local.list
"""
import argparse, datetime, os, re, sys, urllib.request

UPSTREAM = ('https://raw.githubusercontent.com/zirawell/R-Store/main/'
            'Rule/QuanX/Adblock/All/filter/allAdBlock.list')
MIRRORS = [
    'https://cdn.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/filter/allAdBlock.list',
    'https://fastly.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/filter/allAdBlock.list',
]

# QuanX 类型 -> Loon 类型
TYPE_MAP = {
    'host': 'DOMAIN',
    'host-suffix': 'DOMAIN-SUFFIX',
    'host-keyword': 'DOMAIN-KEYWORD',
    'host-wildcard': 'DOMAIN-WILDCARD',
    'ip-cidr': 'IP-CIDR',
    'ip6-cidr': 'IP-CIDR6',
    'geoip': 'GEOIP',
    'url-regex': 'URL-REGEX',
    'user-agent': 'USER-AGENT',
    'dest-port': 'DEST-PORT',
    'src-ip': 'SRC-IP',
    'ip-asn': 'IP-ASN',
}

# QuanX 策略 -> Loon 策略
POLICY_MAP = {
    'reject': 'REJECT',
    'reject-200': 'REJECT',
    'reject-img': 'REJECT-IMG',
    'reject-dict': 'REJECT-DICT',
    'reject-array': 'REJECT-ARRAY',
    'reject-drop': 'REJECT-DROP',
    'direct': 'DIRECT',
    'proxy': 'PROXY',
}

# 只有 IP 类规则加 no-resolve：目标已是 IP，无需 DNS 解析
NO_RESOLVE = {'IP-CIDR', 'IP-CIDR6', 'IP-ASN', 'GEOIP'}

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', help='本地 QuanX 规则文件；不指定则从上游拉取')
ap.add_argument('--list', default='allAdBlock-Loon.list', help='纯规则行输出路径')
ap.add_argument('--plugin', default='allAdBlock-Loon.plugin', help='插件输出路径')
args = ap.parse_args()


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8')


if args.input:
    raw = open(args.input, encoding='utf-8').read()
else:
    raw, last_err = None, None
    for u in [UPSTREAM] + MIRRORS:
        try:
            raw = fetch(u)
            print('[fetch] 已获取:', u)
            break
        except Exception as e:
            last_err = e
            print('[fetch] 失败:', u, e, file=sys.stderr)
    if raw is None:
        raise SystemExit('上游规则获取失败: %s' % last_err)


rules, unknown, stats = [], [], {}
upstream_date, upstream_count = '', ''
csv = {}

for line in raw.split('\n'):
    s = line.strip()
    if not s:
        continue
    if s.startswith('#'):
        if s.startswith('#!date='):
            upstream_date = s.split('=', 1)[1].strip()
        if s.startswith('#!count='):
            upstream_count = s.split('=', 1)[1].strip()
        continue
    if s.lower().startswith('hostname') and '=' in s:      # QuanX filter 的 hostname 行
        csv['hostname'] = s.split('=', 1)[1].strip()
        continue

    parts = [p.strip() for p in s.split(',')]
    if len(parts) < 3:
        unknown.append((s, '字段不足 3 个'))
        continue

    qtype, value, policy = parts[0].lower(), parts[1], parts[2].lower()
    ltype = TYPE_MAP.get(qtype)
    if not ltype:
        unknown.append((s, '未知规则类型: ' + qtype))
        stats['未知类型'] = stats.get('未知类型', 0) + 1
        continue

    lpolicy = POLICY_MAP.get(policy)
    if not lpolicy:
        unknown.append((s, '未知策略: ' + policy))
        stats['未知策略'] = stats.get('未知策略', 0) + 1
        continue

    extra = ',no-resolve' if ltype in NO_RESOLVE else ''
    rules.append('%s,%s,%s%s' % (ltype, value, lpolicy, extra))
    stats['%s -> %s' % (qtype, ltype)] = stats.get('%s -> %s' % (qtype, ltype), 0) + 1

if not upstream_date:
    upstream_date = datetime.date.today().isoformat()

# ---------- 纯规则行（用于 Loon「规则订阅」）----------
list_out = [
    '# Loon 原生分流规则 · 由 Quantumult X 规则转换',
    '# 上游: https://github.com/zirawell/R-Store',
    '# 上游版本: %s' % upstream_date,
    '# 用法: 在 Loon 主配置 [Rule] 段中加一行（放在 FINAL 之前）:',
    '#   <本文件 URL>,REJECT',
    '',
] + rules

# ---------- 插件（含 [Rule] 段）----------
plugin_out = [
    '#!name = 全部-广告拦截合集-分流规则(Loon)',
    '#!desc = R-Store 去广告分流规则，按 Loon 原生规则语法转换',
    '#!author = zirawell(规则源)',
    '#!homepage = https://github.com/zirawell/R-Store',
    '#!icon = https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Icon/Filter/AdBlock.png',
    '#!system = iOS,iPadOS,macOS',
    '#!date = %s' % upstream_date,
    '#!tag = 去广告',
    '#!type = normal',
    '#%s' % (('  ' + upstream_count) if upstream_count else ''),
    '#',
    '# 转换说明:',
    '#   host         -> DOMAIN',
    '#   host-suffix  -> DOMAIN-SUFFIX',
    '#   host-keyword -> DOMAIN-KEYWORD',
    '#   ip-cidr      -> IP-CIDR   (+ no-resolve)',
    '#   ip6-cidr     -> IP-CIDR6  (+ no-resolve)',
    '#   reject       -> REJECT',
    '# 未使用 Surge 专有的 extended-matching / pre-matching，Loon 不支持这两个参数。',
    '',
    '[Rule]',
] + rules

for path, content in ((args.list, list_out), (args.plugin, plugin_out)):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    open(path, 'w', encoding='utf-8').write('\n'.join(content) + '\n')
    print('输出:', path)

print('\n=== 转换统计 ===')
for k, v in sorted(stats.items(), key=lambda x: -x[1]):
    print('%6d  %s' % (v, k))
print('规则总数: %d' % len(rules))
if unknown:
    print('跳过/异常: %d' % len(unknown))
    for s, why in unknown[:10]:
        print('   [%s] %s' % (why, s[:90]))
