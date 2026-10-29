#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并两个 Loon 插件（Loon <-> Loon 融合，非 QuanX 转换）。

以 R-Store 转换产物（allAdRewrite.plugin）为 base，整合 fmz200 的 blockAdsV2：
  - [Rewrite] / [Script]：按【规范化 URL 正则】去重，base 已有的正则一律保留 base，
    blockAdsV2 仅补充 base 没有的正则（含跨段冲突，统一 base 优先）；
  - [MITM]：blockAdsV2 的非标准 hostname（中间/前缀通配、通配 TLD、裸 IP、源损坏）
    按与 R-Store 转换器一致的“*.最长字面后缀”规则收敛，公共后缀感知，再与 base 合并去重；
  - [Argument]：仅 blockAdsV2 有，内部去重后纳入；
  - [Rule]：以 blockAdsV2 规则为底，再抓取 R-Store 独立分流（allAdBlock.list），按语义
    覆盖判定（DOMAIN 精确 / DOMAIN-SUFFIX 后缀包含 / DOMAIN-KEYWORD 关键字 / IP-CIDR 网段
    包含）只追加未被覆盖的规则。最终单插件即可完整替代独立分流，无需再装 allAdBlock。

用法：
  python3 merge_plugins.py --base allAdRewrite.plugin --extra fetch --out allAdRewrite.plugin
  python3 merge_plugins.py --base allAdRewrite.plugin --extra sources/blockAdsV2.plugin --out x.plugin
  # --filter 控制 R-Store 分流来源：fetch（默认）/ 本地路径 / none（不补全）
"""
import argparse, datetime, ipaddress, re, sys, urllib.request

BLOCKV2_URL = ('https://raw.githubusercontent.com/fmz200/wool_scripts/refs/heads/'
                'main/Loon/plugin/blockAdsV2.plugin')
BLOCKV2_MIRRORS = [
    'https://cdn.jsdelivr.net/gh/fmz200/wool_scripts@main/Loon/plugin/blockAdsV2.plugin',
    'https://fastly.jsdelivr.net/gh/fmz200/wool_scripts@main/Loon/plugin/blockAdsV2.plugin',
]

# R-Store 独立分流（QuanX filter），用于补全 [Rule]
FILTER_URL = ('https://raw.githubusercontent.com/zirawell/R-Store/main/'
              'Rule/QuanX/Adblock/All/filter/allAdBlock.list')
FILTER_MIRRORS = [
    'https://cdn.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/filter/allAdBlock.list',
    'https://fastly.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/filter/allAdBlock.list',
]
# QuanX filter 类型/策略 -> Loon
QX_TYPE_MAP = {
    'host': 'DOMAIN', 'host-suffix': 'DOMAIN-SUFFIX', 'host-keyword': 'DOMAIN-KEYWORD',
    'host-wildcard': 'DOMAIN-WILDCARD', 'ip-cidr': 'IP-CIDR', 'ip6-cidr': 'IP-CIDR6',
}
QX_POLICY_MAP = {
    'reject': 'REJECT', 'reject-200': 'REJECT', 'reject-img': 'REJECT-IMG',
    'reject-dict': 'REJECT-DICT', 'reject-array': 'REJECT-ARRAY',
    'reject-drop': 'REJECT-DROP',
}
FILTER_NO_RESOLVE = {'IP-CIDR', 'IP-CIDR6'}

# 常见两级公共后缀（registrable domain 需取三级）
PUBLIC_SUFFIX_2L = {
    'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'ac.cn', 'mil.cn',
    'com.hk', 'com.tw', 'com.au', 'com.sg', 'com.my', 'com.vn', 'com.ph',
    'com.br', 'com.mx', 'com.tr', 'co.jp', 'or.jp', 'ne.jp', 'ac.jp',
    'co.uk', 'org.uk', 'ac.uk', 'co.kr', 'or.kr', 'co.in', 'co.nz',
    'co.th', 'co.id',
}
HOST_OK = re.compile(r'^(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$')
IP_OK = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True, help='base 插件（R-Store 产物）')
ap.add_argument('--extra', required=True,
                help='blockAdsV2 路径；传 fetch 则从上游拉取（含镜像回退）')
ap.add_argument('--filter', default='fetch',
                help='R-Store 分流来源：fetch（默认，含镜像）/ 本地路径 / none（不补全 [Rule]）')
ap.add_argument('--out', required=True, help='合并输出路径')
args = ap.parse_args()


def is_public_suffix(d):
    labels = d.split('.')
    if len(labels) == 1:
        return True
    return len(labels) == 2 and d.lower() in PUBLIC_SUFFIX_2L


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8')


def split_sections(text):
    """返回 (header行, {段: [行]})，仅识别顶层 [X] 段"""
    out, cur, header = {}, None, []
    for line in text.split('\n'):
        m = re.match(r'^\[([A-Za-z]+)\]\s*$', line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur is None:
            header.append(line)
        else:
            out[cur].append(line)
    return header, out


def real_lines(ls):
    """去掉空行与注释行"""
    return [x for x in ls if x.strip() and not x.lstrip().startswith('#')]


# ---------------- URL 正则抽取与规范化 ----------------
def _read_v2_regex(line):
    """从 v2 行 `... ~= /PATTERN/flags ...` 读取 / 之间的正则（处理转义斜杠）"""
    m = re.search(r'~\s*=\s*/', line)
    if not m:
        return None
    i, n, buf = m.end(), len(line), []
    while i < n:
        c = line[i]
        if c == '\\' and i + 1 < n:
            buf.append(line[i:i + 2])
            i += 2
            continue
        if c == '/':
            break
        buf.append(c)
        i += 1
    return ''.join(buf)


def norm_regex(r):
    """正则规范化：统一转义斜杠；其余保持，避免语义改动"""
    return r.replace('\\/', '/').strip()


def entry_regex(line):
    """返回任意一种写法的规范化 URL 正则；无法识别返回 None"""
    if '~= /' in line or '~=/' in line:
        r = _read_v2_regex(line)
        return norm_regex(r) if r else None
    # v1 脚本：http-response/http-request ^PAT script-path=...（正则在第二个 token）
    m = re.match(r'^http-(?:response|request)\s+(\S+)', line)
    if m:
        return norm_regex(m.group(1))
    # legacy rewrite：首个空白分隔 token
    return norm_regex(line.split()[0])


# ---------------- blockAdsV2 hostname 收敛 ----------------
def normalize_extra_host(h):
    """blockAdsV2 的 hostname -> Loon 合法 hostname 列表；无法安全收敛返回 []。
    保留 - 前缀排除项（对收敛后的主体重新加 -）。"""
    h = h.strip().strip('.')
    neg = False
    if h.startswith('-'):
        neg, h = True, h[1:]
    # 源损坏：形如 cupid.51job*.comhostname = xxx，截断拼接
    h = re.split(r'hostname', h)[0].strip().strip('.')
    if not h:
        return []
    # 裸 IP / 通配 IP：Loon hostname 不按 IP 处理，丢弃
    if IP_OK.match(h) or (h.replace('.', '').replace('*', '').isdigit() and '*' in h):
        return []
    # 通配 TLD（*.xxx.* / xxx.*）：去掉末尾 .*
    if h.endswith('.*'):
        h = h[:-2].strip('.')
    # 已知 typo（按完整标签）：souhu -> sohu
    h = re.sub(r'(^|\.)souhu(\.|$)', r'\1sohu\2', h)
    if not h:
        return []
    # 具体域名
    if '*' not in h and '?' not in h:
        if not HOST_OK.match(h):
            return []                       # 缺 TLD 等无法安全补全，丢弃
        out = [] if is_public_suffix(h) else [h]
        return ['-' + x for x in out] if neg else out
    # 标准 *.后缀
    if h.startswith('*.') and '*' not in h[2:] and '?' not in h[2:]:
        out = [] if is_public_suffix(h[2:]) else [h]
        return ['-' + x for x in out] if neg else out
    # 中间/前缀通配（m*.amap.com、*-spclient、*default...）：退化为 *.最长字面后缀
    lit = []
    for lab in reversed([x for x in h.split('.') if x]):
        if '*' in lab or '?' in lab:
            break
        lit.append(lab)
    lit = lit[::-1]
    if len(lit) < 2:
        return []
    need = 3 if '.'.join(lit[-2:]).lower() in PUBLIC_SUFFIX_2L else 2
    if len(lit) < need or is_public_suffix('.'.join(lit[-need:])):
        return []
    res = '*.' + '.'.join(lit)
    out = [res] if re.match(r'^\*\.[A-Za-z0-9\-\.]+$', res) else []
    return ['-' + x for x in out] if neg else out


def dedup_keep_order(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------- R-Store 分流解析与覆盖判定 ----------------
def norm_host(h):
    h = h.strip().lower()
    return h[:-1] if h.endswith('.') else h


def parse_qx_filter(text):
    """QuanX filter 文本 -> Loon 规则行列表；跳过注释/hostname/未知类型。"""
    out = []
    for line in text.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if s.lower().startswith('hostname') and '=' in s:
            continue
        parts = [p.strip() for p in s.split(',')]
        if len(parts) < 3:
            continue
        ltype = QX_TYPE_MAP.get(parts[0].lower())
        lpolicy = QX_POLICY_MAP.get(parts[2].lower())
        if not ltype or not lpolicy:
            continue
        extra = ',no-resolve' if ltype in FILTER_NO_RESOLVE else ''
        out.append('%s,%s,%s%s' % (ltype, norm_host(parts[1]), lpolicy, extra))
    return out


def build_rule_index(rule_lines):
    """从 Loon 规则行构建覆盖判定索引。"""
    idx = {'exact': set(), 'suffix': set(), 'keyword': set(), 'ip': []}
    for l in rule_lines:
        parts = [p.strip() for p in l.split(',')]
        t, v = parts[0], norm_host(parts[1]) if len(parts) > 1 else ''
        if t == 'DOMAIN':
            idx['exact'].add(v)
        elif t == 'DOMAIN-SUFFIX':
            idx['suffix'].add(v)
        elif t == 'DOMAIN-KEYWORD':
            idx['keyword'].add(v)
        elif t in ('IP-CIDR', 'IP-CIDR6'):
            try:
                idx['ip'].append(ipaddress.ip_network(v, strict=False))
            except Exception:
                pass
    return idx


def add_to_index(line, idx):
    parts = [p.strip() for p in line.split(',')]
    t, v = parts[0], norm_host(parts[1])
    if t == 'DOMAIN':
        idx['exact'].add(v)
    elif t == 'DOMAIN-SUFFIX':
        idx['suffix'].add(v)
    elif t == 'DOMAIN-KEYWORD':
        idx['keyword'].add(v)
    elif t in ('IP-CIDR', 'IP-CIDR6'):
        try:
            idx['ip'].append(ipaddress.ip_network(v, strict=False))
        except Exception:
            pass


def rule_is_covered(line, idx):
    parts = [p.strip() for p in line.split(',')]
    t, v = parts[0], norm_host(parts[1])
    if t == 'DOMAIN':
        if v in idx['exact']:
            return True
        for sx in idx['suffix']:
            if v == sx or v.endswith('.' + sx):
                return True
        for kw in idx['keyword']:
            if kw in v:
                return True
        return False
    if t == 'DOMAIN-SUFFIX':
        for sx in idx['suffix']:
            if v == sx or v.endswith('.' + sx):
                return True
        return False
    if t == 'DOMAIN-KEYWORD':
        return v in idx['keyword']
    if t in ('IP-CIDR', 'IP-CIDR6'):
        try:
            net = ipaddress.ip_network(v, strict=False)
        except Exception:
            return False
        for bn in idx['ip']:
            if bn.version == net.version and net.subnet_of(bn):
                return True
        return False
    return False   # DOMAIN-WILDCARD 等其它类型保守处理


# ---------------- 读取两个插件 ----------------
base_text = open(args.base, encoding='utf-8').read()
if args.extra == 'fetch':
    extra_text, last_err = None, None
    for u in [BLOCKV2_URL] + BLOCKV2_MIRRORS:
        try:
            extra_text = fetch(u)
            print('[fetch] 已获取 blockAdsV2:', u)
            break
        except Exception as e:
            last_err = e
            print('[fetch] 失败:', u, e, file=sys.stderr)
    if extra_text is None:
        raise SystemExit('blockAdsV2 获取失败: %s' % last_err)
else:
    extra_text = open(args.extra, encoding='utf-8').read()

_, base_sec = split_sections(base_text)
_, extra_sec = split_sections(extra_text)

# base 全部 URL 正则（Rewrite + Script），用于跨段去重
base_regex = set()
for sec in ('Rewrite', 'Script'):
    for l in real_lines(base_sec.get(sec, [])):
        r = entry_regex(l)
        if r:
            base_regex.add(r)

# ---------------- blockAdsV2 残留 QuanX 旧行处理 ----------------
# 旧 reject 动作 -> v2（status 取官方映射）
_LEGACY_REJECT = {
    'reject': 'reject(404)', 'reject-200': 'reject(200)',
    'reject-img': 'reject_img(200)', 'reject-dict': 'reject_dict(200)',
    'reject-array': 'reject_array(200)', 'reject-video': 'reject_video(200)',
}


def convert_legacy_line(line):
    """把 blockAdsV2 中残留的 QuanX 旧写法转成 Loon v2；无法安全转换返回 None（丢弃）。
    覆盖本源实际出现的三类：裸 reject、两种 302；其余（header、v1 脚本、302 到文件、
    损坏行）base 已覆盖或不可靠，统一丢弃。"""
    s = line.strip()
    toks = s.split()

    # 1) 裸 reject 家族：^PAT reject-dict
    if len(toks) == 2 and toks[1] in _LEGACY_REJECT:
        return ('request if ${url} ~= /%s/ then %s'
                % (toks[0], _LEGACY_REJECT[toks[1]]))

    # 2) vgtime：^(... )false(...) $1true$2 302（末尾 302）
    if s.endswith(' 302') and 'close_ad=' in s:
        m = re.match(r'^(\^.+?)\s+\$1true\$2\s+302$', s)
        if m:
            return ('request if ${url} ~= /%s/ as m then redirect(302, "${m.1}true${m.2}")'
                    % m.group(1))

    # 3) zhihu：^PAT 302 http://$1（302 后接目标）
    m = re.match(r'^(\^.+?)\s+302\s+(\S+)$', s)
    if m and 'zhihu' in s:
        tgt = m.group(2).replace('$1', '${m.1}')
        return ('request if ${url} ~= /%s/ as m then redirect(302, "%s")'
                % (m.group(1), tgt))

    # 其余旧写法（header / http-response 脚本 / 302 到文件 / 损坏）：丢弃
    return None


# ---- 合并 Rewrite / Script：base 原文 + extra 中 base 未覆盖的正则 ----
merged = {}
stats = {'rw_added': 0, 'sc_added': 0, 'rw_dup': 0, 'sc_dup': 0,
         'legacy_conv': 0, 'legacy_drop': 0, 'rw_exact_drop': 0, 'sc_exact_drop': 0}
for sec, key in (('Rewrite', 'rw'), ('Script', 'sc')):
    bl = real_lines(base_sec.get(sec, []))
    added = []
    for l in real_lines(extra_sec.get(sec, [])):
        is_v2 = bool(re.match(r'^(request|response)\b', l.strip()))
        if not is_v2:
            conv = convert_legacy_line(l)
            if conv is None:
                stats['legacy_drop'] += 1
                continue
            l = conv
            stats['legacy_conv'] += 1
        r = entry_regex(l)
        if r and r in base_regex:
            stats[key + '_dup'] += 1
            continue
        added.append(l)
        if r:
            base_regex.add(r)               # 防止 extra 内部重复
    stats[key + '_added'] = len(added)
    combined = bl + added
    deduped = dedup_keep_order(combined)   # 折叠完全相同的行（base 内部 12 组）
    stats[key + '_exact_drop'] = len(combined) - len(deduped)
    merged[sec] = deduped

# ---- Argument：仅 extra，内部按参数名去重 ----
arg_items = dedup_keep_order(real_lines(extra_sec.get('Argument', [])))

# ---- Rule：blockAdsV2 规则 + R-Store 分流中未覆盖的规则 ----
rule_items = dedup_keep_order(real_lines(extra_sec.get('Rule', [])))
fstats = {'total': 0, 'covered': 0, 'added': 0}
if args.filter != 'none':
    if args.filter == 'fetch':
        ftext, f_err = None, None
        for u in [FILTER_URL] + FILTER_MIRRORS:
            try:
                ftext = fetch(u)
                print('[fetch] 已获取 R-Store filter:', u)
                break
            except Exception as e:
                f_err = e
                print('[fetch] 失败:', u, e, file=sys.stderr)
        if ftext is None:
            raise SystemExit('R-Store filter 获取失败: %s' % f_err)
    else:
        ftext = open(args.filter, encoding='utf-8').read()
    f_rules = dedup_keep_order(parse_qx_filter(ftext))
    idx = build_rule_index(rule_items)
    added = []
    for fr in f_rules:
        fstats['total'] += 1
        if rule_is_covered(fr, idx):
            fstats['covered'] += 1
        else:
            added.append(fr)
            add_to_index(fr, idx)
            fstats['added'] += 1
    rule_items = dedup_keep_order(rule_items + added)

# ---- MITM：base 主机（已规范） + extra 收敛后主机，合并去重 ----
mitm = []
for l in base_sec.get('MITM', []):
    if '=' in l:
        mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
extra_raw = []
for l in extra_sec.get('MITM', []):
    if '=' in l:
        extra_raw += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
extra_dropped = []
for h in extra_raw:
    got = normalize_extra_host(h)
    if not got:
        extra_dropped.append(h)
    else:
        mitm += got
mitm = dedup_keep_order(mitm)

# ---------------- 输出 ----------------
today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
header = [
    '#!name=R-Store × 奶思 blockAdsV2 去广告净化合集',
    '#!desc=合并 zirawell/R-Store 与 fmz200/blockAdsV2（约730款 App/小程序），按 URL 正则去重，R-Store 优先；[Rule] 已含两套上游分流，单插件自包含',
    '#!author=zirawell / fmz200（本仓库自动合并）',
    '#!homepage=https://github.com/XcvcvX/loon-change',
    '#!merged-at=%s' % today,
    '#!note=R-Store 规则保留原始写法，blockAdsV2 为 Rewrite/Script v2；Loon 支持新旧语法同段混用。',
    '#!sources=R-Store rewrite+filter(QuanX->Loon) + fmz200/wool_scripts blockAdsV2',
    '',
]
out = list(header)
if arg_items:
    out += ['[Argument]'] + arg_items + ['']
if rule_items:
    out += ['[Rule]'] + rule_items + ['']
out += ['[Rewrite]'] + merged['Rewrite'] + ['']
out += ['[Script]'] + merged['Script'] + ['']
out += ['[MITM]', 'hostname = ' + ', '.join(mitm), '']

open(args.out, 'w', encoding='utf-8').write('\n'.join(out))

print('\n[merge] 输出:', args.out)
print('  Rewrite：base %d + 新增 %d（去重跳过 %d）'
      % (len(real_lines(base_sec.get('Rewrite', []))), stats['rw_added'], stats['rw_dup']))
print('  Script ：base %d + 新增 %d（去重跳过 %d）'
      % (len(real_lines(base_sec.get('Script', []))), stats['sc_added'], stats['sc_dup']))
print('  Rule   ：%d 条；Argument：%d 个开关' % (len(rule_items), len(arg_items)))
if args.filter != 'none':
    print('  分流补全：R-Store %d 条，已覆盖 %d，补入 %d（独立分流可废弃）'
          % (fstats['total'], fstats['covered'], fstats['added']))
print('  旧行   ：转换 %d，丢弃 %d（base 已覆盖或不可靠）'
      % (stats['legacy_conv'], stats['legacy_drop']))
print('  MITM   ：%d 个主机（blockAdsV2 无法收敛丢弃 %d）' % (len(mitm), len(extra_dropped)))
if extra_dropped:
    print('  丢弃的 extra hostname：', ', '.join(extra_dropped[:20]))
