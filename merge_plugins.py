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
import argparse, datetime, ipaddress, json, os, re, sys, urllib.request
from source_guard import (validate_blockv2, validate_filter, validate_myblockads,
                          fetch_validated)
from mitm_policy import mitm_skip_host

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

# MyBlockAds（RuCu6/Walalala 自用去广告大合集）：仅经 Cloudflare Pages 发布，无公开 GitHub 源。
# 在线抓取失败时回退到仓库内置缓存 sources/myblockads.lpx，保证自动更新不中断、独有规则不丢失。
MYBLOCKADS_URL = 'https://rucu6.pages.dev/Plugins/myblockads.lpx'
MYBLOCKADS_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'myblockads.lpx')

# aoomee 独立 App 去广告插件仓库（工作流 clone 到本地后传入目录）
AOOMEE_REPO = 'https://github.com/aoomee/Loon-Adblock-Plugins.git'
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
HOST_OK = re.compile(r'^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
IP_OK = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')

# 不使用不完整的 TLD 白名单拒绝域名；公共后缀表只用于避免过宽通配。

# MITM skip policy is shared with deep_audit.py to prevent false missing-host alarms.


ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True, help='base 插件（R-Store 产物）')
ap.add_argument('--extra', required=True,
                help='blockAdsV2 路径；传 fetch 则从上游拉取（含镜像回退）')
ap.add_argument('--filter', default='fetch',
                help='R-Store 分流来源：fetch（默认，含镜像）/ 本地路径 / none（不补全 [Rule]）')
ap.add_argument('--apps', default=None,
                help='Thelongdarkorg/loon-plugins 仓库目录（可选）；遍历其中去广告插件并入，'
                     '仅识别 *_ad_block.plugin / *_splash_ad_block.plugin，跳过 ai_auto_node')
ap.add_argument('--aoomee', default=None,
                help='aoomee/Loon-Adblock-Plugins 仓库目录（工作流 clone 后传入）；遍历其中 '
                     '.plugin/.lpx 独立 App 插件并入，独立 App 插件优先级最高（同正则替换其他来源）')
ap.add_argument('--zmjde', default=None,
                help='zmjde/loon-plugins 仓库目录（工作流 clone 后传入）；读取 8 个指定 .lpx：'
                     'DiDi/PinDuoDuo/闲鱼/淘宝/什么值得买作为 App 高优先级完整并入，'
                     'Block_HTTPDNS/BlockAdvertisers/可莉广告过滤器以 base 优先只补不覆盖')
ap.add_argument('--qxapp', action='append', default=None,
                help='QuanX 单文件 App 插件（.conf，如瓜子影视）本地路径，可重复传入；'
                     '脚本内解析 hostname 并把 qx 规则转为 Loon v2，按专属 App 高优先级完整并入')
ap.add_argument('--amap', default=None,
                help='RuCu6/sooyaaabo 高德地图独立 Loon 插件（经来源校验的本地 .lpx 文件）；最高 App 优先级')
ap.add_argument('--myblockads', default='fetch',
                help='MyBlockAds 来源：fetch（默认，在线抓取失败回退 sources/myblockads.lpx 缓存）'
                     '/ 本地路径 / none（不并入）')
ap.add_argument('--out', required=True, help='合并输出路径')
ap.add_argument('--provenance-out', default=None, help='可选：输出逐条规则来源追溯 JSON')
ap.add_argument('--source-report', default=None, help='可选：将 source-report.json 上游版本信息附入来源追溯')
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
            out.setdefault(cur, [])
        elif cur is None:
            header.append(line)
        else:
            out[cur].append(line)
    return header, out


def iter_app_plugins(appdir):
    """遍历 Thelongdarkorg/loon-plugins 目录，产出所有去广告插件 (文件名, 文本)。
    仅识别 *_ad_block.plugin / *_splash_ad_block.plugin；跳过 ai_auto_node（分流类）。"""
    names = sorted(x for x in os.listdir(appdir)
                   if x.endswith('.plugin')
                   and (x.endswith('_ad_block.plugin') or x.endswith('_splash_ad_block.plugin'))
                   and not x.startswith('ai_auto_node'))
    for n in names:
        yield n, open(os.path.join(appdir, n), encoding='utf-8').read()


def parse_loose_sections(text):
    """归一化段解析：识别含空格段名（URL Rewrite），并把 MitM/Mitm/MITM 三种大小写
    统一为 MITM；返回 {段名: [非空非注释行]}。"""
    out, cur = {}, None
    for line in text.split('\n'):
        m = re.match(r'^\[(.+?)\]\s*$', line)
        if m:
            raw = m.group(1).strip()
            cur = 'MITM' if raw.lower() == 'mitm' else raw
            out.setdefault(cur, [])
        elif cur is not None and line.strip() and not line.lstrip().startswith('#'):
            out[cur].append(line.strip())
    return out


def iter_aoomee(aoomee_dir):
    """遍历 aoomee/Loon-Adblock-Plugins，产出 (文件名, 归一化段dict)。
    兼容传入仓库根目录（含 plugins/）或直接传入 plugins 目录；
    识别 .plugin/.lpx（均为文本），跳过 .js 等非插件文件。"""
    pdir = os.path.join(aoomee_dir, 'plugins')
    if not os.path.isdir(pdir):
        pdir = aoomee_dir
    names = sorted(x for x in os.listdir(pdir)
                   if x.endswith('.plugin') or x.endswith('.lpx'))
    for n in names:
        text = open(os.path.join(pdir, n), encoding='utf-8').read()
        yield n, parse_loose_sections(text)


def generic_script_url(line):
    """提取 generic 行的脚本 URL（script-path= 或 script("...")）；非 generic 返回 None。"""
    if not line.strip().startswith('generic'):
        return None
    m = re.search(r'script\("([^"]+)"', line)
    if m:
        return m.group(1)
    m = re.search(r'script-path=([^,]+)', line)
    return m.group(1) if m else None


def is_v2_line(line):
    return bool(re.match(r'^(request|response|generic)\b', line.strip())) and ' then ' in line


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


# ---------------- hostname 守卫反查（通配 TLD 收敛） ----------------
def is_ip_literal_host(host):
    """识别裸 IPv4/IPv6 及明显的 IP 通配形式；接受 MITM 负向前缀和 IPv6 方括号。"""
    candidate = host.strip()
    if candidate.startswith('-'):
        candidate = candidate[1:].strip()
    if candidate.startswith('['):
        closing = candidate.find(']')
        if closing >= 0:
            candidate = candidate[1:closing]
    elif candidate.count(':') == 1:
        # IPv4 URL 可能带端口；只剥离明确的 :数字 后缀。
        address, port = candidate.rsplit(':', 1)
        if port.isdigit():
            candidate = address
    # 有效或格式错误的四段数字地址都不应伪装成域名。
    labels = candidate.split('.')
    if len(labels) == 4 and all(part.isdigit() for part in labels):
        return True
    # 通配 IPv4（例如 10.1.*.*）同样不是 MITM 域名。
    if '.' in candidate and all(ch in '0123456789.*?' for ch in candidate):
        return True
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        return False


def guard_hosts_from_lines(lines):
    """从 Rewrite/Script 守卫提取 Loon 合法 hostname 集合：
    - 完整明确 host：要求 HOST_OK 且最后标签在真实 TLD 白名单；
    - 含通配/OR 的守卫：退化为 *.末尾连续字面标签（只取纯字面标签，不臆造）；
    只取 then/script-path 之前的守卫（排除 jq body 与脚本资源地址）；
    自动排除裸 IP、通配 IP 与仅 http:// 的 host。
    顺序无关：同一 host 只要被任一 https/https? 规则守卫就纳入（即使同时存在纯 http 规则），
    仅被纯 http 规则守卫的 host 不纳入。"""
    https = set()
    for l in lines:
        head = l.split(' then ', 1)[0].split('script-path=', 1)[0]
        clean = head.replace('\\/', '/').replace('\\.', '.')
        for proto, zone in re.findall(r'(https?\??)://([^/\s]+)', clean):
            if proto == 'http':
                # 纯明文 HTTP 不需解密；不参与 https 集合（顺序无关，不污染同 host 的 https 守卫）
                continue
            result = None
            # 1) 完整字面 host
            if HOST_OK.match(zone):
                result = zone
            else:
                # 2) 含通配/OR：取末尾连续纯字面标签，构造 *.后缀
                lit = []
                for lab in reversed(zone.split('.')):
                    if not lab or not re.match(r'^[A-Za-z0-9\-]+$', lab):
                        break
                    lit.append(lab)
                lit = lit[::-1]
                need = 3 if '.'.join(lit[-2:]).lower() in PUBLIC_SUFFIX_2L else 2
                if (len(lit) >= need and not is_public_suffix('.'.join(lit[-need:]))
                        and HOST_OK.match('.'.join(lit))):
                    result = '*.' + '.'.join(lit)
            # HOST_OK 也可能匹配四段数字形式；IP 目标不能进入 MITM 自愈候选。
            if result and not is_ip_literal_host(result):
                https.add(result)
    return https


def host_wildcard_resolve(pattern, guard_hosts):
    """把含通配的 hostname 用标签级通配在守卫真实 host 中反查，返回命中的真实 host。
    * 匹配标签内任意字符（不跨点），? 匹配单个字符；不臆造 TLD。"""
    rx = ''
    for ch in pattern:
        if ch == '*':
            rx += '[^.]*'
        elif ch == '?':
            rx += '[^.]'
        else:
            rx += re.escape(ch)
    r = re.compile('^' + rx + '$', re.IGNORECASE)
    return sorted(h for h in guard_hosts if r.match(h))


# ---------------- blockAdsV2 hostname 收敛 ----------------
def normalize_extra_host(h, guard_hosts=None):
    """hostname -> Loon 合法 hostname 列表；无法安全收敛返回 []。
    保留 - 前缀排除项（对收敛后的主体重新加 -）。
    裸 IP / 通配 IP 丢弃；只接受具体域名与上游明确的标准 *.后缀，
    不做中间通配的整域退化；其余用守卫真实 host 反查、只取具体 host，查不到即丢弃。"""
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
    # 保留原始通配模式（含末尾 TLD 通配），供守卫反查使用
    guard_pat = h
    # 通配 TLD（*.xxx.* / xxx.*）：去掉末尾 .*，尝试字符串收敛
    if h.endswith('.*'):
        h = h[:-2].strip('.')
    # 已知 typo（按完整标签）：souhu -> sohu
    h = re.sub(r'(^|\.)souhu(\.|$)', r'\1sohu\2', h)
    if not h:
        return []

    def has_real_tld(x):
        return bool(HOST_OK.match(x))

    out = []
    # 具体域名
    if '*' not in h and '?' not in h:
        if HOST_OK.match(h) and has_real_tld(h) and not is_public_suffix(h):
            out = [h]
    # 标准 *.后缀（上游明确声明，保留）
    elif h.startswith('*.') and '*' not in h[2:] and '?' not in h[2:]:
        if HOST_OK.match(h[2:]) and has_real_tld(h) and not is_public_suffix(h[2:]):
            out = [h]
    # 中间/前缀通配（m*.amap.com、*-spclient、*default...）：不做整域退化。
    # 整域退化会把窄路径规则扩大成 *.域 强制 MITM，pinning 下会重蹈 amemv 故障，
    # 故统一交给下方守卫反查，只接受真实出现的具体 host。

    # 字符串无法安全收敛（缺 TLD/中间通配）：用守卫真实 host 反查，
    # 只取具体 host（不含通配），不臆造 TLD、不扩大整域；查不到则丢弃。
    if not out and guard_hosts:
        out = [x for x in host_wildcard_resolve(guard_pat, guard_hosts)
               if '*' not in x and '?' not in x]
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


# AND/OR 逻辑规则里的域名类子规则（如 AND,((DOMAIN,pan.baidu.com),(PROTOCOL,QUIC)),REJECT）
_AND_DOMAIN_RE = re.compile(
    r'(?:DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD),([A-Za-z0-9\-\.\*]+)')


def and_rule_domains(line):
    """提取 AND/OR 规则中所有域名类子规则的值（用于判断 base 是否已覆盖其域名维度）"""
    return _AND_DOMAIN_RE.findall(line)



# ============================================================================
# 主流程：统一优先级合并
# 优先级（数字小=高）：高德 App(-1) > zmjde App(0) > qx 单文件 App(1) > aoomee(2) > Thelongdarkorg(3)
#                     > base/R-Store(4) > blockAdsV2(5) > zmjde 通用(6) > MyBlockAds(7)
# 高德 App 独立完整并入、同正则同动作替换其他来源；不同动作作为互补行为保留。
# zmjde App（DiDi/PinDuoDuo/闲鱼/淘宝/什么值得买）完整并入、同正则替换其他来源；
# zmjde 通用（Block_HTTPDNS/BlockAdvertisers/可莉广告过滤器）低于 base，只补 base 没有的。
# ============================================================================
import collections

# ---------------- 读取 base / extra ----------------
base_text = open(args.base, encoding='utf-8').read()
if args.extra == 'fetch':
    try:
        extra_text, used_url, _ = fetch_validated(
            [BLOCKV2_URL] + BLOCKV2_MIRRORS, fetch, validate_blockv2, 'blockAdsV2')
        print('[fetch] 已获取并通过完整性检查 blockAdsV2:', used_url)
    except Exception as e:
        raise SystemExit('blockAdsV2 获取失败: %s' % e)
else:
    # 显式本地输入也用于单元测试/离线调试；远程生产抓取才执行上游体量门禁。
    extra_text = open(args.extra, encoding='utf-8').read()

# ---------------- MyBlockAds：在线抓取，失败回退仓库内置缓存 ----------------
mb_text = None
if args.myblockads == 'fetch':
    try:
        mb_text = fetch(MYBLOCKADS_URL)
        validate_myblockads(mb_text)
        print('[fetch] 已获取并通过完整性检查 MyBlockAds:', MYBLOCKADS_URL)
    except Exception as e:
        print('[fetch] MyBlockAds 在线抓取失败，回退内置缓存:', e, file=sys.stderr)
        if os.path.exists(MYBLOCKADS_CACHE):
            mb_text = open(MYBLOCKADS_CACHE, encoding='utf-8').read()
            validate_myblockads(mb_text)
            print('[fetch] 已使用并通过完整性检查 MyBlockAds 缓存:', MYBLOCKADS_CACHE)
elif args.myblockads != 'none':
    mb_text = open(args.myblockads, encoding='utf-8').read()
if mb_text is None and args.myblockads != 'none':
    raise SystemExit('MyBlockAds 在线来源与本地缓存/文件均不可用，拒绝静默跳过该来源')

_, base_sec = split_sections(base_text)
_, extra_sec = split_sections(extra_text)
amap_sec = parse_loose_sections(open(args.amap, encoding='utf-8').read()) if args.amap else {}
amap_rw = real_lines(amap_sec.get('Rewrite', []))
amap_sc = real_lines(amap_sec.get('Script', []))
amap_rule = real_lines(amap_sec.get('Rule', []))
amap_mitm = []
for l in amap_sec.get('MITM', []):
    if '=' in l:
        amap_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# 将第三方脚本/JQ 依赖纳入仓库本地镜像，避免上游临时不可用或 kelee.one 403。
_AMAP_ASSET_BASE = 'https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/amap/'
if args.amap:
    amap_rw = [l.replace('https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js', _AMAP_ASSET_BASE + 'rucu6_amap.js')
                 .replace('https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/loon_Amap.recommend.jq', _AMAP_ASSET_BASE + 'loon_Amap.recommend.jq')
                 .replace('https://kelee.one/Resource/JQLang/Amap/updatable.jq', _AMAP_ASSET_BASE + 'updatable.jq')
                 .replace('https://kelee.one/Resource/JQLang/Amap/search_poi_detail.jq', _AMAP_ASSET_BASE + 'search_poi_detail.jq')
                 for l in amap_rw]
amap_sc = [l.replace('https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js', _AMAP_ASSET_BASE + 'rucu6_amap.js') for l in amap_sc]

# ---------------- legacy 旧行转换（blockAdsV2 / qx 单文件等复用）----------------
_LEGACY_REJECT = {
    'reject': 'reject(404)', 'reject-200': 'reject(200)',
    'reject-img': 'reject_img(200)', 'reject-dict': 'reject_dict(200)',
    'reject-array': 'reject_array(200)', 'reject-video': 'reject_video(200)',
}


def escape_slash_for_v2(pat):
    """转义正则内部的裸斜杠（/ -> \\/），保留已有转义；确保包进 v2 `/.../` 后能被完整读回。"""
    out, i = [], 0
    while i < len(pat):
        if pat[i] == '\\' and i + 1 < len(pat):
            out.append(pat[i:i + 2]); i += 2
        elif pat[i] == '/':
            out.append('\\/'); i += 1
        else:
            out.append(pat[i]); i += 1
    return ''.join(out)


def convert_legacy_line(line):
    """把 QuanX 旧写法转成 Loon v2；无法安全转换返回 None（丢弃）。"""
    s = line.strip()
    toks = s.split()
    if len(toks) == 2 and toks[1] in _LEGACY_REJECT:
        return ('request if ${url} ~= /%s/ then %s'
                % (escape_slash_for_v2(toks[0]), _LEGACY_REJECT[toks[1]]))
    if s.endswith(' 302') and 'close_ad=' in s:
        m = re.match(r'^(\^.+?)\s+\$1true\$2\s+302$', s)
        if m:
            return ('request if ${url} ~= /%s/ as m then redirect(302, "${m.1}true${m.2}")'
                    % escape_slash_for_v2(m.group(1)))
    m = re.match(r'^(\^.+?)\s+302\s+(\S+)$', s)
    if m and 'zhihu' in s:
        tgt = m.group(2).replace('$1', '${m.1}')
        return ('request if ${url} ~= /%s/ as m then redirect(302, "%s")'
                % (escape_slash_for_v2(m.group(1)), tgt))
    return None


# ---------------- 无 URL 守卫行（generic / cron）识别 ----------------
def unguarded_key(line):
    g = generic_script_url(line)
    if g is not None:
        return ('generic', g)
    st = line.strip()
    if re.match(r'^cron\b', st):
        m = re.search(r'script-path=([^,]+)', st) or re.search(r'script\("([^"]+)"', st)
        return ('cron', m.group(1) if m else st)
    return None


# ---------------- 动作签名：保留 reject 的不同响应类型，互补动作并存 ----------------
def split_action(line):
    """返回 (v2/v1, 动作部分)。v2 取 then 之后；v1 去掉首段正则。"""
    s = line.strip()
    if re.match(r'^(request|response)\b', s) and ' then ' in s:
        return 'v2', s.split(' then ', 1)[1].strip()
    head = s.split(None, 1)[0]
    return 'v1', s[len(head):].strip()


def action_key(line):
    """规范化旧版/新版拒绝动作别名；不同响应类型和状态码保持不同签名。"""
    _, action = split_action(line)
    aliases = {
        'reject': 'reject(404)',
        'reject-200': 'reject(200)',
        'reject-img': 'reject_img(200)',
        'reject-dict': 'reject_dict(200)',
        'reject-array': 'reject_array(200)',
        'reject-video': 'reject_video(200)',
    }
    action = aliases.get(action, action)
    name = re.split(r'[\s(]', action, 1)[0].lower()
    if name in ('reject', 'reject_img', 'reject_dict', 'reject_array', 'reject_video'):
        return ('REJECT', name, action)
    return (name, action)


# ---------------- 统一优先级合并器 ----------------
def priority_merge(feeds):
    """feeds: 按【输出位置顺序】喂入的 (prio, 行列表)。
    去重单元 = (正则, 动作签名)：同单元取 prio 最小（同级 v2 优先）；
    同正则不同动作（互补）各自保留；新单元按首次出现定位；
    generic/cron 无守卫行按 (类型,脚本URL) 去重单独返回。"""
    units, uprio, order, unguarded = {}, {}, [], {}
    for prio, lines in feeds:
        for l in lines:
            uk = unguarded_key(l)
            if uk is not None:
                old = unguarded.get(uk)
                if old is None or (is_v2_line(l) and not is_v2_line(old)):
                    unguarded[uk] = l
                continue
            r = entry_regex(l)
            if not r:
                continue
            key = (r, action_key(l))
            if key in units:
                if (prio < uprio[key]
                        or (prio == uprio[key] and is_v2_line(l) and not is_v2_line(units[key]))):
                    units[key], uprio[key] = l, prio
            else:
                units[key], uprio[key] = l, prio
                order.append(key)
    return [units[k] for k in order], list(unguarded.values())


def prep_block_lines(ls):
    """blockAdsV2：v2 直接收，旧行走 convert_legacy_line。"""
    out = []
    for l in real_lines(ls):
        if re.match(r'^(request|response)\b', l.strip()):
            out.append(l)
        else:
            c = convert_legacy_line(l)
            if c:
                out.append(c)
    return out


def prep_block_sections(rewrite_lines, script_lines):
    """按 Loon 官方区块语义整理 blockAdsV2。
    上游偶尔把 reject 等 Rewrite Action 放进 [Script]；这类行应移到 [Rewrite]，
    不能生成无 script(...) Action 的 Script 指令。旧版 script-path 行仍留在 [Script]。
    """
    rewrite = prep_block_lines(rewrite_lines)
    script = []
    for line in real_lines(script_lines):
        is_http = bool(re.match(r'^(request|response)\b', line)
                       and ' then ' in line)
        has_script = bool(re.search(r'\bscript\s*\(', line, re.I)
                          or re.search(r'\bscript-path\s*=', line, re.I))
        is_legacy_http_script = bool(
            re.match(r'^(http-request|http-response)\b', line)
            and re.search(r'\bscript-path\s*=', line, re.I))
        is_unguarded_script = bool(
            re.match(r'^(cron|network-changed|generic)\b', line)
            and has_script)
        if (is_http and has_script) or is_legacy_http_script or is_unguarded_script:
            script.append(line)
        elif is_http:
            rewrite.append(line)
        else:
            converted = convert_legacy_line(line)
            if converted:
                rewrite.append(converted)
    return rewrite, script


# 起点读书 magev6 主机：点号必须按 DNS 标签分隔符精确匹配。
_QIDIAN_MAGEV6_PATHS = (
    '/argus/api/v1/client/iosad',
    '/argus/api/v1/bookshelf/getad',
    '/argus/api/v4/client/getsplashscreen',
)


def escape_qidian_magev6_host(rewrite_lines, source):
    """只修正已知起点广告接口 matcher 中未转义的域名点号。"""
    output = []
    adjustments = []
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\/', '/') if matcher else matcher
        if not matcher or 'magev6' not in normalized or '/argus/api/' not in normalized:
            output.append(line)
            continue
        raw_host = 'magev6.if.qidian.com'
        escaped_host = r'magev6\.if\.qidian\.com'
        if escaped_host in normalized:
            output.append(line)
            continue
        raw_prefix = '^https?://' + raw_host
        if not normalized.startswith(raw_prefix):
            raise RuntimeError(
                source + ' 起点读书 magev6 广告 matcher 已变化，拒绝静默放宽主机匹配：' + line
            )
        path = normalized[len(raw_prefix):]
        if not any(path.startswith(target) for target in _QIDIAN_MAGEV6_PATHS):
            raise RuntimeError(
                source + ' 起点读书 magev6 广告路径已变化，拒绝自动改写：' + line
            )
        if action_key(line) != ('REJECT', 'reject', 'reject(404)'):
            raise RuntimeError(
                source + ' 起点读书 magev6 广告动作已变化，拒绝自动改写：' + line
            )
        updated = line.replace(raw_host, escaped_host, 1)
        updated_matcher = entry_regex(updated)
        updated_normalized = updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        if updated_normalized != normalized.replace(raw_host, escaped_host, 1):
            raise RuntimeError(source + ' 起点读书 magev6 matcher 修正后语义校验失败：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': 'Escape the literal dots in the declared magev6.if.qidian.com hostname so the matcher cannot accept lookalike hosts.',
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    return output, adjustments


_G1_163_MADFEEDBACK_HOST = 'g1.163.com'
_G1_163_MADFEEDBACK_PREFIX = '^https?://' + _G1_163_MADFEEDBACK_HOST + '/madfeedback'


_TARGETED_AD_HOST_MATCHERS = (
    {
        'host': 'dili.sqcosmos.com',
        'marker': '/jiekou/endpage/ad',
        'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'),
        'reason': 'Escape literal dots in the dili.sqcosmos.com end-page ad endpoint matcher.',
    },
    {
        'host': 'api.xiaoyi.com',
        'marker': '/v5/app/mobile/ads',
        'action_key': ('REJECT', 'reject', 'reject(404)'),
        'reason': 'Escape literal dots in the api.xiaoyi.com mobile ads endpoint matcher.',
    },
)


def escape_targeted_ad_hosts(rewrite_lines, source):
    """只收紧已确认广告接口的字面主机名点号，不改变路径与拦截动作。"""
    output = []
    adjustments = []
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\/', '/') if matcher else matcher
        updated_line = line
        for spec in _TARGETED_AD_HOST_MATCHERS:
            host = spec['host']
            escaped_host = host.replace('.', r'\.')
            if not normalized or spec['marker'] not in normalized:
                continue
            if escaped_host in normalized:
                continue
            if host not in normalized:
                raise RuntimeError(
                    source + ' 广告接口主机 matcher 已变化，拒绝自动改写：' + line
                )
            if action_key(line) != spec['action_key']:
                raise RuntimeError(
                    source + ' 广告接口拦截动作已变化，拒绝自动改写：' + line
                )
            updated_line = updated_line.replace(host, escaped_host, 1)
            updated_matcher = entry_regex(updated_line)
            updated_normalized = (
                updated_matcher.replace(r'\/', '/')
                if updated_matcher else updated_matcher
            )
            expected = normalized.replace(host, escaped_host, 1)
            if updated_normalized != expected:
                raise RuntimeError(
                    source + ' 广告接口 matcher 修正后语义校验失败：' + line
                )
            adjustments.append({
                'source': source,
                'section': 'Rewrite',
                'reason': spec['reason'] + ' This prevents lookalike hosts from being rejected.',
                'original_line': line,
                'output_line': updated_line,
            })
            normalized = updated_normalized
        output.append(updated_line)
    return output, adjustments


def narrow_gamersky_list_response_host(rewrite_lines, source):
    """将游民星空列表广告响应过滤限制到合法子域名与明确接口路径。"""
    output = []
    adjustments = []
    jq_action = (
        'then response.json.jq(' + chr(96)
        + '.listElements |= map(select(has("adCategory") | not))'
        + chr(96) + ')'
    )
    original = (
        r'response if ${url} ~= /http:\/\/.+\.gamersky.com\/.+\/lists\/getListElements/ '
        + jq_action
    )
    narrowed = (
        r'response if ${url} ~= /^http:\/\/(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}'
        r'[A-Za-z0-9])?\.)+gamersky\.com\/.+\/lists\/getListElements(?:\/|\?|#|$)/ '
        + jq_action
    )
    for line in rewrite_lines:
        if 'gamersky' not in line or 'getListElements' not in line:
            output.append(line)
            continue
        if line != original:
            raise RuntimeError(
                source + ' 游民星空列表广告响应规则范围或过滤动作已变化，拒绝自动改写：' + line
            )
        updated_matcher = entry_regex(narrowed)
        updated_normalized = updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        expected = (
            r'^http://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'
            r'gamersky\.com/.+/lists/getListElements(?:/|\?|#|$)'
        )
        if updated_normalized != expected:
            raise RuntimeError(source + ' 游民星空列表广告响应 matcher 收敛后校验失败：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': (
                'Constrain the Gamersky list-ad response filter to valid declared subdomains, '
                'a literal gamersky.com suffix, and the explicit getListElements endpoint; '
                'preserve the original HTTP scheme and JSON adCategory filter.'
            ),
            'original_line': line,
            'output_line': narrowed,
        })
        output.append(narrowed)
    return output, adjustments


def narrow_baidunetdisk_cdn_subdomains(rewrite_lines, source):
    """将百度网盘广告图片 CDN 兜底规则限制到 MITM 声明的合法子域名。"""
    output = []
    adjustments = []
    targets = {
        r'^https://.*\.vlion\.cn/.+ reject-200':
            r'^https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+vlion\.cn/.+ reject-200',
        r'^https://.*\.advlion\.com/.+ reject-200':
            r'^https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+advlion\.com/.+ reject-200',
    }
    for original, narrowed in targets.items():
        candidates = [
            line for line in rewrite_lines
            if (r'.*\.vlion\.cn/.+' in line if 'advlion' not in original
                else r'.*\.advlion\.com/.+' in line)
        ]
        if len(candidates) != 1 or candidates[0] != original:
            raise RuntimeError(
                source + ' 百度网盘 CDN 子域名规则范围或动作已变化，拒绝自动改写：'
                + repr(candidates)
            )
        matcher = entry_regex(narrowed)
        expected = (
            r'^https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'
            + (r'vlion\.cn/.+' if 'advlion' not in original else r'advlion\.com/.+')
        )
        if matcher != expected:
            raise RuntimeError(source + ' 百度网盘 CDN 子域名 matcher 校验失败：' + original)
    for line in rewrite_lines:
        if line in targets:
            narrowed = targets[line]
            adjustments.append({
                'source': source,
                'source_file': 'baidunetdisk_splash_ad_block.plugin',
                'section': 'Rewrite',
                'reason': (
                    'Constrain the Baidu Netdisk CDN image fallback to syntactically valid '
                    'subdomains of the already-declared *.vlion.cn / *.advlion.com MITM hosts; '
                    'preserve HTTPS, the image-path pattern, and reject-200.'
                ),
                'original_line': line,
                'output_line': narrowed,
            })
            output.append(narrowed)
        else:
            output.append(line)
    return output, adjustments


def add_baidunetdisk_advlion_quic_rule(rule_lines, mitm_lines, source):
    """补齐百度网盘 *.advlion.com MITM 主机对应的 QUIC 拦截，保留既有 .cn 规则。"""
    expected_cn = "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT"
    expected_com = "AND,((DOMAIN-SUFFIX,advlion.com),(PROTOCOL,QUIC)),REJECT"
    mitm_hosts = []
    for line in mitm_lines:
        if '=' in line:
            mitm_hosts.extend(
                host.strip().lower()
                for host in line.split('=', 1)[1].split(',')
                if host.strip()
            )
    if '*.advlion.com' not in mitm_hosts:
        raise RuntimeError(
            source + ' 百度网盘 advlion.com QUIC 补齐守卫缺少对应 MITM 声明，拒绝自动添加'
        )

    cn_candidates = [
        line for line in rule_lines
        if 'advlion.cn' in line.lower() and 'protocol' in line.lower()
    ]
    com_candidates = [
        line for line in rule_lines
        if 'advlion.com' in line.lower() and 'protocol' in line.lower()
    ]
    if len(cn_candidates) > 1 or any(line != expected_cn for line in cn_candidates):
        raise RuntimeError(
            source + ' 百度网盘 advlion.cn QUIC 规则范围或动作已变化，拒绝自动补齐：'
            + repr(cn_candidates)
        )
    if len(com_candidates) > 1 or any(line != expected_com for line in com_candidates):
        raise RuntimeError(
            source + ' 百度网盘 advlion.com QUIC 规则范围或动作已变化，拒绝自动补齐：'
            + repr(com_candidates)
        )
    if com_candidates:
        return list(rule_lines), [], []

    if len(cn_candidates) != 1:
        raise RuntimeError(
            source + ' 百度网盘 QUIC 配套规则基线已变化，拒绝猜测补齐：'
            + repr(cn_candidates)
        )
    adjustment = {
        'source': source,
        'source_file': 'baidunetdisk_splash_ad_block.plugin',
        'section': 'Rule',
        'change_type': 'add_missing_quic_coverage',
        'reason': (
            'The upstream Baidu Netdisk plugin declares *.advlion.com in MITM and '
            'uses advlion.com for its ad-image fallback, but its QUIC companion rule '
            'covers advlion.cn instead. Add the matching advlion.com QUIC REJECT while '
            'preserving the separate existing advlion.cn rule.'
        ),
        'related_existing_rule': expected_cn,
        'mitm_host': '*.advlion.com',
        'output_line': expected_com,
    }
    return list(rule_lines), [expected_com], [adjustment]


def narrow_baidunetdisk_ad_image_host(rewrite_lines, source):
    """将百度网盘广告图兜底规则限制到插件实际声明 MITM 的 pan.baidu.com。"""
    output = []
    adjustments = []
    original = r'^https://.*\.baidu\.com.*ad/.* reject-200'
    narrowed = r'^https://pan\.baidu\.com/.*ad/.* reject-200'
    candidates = [
        line for line in rewrite_lines
        if r'.*\.baidu\.com.*ad/.*' in line
    ]
    if len(candidates) != 1 or candidates[0] != original:
        raise RuntimeError(
            source + ' 百度网盘广告图 CDN 规则数量、范围或动作已变化，拒绝自动改写：'
            + repr(candidates)
        )
    for line in rewrite_lines:
        if line != original:
            output.append(line)
            continue
        matcher = entry_regex(narrowed)
        if matcher != r'^https://pan\.baidu\.com/.*ad/.*':
            raise RuntimeError(source + ' 百度网盘广告图 CDN 主机收敛后校验失败：' + line)
        adjustments.append({
            'source': source,
            'source_file': 'baidunetdisk_splash_ad_block.plugin',
            'section': 'Rewrite',
            'reason': (
                'The upstream Baidu Netdisk plugin declares only pan.baidu.com in MITM; '
                'limit this broad Baidu ad-image fallback matcher to that actual decrypted host '
                'while preserving its HTTPS path pattern and reject-200 action.'
            ),
            'original_line': line,
            'output_line': narrowed,
        })
        output.append(narrowed)
    return output, adjustments


def narrow_gamersky_statistic_ad_host(rewrite_lines, source):
    """将游民星空 statisticAd 规则锚定到合法子域名与明确接口路径。"""
    output = []
    adjustments = []
    original = (
        r"request if ${url} ~= /https:\/\/.+\.gamersky.com\/v1\/statisticAd/"
        r" then reject_dict(200)"
    )
    narrowed = (
        r"request if ${url} ~= /^https:\/\/(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
        r"[A-Za-z0-9])?\.)+gamersky\.com\/v1\/statisticAd(?:\/|\?|#|$)/"
        r" then reject_dict(200)"
    )
    for line in rewrite_lines:
        if 'gamersky' not in line or 'statisticAd' not in line:
            output.append(line)
            continue
        if line != original or action_key(line) != ('REJECT', 'reject_dict', 'reject_dict(200)'):
            raise RuntimeError(
                source + ' 游民星空 statisticAd 广告规则范围或动作已变化，拒绝自动改写：' + line
            )
        updated_matcher = entry_regex(narrowed)
        updated_normalized = updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        expected = (
            r'^https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+'
            r'gamersky\.com/v1/statisticAd(?:/|\?|#|$)'
        )
        if updated_normalized != expected:
            raise RuntimeError(source + ' 游民星空 statisticAd 正则收敛后校验失败：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': (
                'Anchor the Gamersky statisticAd matcher and constrain its host/path boundary; '
                'preserve HTTPS and reject only the explicit ad-statistics endpoint under valid declared subdomains.'
            ),
            'original_line': line,
            'output_line': narrowed,
        })
        output.append(narrowed)
    return output, adjustments


def narrow_gamersky_ad_system_host(rewrite_lines, source):
    """将游民星空广告接口限制为合法的 gamersky.com 子域名，不改变路径与动作。"""
    output = []
    adjustments = []
    original = (
        r"request if ${url} ~= /^http:\/\/.+\.gamersky\.com\/.+"
        r"\/adSystem\/ad\/.+/ then reject_dict(200)"
    )
    narrowed = (
        r"request if ${url} ~= /^http:\/\/(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
        r"[A-Za-z0-9])?\.)+gamersky\.com\/.+\/adSystem\/ad\/.+/"
        r" then reject_dict(200)"
    )
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\/', '/') if matcher else matcher
        if not normalized or 'gamersky' not in normalized or '/adSystem/ad/' not in normalized:
            output.append(line)
            continue
        if line != original or action_key(line) != ('REJECT', 'reject_dict', 'reject_dict(200)'):
            raise RuntimeError(
                source + ' 游民星空 adSystem 广告规则范围或动作已变化，拒绝自动改写：' + line
            )
        updated_matcher = entry_regex(narrowed)
        updated_normalized = updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        expected = normalized.replace(
            r'.+\.gamersky\.com',
            r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+gamersky\.com',
            1,
        )
        if updated_normalized != expected:
            raise RuntimeError(source + ' 游民星空广告主机收紧后语义校验失败：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': (
                'Constrain the Gamersky adSystem endpoint to syntactically valid '
                'subdomains of the declared *.gamersky.com MITM scope, while preserving '
                'the HTTP scheme, ad path, and reject_dict(200) action.'
            ),
            'original_line': line,
            'output_line': narrowed,
        })
        output.append(narrowed)
    return output, adjustments


def escape_adstatic_peopleapp_image_extension(rewrite_lines, source):
    """将 PeopleApp 开屏广告图片扩展名分隔点收紧为字面点，不改变文件类型与动作。"""
    output = []
    adjustments = []
    host_prefix = r'^https?://adstatic\.peopleapp\.com/upload/AppLoad/'
    variants = (
        ('.*.(?:jpg|png)', r'.*\.(?:jpg|png)'),
        ('.*.(jpg|png)', r'.*\.(jpg|png)'),
    )
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\/', '/') if matcher else matcher
        if not normalized or '/upload/AppLoad/' not in normalized:
            output.append(line)
            continue
        if r'adstatic\.peopleapp\.com' not in normalized:
            if 'adstatic.peopleapp.com' in normalized:
                raise RuntimeError(
                    source + ' PeopleApp 图片广告主机 matcher 已变化，拒绝自动改写：' + line
                )
            output.append(line)
            continue
        if not normalized.startswith(host_prefix):
            raise RuntimeError(
                source + ' PeopleApp 图片广告主机/路径范围已变化，拒绝自动改写：' + line
            )
        if action_key(line) != ('REJECT', 'reject', 'reject(200)'):
            raise RuntimeError(
                source + ' PeopleApp 图片广告拦截动作已变化，拒绝自动改写：' + line
            )
        matched_variant = next(
            ((raw, escaped) for raw, escaped in variants if raw in normalized),
            None,
        )
        if matched_variant is None:
            if any(escaped in normalized for _, escaped in variants):
                output.append(line)
                continue
            raise RuntimeError(
                source + ' PeopleApp 图片广告扩展名 matcher 已变化，拒绝自动改写：' + line
            )
        raw, escaped = matched_variant
        updated = line.replace(raw, escaped, 1)
        updated_matcher = entry_regex(updated)
        updated_normalized = (
            updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        )
        expected = normalized.replace(raw, escaped, 1)
        if updated_normalized != expected:
            raise RuntimeError(
                source + ' PeopleApp 图片广告 matcher 修正后语义校验失败：' + line
            )
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': (
                'Escape the literal file-extension dot in the PeopleApp AppLoad '
                'ad-image matcher so non-image suffix lookalikes are not rejected.'
            ),
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    return output, adjustments


_AD_IMAGE_EXTENSION_TARGETS = (
    {
        'name': '叮嗒出行 admobile 广告图片',
        'prefix': r'^https?://img\\.admobile\\.top/admobile-adRequest/',
    },
    {
        'name': '加油广东广告图片',
        'prefix': r'^https?://img\\.gdoil\\.cn/upload/ad/',
    },
    {
        'name': '悟空遥控器 AD/iOS 图片',
        'prefix': r'^https?://img\\.wukongtv\\.com/wkremote/AD/iOS/',
    },
    {
        'name': '杭州市民广告投放素材',
        'prefix': r'^https?://ads\\.iconntech\\.com/resource-delivery',
    },
    {
        'name': '优理宝开屏图片',
        'prefix': r'^https?://static\\.xyzq\\.cn/image/splash/opera3',
    },
    {
        'name': '广发银行 advertising/accurate 图片素材',
        'prefix': r'^https?://static\\.95508\\.com/icppweb/images/modelMaterial/',
    },
    {
        'name': '返利网开屏图片',
        'prefix': r'^https?://l[0-9]{1}\\.51fanli\\.net/app/images/splash/2022/',
    },
)
_AD_IMAGE_EXTENSION_VARIANTS = (
    ('.*.(?:jpg|png)', r'.*\\.(?:jpg|png)'),
    ('.*.(png|jpg)', r'.*\\.(png|jpg)'),
    ('.*.(jpg|png)', r'.*\\.(jpg|png)'),
    ('.*.(jpg|png|jpeg)', r'.*\\.(jpg|png|jpeg)'),
    ('.*.jpg', r'.*\\.jpg'),
)


def escape_known_ad_image_extension_delimiters(rewrite_lines, source):
    """只转义已核实广告/开屏图片路径中，文件扩展名前的字面点。"""
    output = []
    adjustments = []
    expected_action = ('REJECT', 'reject', 'reject(200)')
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\\/', '/') if matcher else matcher
        target = next(
            (item for item in _AD_IMAGE_EXTENSION_TARGETS
             if normalized and normalized.startswith(item['prefix'])),
            None,
        )
        if target is None:
            output.append(line)
            continue
        if action_key(line) != expected_action:
            raise RuntimeError(
                source + ' ' + target['name'] + ' 图片规则动作已变化，拒绝自动改写：' + line
            )
        raw_variants = [
            (raw, escaped) for raw, escaped in _AD_IMAGE_EXTENSION_VARIANTS
            if raw in normalized
        ]
        escaped_variants = [
            escaped for _, escaped in _AD_IMAGE_EXTENSION_VARIANTS
            if escaped in normalized
        ]
        if len(raw_variants) == 1 and not escaped_variants:
            raw, escaped = raw_variants[0]
            updated = line.replace(raw, escaped, 1)
            updated_matcher = entry_regex(updated)
            updated_normalized = (
                updated_matcher.replace(r'\\/', '/') if updated_matcher else updated_matcher
            )
            if updated_normalized != normalized.replace(raw, escaped, 1):
                raise RuntimeError(
                    source + ' ' + target['name'] + ' 图片扩展名 matcher 修正后语义校验失败：'
                    + line
                )
            adjustments.append({
                'source': source,
                'section': 'Rewrite',
                'target': target['name'],
                'reason': (
                    'Escape only the literal dot immediately before the image extension; '
                    'keep the original host, path, extension allowlist, and reject(200) action.'
                ),
                'original_line': line,
                'output_line': updated,
            })
            output.append(updated)
        elif not raw_variants and len(escaped_variants) == 1:
            output.append(line)
        else:
            raise RuntimeError(
                source + ' ' + target['name'] + ' 图片扩展名 matcher 已变化，拒绝自动改写：'
                + line
            )
    return output, adjustments


def escape_g1_163_madfeedback_host(rewrite_lines, source):
    """只转义网易 g1.163.com 广告反馈接口的字面主机名点号。"""
    output = []
    adjustments = []
    for line in rewrite_lines:
        matcher = entry_regex(line)
        normalized = matcher.replace(r'\/', '/') if matcher else matcher
        if not matcher or not normalized.startswith(_G1_163_MADFEEDBACK_PREFIX):
            output.append(line)
            continue
        if r'g1\.163\.com' in normalized:
            output.append(line)
            continue
        if action_key(line)[0] != 'REJECT':
            raise RuntimeError(
                source + ' 网易 g1.163.com matcher 动作已变化，拒绝自动改写：' + line
            )
        updated = line.replace(_G1_163_MADFEEDBACK_HOST, r'g1\.163\.com', 1)
        updated_matcher = entry_regex(updated)
        updated_normalized = updated_matcher.replace(r'\/', '/') if updated_matcher else updated_matcher
        if updated_normalized != normalized.replace(
                _G1_163_MADFEEDBACK_HOST, r'g1\.163\.com', 1):
            raise RuntimeError(source + ' 网易 g1.163.com matcher 修正后语义校验失败：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': 'Escape literal dots in g1.163.com so the ad-feedback matcher cannot match lookalike hosts.',
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    return output, adjustments


# 懒人听书：只允许上游该接口明确声明的两个业务主机。
_LANRENTINGSHU_MARKER = '# > 懒人听书'
_LANRENTINGSHU_HOST_DECLARATION = (
    '# hostname = 118.178.214.118, dapis.mting.info, display.wting.info'
)
_LANRENTINGSHU_GENERIC = (
    r'https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action'
)
_LANRENTINGSHU_SCOPED = (
    r'https?:\/\/(?:118\.178\.214\.118|dapis\.mting\.info)'
    r'\/yyting\/advertclient\/ClientAdvertList.action'
)


def validate_lanrentingshu_source(source_text):
    """若上游包含懒人听书区块，确认接口主机声明与宽泛规则未漂移。"""
    marker_index = source_text.find(_LANRENTINGSHU_MARKER)
    if marker_index < 0:
        return False
    next_app = re.search(
        r'(?m)^#\s*>\s*',
        source_text[marker_index + len(_LANRENTINGSHU_MARKER):],
    )
    section_end = (
        marker_index + len(_LANRENTINGSHU_MARKER) + next_app.start()
        if next_app else len(source_text)
    )
    section = source_text[marker_index:section_end]
    if _LANRENTINGSHU_HOST_DECLARATION not in section:
        raise RuntimeError(
            '懒人听书上游 hostname 声明已变化，停止构建并要求复核'
        )
    if (_LANRENTINGSHU_GENERIC not in section
            or 'reject(404)' not in section):
        raise RuntimeError(
            '懒人听书 ClientAdvertList 上游 matcher/action 已变化，'
            '停止构建并要求复核'
        )
    return True


def narrow_lanrentingshu_base_scope(rewrite_lines, source_present):
    """将 R-Store 转换产物中的同接口旧式全主机规则限制到已核实的业务主机。"""
    if not source_present:
        return rewrite_lines, []
    generic = _LANRENTINGSHU_GENERIC
    scoped = _LANRENTINGSHU_SCOPED
    adjustments = []
    output = []
    for line in rewrite_lines:
        is_target = (
            'ClientAdvertList.action' in line
            and line.endswith(' reject')
        )
        if not is_target:
            output.append(line)
            continue
        if scoped in line:
            output.append(line)
            continue
        if generic not in line:
            raise RuntimeError(
                'R-Store 懒人听书 ClientAdvertList matcher 已变化，'
                '拒绝静默保留未知主机范围：' + line
            )
        updated = line.replace(generic, scoped, 1)
        adjustments.append({
            'source': 'base',
            'section': 'Rewrite',
            'reason': 'Narrow the legacy R-Store ClientAdvertList matcher to the two business hosts corroborated by the dedicated blockAdsV2 hostname declaration',
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    return output, adjustments


def narrow_lanrentingshu_scope(rewrite_lines, source_present):
    """将懒人听书 ClientAdvertList 的全主机匹配限制到上游声明的两个主机。"""
    if not source_present:
        return rewrite_lines, []
    adjustments = []
    output = []
    for line in rewrite_lines:
        is_target = (
            '/yyting\\/advertclient\\/ClientAdvertList.action' in line
            and 'reject(404)' in line
        )
        if not is_target:
            output.append(line)
            continue
        if _LANRENTINGSHU_SCOPED in line:
            output.append(line)
            continue
        if _LANRENTINGSHU_GENERIC not in line:
            raise RuntimeError(
                '懒人听书 ClientAdvertList matcher 已变化，拒绝静默跳过域名收敛：'
                + line
            )
        updated = line.replace(
            _LANRENTINGSHU_GENERIC, _LANRENTINGSHU_SCOPED, 1
        )
        adjustments.append({
            'source': 'block',
            'section': 'Rewrite',
            'reason': 'Narrow 懒人听书 ClientAdvertList to its two explicitly declared hosts',
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    if not adjustments:
        raise RuntimeError(
            '检测到懒人听书上游区块，但未找到待收敛的 ClientAdvertList 规则'
        )
    return output, adjustments


# QQ音乐开屏素材：仅允许专用插件 MITM 声明的两个 HTTPS 主机。
_QQMUSIC_MARKER = '# > QQ音乐'
_QQMUSIC_BLOCK_HOST_DECLARATION = (
    '# hostname = us.l.qq.com, y.gtimg.cn, music.y.qq.com'
)
_QQMUSIC_BLOCK_GENERIC = (
    r'https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/'
)
_QQMUSIC_BLOCK_SCOPED = (
    r'https?:\/\/(?:y\.gtimg\.cn|music\.y\.qq\.com)'
    r'\/music\/common\/upload\/t_splash_info\/'
)
_QQMUSIC_THELONG_GENERIC = _QQMUSIC_BLOCK_GENERIC
_QQMUSIC_THELONG_SCOPED = _QQMUSIC_BLOCK_SCOPED
_QQMUSIC_THELONG_MITM = 'hostname = y.gtimg.cn, music.y.qq.com'


def validate_qqmusic_sources(block_text, thelong_text=None):
    """核实两个上游 QQ音乐区块中的 matcher、hostname 与 MITM 声明。"""
    marker_positions = [
        match.start()
        for match in re.finditer(re.escape(_QQMUSIC_MARKER), block_text)
    ]
    if not marker_positions:
        return False, False

    block_section = None
    for marker_index in marker_positions:
        next_app = re.search(
            r'(?m)^# > (?!>)[^\r\n]*',
            block_text[marker_index + len(_QQMUSIC_MARKER):],
        )
        section_end = (
            marker_index + len(_QQMUSIC_MARKER) + next_app.start()
            if next_app else len(block_text)
        )
        candidate = block_text[marker_index:section_end]
        if (_QQMUSIC_BLOCK_HOST_DECLARATION in candidate
                and _QQMUSIC_BLOCK_GENERIC in candidate
                and r'y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\/' in candidate
                and 'reject' in candidate):
            block_section = candidate
            break

    if block_section is None:
        raise RuntimeError(
            'QQ音乐 blockAdsV2 hostname/matcher/action 已变化，停止构建并要求复核'
        )

    if thelong_text is None:
        return True, False
    mitm_section = thelong_text.split('[MITM]', 1)
    if (len(mitm_section) != 2
            or _QQMUSIC_THELONG_MITM not in mitm_section[1]
            or _QQMUSIC_THELONG_GENERIC not in thelong_text
            or r'y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\/' not in thelong_text
            or '该主机需在 MITM 列表内才会生效' not in thelong_text
            or 'reject' not in thelong_text):
        raise RuntimeError(
            'Thelong QQ音乐 MITM/备用 CDN 规则声明已变化，停止构建并要求复核'
        )
    return True, True


def narrow_qqmusic_scope(rewrite_lines, source):
    """将 QQ音乐备用 CDN 的全主机 matcher 收敛到其专用 MITM 主机。"""
    generic = (_QQMUSIC_BLOCK_GENERIC if source == 'block'
               else _QQMUSIC_THELONG_GENERIC)
    scoped = (_QQMUSIC_BLOCK_SCOPED if source == 'block'
              else _QQMUSIC_THELONG_SCOPED)
    output, adjustments = [], []
    for line in rewrite_lines:
        is_target = 't_splash_info' in line and 'reject' in line and generic in line
        if not is_target:
            output.append(line)
            continue
        if scoped in line:
            output.append(line)
            continue
        updated = line.replace(generic, scoped, 1)
        if updated == line:
            raise RuntimeError('QQ音乐宽泛 t_splash_info matcher 无法安全收敛：' + line)
        adjustments.append({
            'source': source,
            'section': 'Rewrite',
            'reason': 'Limit fallback CDN matcher to y.gtimg.cn and music.y.qq.com, the two hosts explicitly declared by the dedicated QQ音乐 MITM source; retain the separate IPv4 rule',
            'original_line': line,
            'output_line': updated,
        })
        output.append(updated)
    if not adjustments:
        raise RuntimeError('QQ音乐来源存在但未找到待收敛的备用 CDN matcher')
    return output, adjustments


# 555影视：上游明确声明的业务主机范围。通配项只匹配子域，不包含根域。
_555_GENERIC_HOST = r'[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+){1,3}(:\d+)?'
_555_SCOPED_HOST = (
    r'(?:vip7\.fzwdyy\.cn|(?:[A-Za-z0-9-]+\.)+qyfxgd\.cn|'
    r'(?:[A-Za-z0-9-]+\.)+weilai555\.com|'
    r'(?:[A-Za-z0-9-]+\.)+ecoliving168\.com)(?::\d+)?'
)


def narrow_555_scope(rewrite_lines, script_lines):
    """将 555影视两条泛主机触发器限制到上游声明的四组主机。"""
    adjustments = []

    def narrow(line, section):
        is_555_advert = (
            section == 'Rewrite'
            and r'/api\/v\d\/advert' in line
            and 'reject(404)' in line
        )
        is_555_script = (
            section == 'Script'
            and '555Ad.js' in line
            and r'/api\/v\d\/movie\/index_recommend' in line
        )
        if not (is_555_advert or is_555_script):
            return line
        if _555_SCOPED_HOST in line:
            return line
        if _555_GENERIC_HOST not in line:
            raise RuntimeError(
                '555影视上游 matcher 已变化，拒绝静默跳过域名收敛；'
                '请先人工复核：' + line
            )
        updated = line.replace(_555_GENERIC_HOST, _555_SCOPED_HOST, 1)
        adjustments.append({
            'source': 'block',
            'section': section,
            'reason': 'Narrow generic host matcher to the four hosts declared in the 555影视 source comment',
            'original_line': line,
            'output_line': updated,
        })
        return updated

    return (
        [narrow(line, 'Rewrite') for line in rewrite_lines],
        [narrow(line, 'Script') for line in script_lines],
        adjustments,
    )


# Shadowrocket 风格 "^regex url reject(-dict)"：Loon 旧版无 url 关键字，去掉即可
_SR_URL_RE = re.compile(r'^(\^.*?)\s+url\s+(reject(?:-dict)?)$')
# 旧版动作名大小写归一（官方文档一律小写）
_LEGACY_UPPER = {
    'REJECT': 'reject', 'REJECT-200': 'reject-200', 'REJECT-IMG': 'reject-img',
    'REJECT-DICT': 'reject-dict', 'REJECT-ARRAY': 'reject-array',
    'REJECT-VIDEO': 'reject-video',
}


def convert_shadowrocket_line(line):
    s = line.strip()
    m = _SR_URL_RE.match(s)
    if m:
        s = '%s %s' % (m.group(1), m.group(2))
    toks = s.split()
    if len(toks) >= 2 and toks[1] in _LEGACY_UPPER:
        s = s.replace(toks[1], _LEGACY_UPPER[toks[1]], 1)
    return s


# ---------------- 准备各来源 Rewrite / Script ----------------
# base（R-Store 转换产物，原始写法）
base_rw = real_lines(base_sec.get('Rewrite', []))
base_sc = real_lines(base_sec.get('Script', []))
# The user does not use 涨乐财富通. R-Store labels this exact rule
# under "# > 涨乐财富通 - ZHANGLE"; current provenance shows no other
# Rewrite or Script rule references c.zhangle.com.
_ZHANGLE_UNUSED_RULES = {
    r'^https?://c\.zhangle\.com/pic/mktg/diversity/.+\.jpg$': {'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'), 'action': 'reject-dict(200)', 'label': 'c.zhangle.com splash image'},
    r'^https?://live\.inst-service\.htsc\.com/live': {'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'), 'action': 'reject-dict(200)', 'label': 'live.inst-service.htsc.com Live endpoint'},
    r'^https?://geetest\.htsc\.com:\d+/pre_get_token': {'action_key': ('REJECT', 'reject', 'reject(200)'), 'action': 'reject-200', 'label': 'geetest.htsc.com verification endpoint'},
}
zhangle_rewrite_exclusions = []
_zhangle_rw_kept = []
for _line in base_rw:
    _matcher = entry_regex(_line)
    if _matcher not in _ZHANGLE_UNUSED_RULES:
        _zhangle_rw_kept.append(_line)
        continue
    _spec = _ZHANGLE_UNUSED_RULES[_matcher]
    if action_key(_line) != _spec['action_key']:
        raise RuntimeError('R-Store 涨乐财富通专属规则发生变化，拒绝扩大排除范围：' + _line)
    zhangle_rewrite_exclusions.append({
        'source': 'base', 'source_catalog': 'R-Store / 涨乐财富通 - ZHANGLE',
        'input_line': _line, 'matcher': _matcher, 'action': _spec['action'],
        'reason': 'User confirmed they do not use 涨乐财富通; R-Store places this exact rule in its dedicated ZHANGLE section.',
        'status': 'excluded_unused_app', 'label': _spec['label'],
    })
base_rw = _zhangle_rw_kept
base_rw, g1_163_base_adjustments = escape_g1_163_madfeedback_host(base_rw, 'base')
base_rw, peopleapp_base_adjustments = escape_adstatic_peopleapp_image_extension(
    base_rw, 'base')
base_rw, ad_image_extension_base_adjustments = escape_known_ad_image_extension_delimiters(
    base_rw, 'base')

# Mango TV upstream labels this broad IP/port matcher as "无用请求", not an ad endpoint.
# It can reject the same path on unrelated apps' arbitrary IPv4:five-digit-port hosts.
# Exclude only this exact matcher from both base and block feeds; keep the distinct odin ad APIs.
_MGTV_UNUSED_INDEXES_MATCHER = r'^https?://[\d\.]+:\d{5}/\?cmd=indexes'
mgtv_unused_indexes_rewrite_exclusions = []
_mgtv_base_rw_kept = []
for _base_index, _base_line in enumerate(base_rw):
    if entry_regex(_base_line) == _MGTV_UNUSED_INDEXES_MATCHER:
        mgtv_unused_indexes_rewrite_exclusions.append({
            'source': 'base',
            'source_catalog': 'R-Store converted Rewrite source',
            'source_entry_index': _base_index,
            'input_line': _base_line,
            'matcher': _MGTV_UNUSED_INDEXES_MATCHER,
            'action': split_action(_base_line)[1],
            'reason': (
                'The upstream Mango TV section labels this broad IPv4/five-digit-port '
                'cmd=indexes request as "无用请求", not an ad endpoint. Excluding the '
                'exact matcher avoids rejecting unrelated apps while preserving the '
                'separate Mango TV odin ad/config endpoints.'
            ),
            'status': 'excluded_non_ad_probe',
        })
    else:
        _mgtv_base_rw_kept.append(_base_line)
base_rw = _mgtv_base_rw_kept

# JD Lite 开屏广告：base 的请求阶段 reject 会终止请求，不会产生响应供后续 response Rewrite 修改。
# 仅在该终止请求规则仍存在时，排除 blockAdsV2 / Thelong 的两条不可达响应改写。
_LITE_ADVERTISING_MATCHER = r'^https?://api\.m\.jd\.com/client\.action\?functionId=lite_advertising'
_LITE_ADVERTISING_REQUEST_ACTION = ('REJECT', 'reject', 'reject(404)')
_LITE_ADVERTISING_BLOCK_RESPONSE = (
    r'response if ${url} ~= /^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising/ '
    r'then response.body.replace(/jdLiteAdvertisingVO/, "fmz200")'
)
_LITE_ADVERTISING_THELONG_RESPONSE = (
    r'^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising '
    r'response-body-replace-regex jdLiteAdvertisingVO sooyaaabo'
)
lite_advertising_rewrite_exclusions = []
_lite_advertising_guard_present = any(
    entry_regex(line) == _LITE_ADVERTISING_MATCHER
    and action_key(line) == _LITE_ADVERTISING_REQUEST_ACTION
    for line in base_rw
)

# blockAdsV2
block_rw, block_sc = prep_block_sections(
    extra_sec.get('Rewrite', []), extra_sec.get('Script', []))
block_rw, block_qidian_adjustments = escape_qidian_magev6_host(
    block_rw, 'block')
block_rw, g1_163_block_adjustments = escape_g1_163_madfeedback_host(block_rw, 'block')
block_rw, targeted_ad_host_adjustments = escape_targeted_ad_hosts(
    block_rw, 'block')
block_rw, peopleapp_block_adjustments = escape_adstatic_peopleapp_image_extension(
    block_rw, 'block')
block_rw, ad_image_extension_block_adjustments = escape_known_ad_image_extension_delimiters(
    block_rw, 'block')
block_rw, gamersky_block_adjustments = narrow_gamersky_ad_system_host(
    block_rw, 'block')
block_rw, gamersky_statistic_block_adjustments = narrow_gamersky_statistic_ad_host(
    block_rw, 'block')
block_rw, gamersky_list_block_adjustments = narrow_gamersky_list_response_host(
    block_rw, 'block')
_ZHANGLE_BLOCK_RULES = {
    r'^https?://c\.zhangle\.com/pic/mktg/diversity/.+\.jpg$': (r'request if ${url} ~= /^https?:\/\/c\.zhangle\.com\/pic\/mktg\/diversity\/.+\.jpg$/ then reject_dict(200)', ('REJECT', 'reject_dict', 'reject_dict(200)'), 'reject_dict(200)'),
    r'^https?://live\.inst-service\.htsc\.com/live': (r'request if ${url} ~= /^https?:\/\/live\.inst-service\.htsc\.com\/live/ then reject_dict(200)', ('REJECT', 'reject_dict', 'reject_dict(200)'), 'reject_dict(200)'),
    r'^https?://geetest\.htsc\.com:8888/pre_get_token': (r'request if ${url} ~= /^https?:\/\/geetest\.htsc\.com:8888\/pre_get_token/ then reject(200)', ('REJECT', 'reject', 'reject(200)'), 'reject(200)'),
}
zhangle_block_rewrite_exclusions = []
_zhangle_block_kept = []
for _line in block_rw:
    _matcher = entry_regex(_line)
    if _matcher not in _ZHANGLE_BLOCK_RULES:
        if any(host in _line.lower() for host in ('zhangle.com', 'inst-service.htsc.com', 'geetest.htsc.com')):
            raise RuntimeError('blockAdsV2 涨乐财富通规则发生变化，拒绝扩大排除范围：' + _line)
        _zhangle_block_kept.append(_line)
        continue
    _expected_line, _expected_action, _action_label = _ZHANGLE_BLOCK_RULES[_matcher]
    if _line != _expected_line or action_key(_line) != _expected_action:
        raise RuntimeError('blockAdsV2 涨乐财富通规则发生变化，拒绝扩大排除范围：' + _line)
    zhangle_block_rewrite_exclusions.append({
        'source': 'block', 'source_catalog': 'fmz200/wool_scripts blockAdsV2',
        'input_line': _line, 'matcher': _matcher, 'action': _action_label,
        'reason': 'User confirmed they do not use 涨乐财富通; blockAdsV2 groups this exact rule with the ZHANGLE host set.',
        'status': 'excluded_unused_app',
    })
block_rw = _zhangle_block_kept

_mgtv_block_rw_kept = []
for _block_index, _block_line in enumerate(block_rw):
    if entry_regex(_block_line) == _MGTV_UNUSED_INDEXES_MATCHER:
        _source_line_number = None
        for _line_number, _raw_line in enumerate(extra_text.splitlines(), 1):
            if _raw_line.strip() == _block_line.strip():
                _source_line_number = _line_number
                break
        mgtv_unused_indexes_rewrite_exclusions.append({
            'source': 'block',
            'source_catalog': 'fmz200/wool_scripts blockAdsV2 / 芒果TV',
            'source_entry_index': _block_index,
            'source_line_number': _source_line_number,
            'input_line': _block_line,
            'matcher': _MGTV_UNUSED_INDEXES_MATCHER,
            'action': split_action(_block_line)[1],
            'reason': (
                'The upstream Mango TV section explicitly labels this broad '
                'IPv4/five-digit-port cmd=indexes request as "无用请求", not an ad '
                'endpoint. Excluding the exact matcher avoids rejecting unrelated '
                'apps while preserving the separate Mango TV odin ad/config endpoints.'
            ),
            'status': 'excluded_non_ad_probe',
        })
    else:
        _mgtv_block_rw_kept.append(_block_line)
block_rw = _mgtv_block_rw_kept

if _lite_advertising_guard_present:
    _kept_block_rw = []
    for _line in block_rw:
        if entry_regex(_line) == _LITE_ADVERTISING_MATCHER:
            if _line != _LITE_ADVERTISING_BLOCK_RESPONSE:
                raise RuntimeError('JD Lite 上游响应规则发生变化，拒绝扩大排除范围：' + _line)
            lite_advertising_rewrite_exclusions.append({
                'source': 'block',
                'source_catalog': 'fmz200/wool_scripts blockAdsV2',
                'input_line': _line,
                'matcher': _LITE_ADVERTISING_MATCHER,
                'action': 'response.body.replace(/jdLiteAdvertisingVO/, "fmz200")',
                'reason': 'The retained base request-phase reject terminates this URL before an upstream response exists; this response-body rewrite is unreachable and adds no ad-blocking effect.',
                'status': 'excluded_unreachable_response_rule',
            })
        else:
            _kept_block_rw.append(_line)
    block_rw = _kept_block_rw
block_rw, block_sc, block_scope_adjustments = narrow_555_scope(
    block_rw, block_sc)
block_scope_adjustments.extend(block_qidian_adjustments)
block_scope_adjustments.extend(g1_163_base_adjustments)
block_scope_adjustments.extend(peopleapp_base_adjustments)
block_scope_adjustments.extend(peopleapp_block_adjustments)
block_scope_adjustments.extend(ad_image_extension_base_adjustments)
block_scope_adjustments.extend(ad_image_extension_block_adjustments)
block_scope_adjustments.extend(gamersky_block_adjustments)
block_scope_adjustments.extend(gamersky_statistic_block_adjustments)
block_scope_adjustments.extend(gamersky_list_block_adjustments)
block_scope_adjustments.extend(g1_163_block_adjustments)
block_scope_adjustments.extend(targeted_ad_host_adjustments)
lanrentingshu_source_present = validate_lanrentingshu_source(extra_text)
base_rw, lanrentingshu_base_adjustments = narrow_lanrentingshu_base_scope(
    base_rw, lanrentingshu_source_present)
block_scope_adjustments.extend(lanrentingshu_base_adjustments)
block_rw, lanrentingshu_scope_adjustments = narrow_lanrentingshu_scope(
    block_rw, lanrentingshu_source_present)
block_scope_adjustments.extend(lanrentingshu_scope_adjustments)
qqmusic_block_present, _ = validate_qqmusic_sources(extra_text)
if qqmusic_block_present:
    block_rw, qqmusic_block_adjustments = narrow_qqmusic_scope(block_rw, 'block')
    block_scope_adjustments.extend(qqmusic_block_adjustments)


# Tencent Cloud HTTPDNS safety exclusion:
# Tencent's current HTTP and HTTPS API endpoints are 119.29.29.98 and .99;
# both use the /d API path. The old .29 endpoint was retired.
# The exact broad matcher is not an ad-removal rule: any action on it can break DNS.
# Exclude it independent of action spelling so an upstream action change cannot bypass the guard.
# Official docs: https://cloud.tencent.com/document/product/379/95497
# https://cloud.tencent.com/document/product/379/56885
_BLOCK_HTTPDNS_MATCHER = r'^https?://119\.29\.29\.\d+/d'
block_rewrite_exclusions = []
block_mitm_exclusions = []
_block_rw_kept = []
for _block_index, _block_line in enumerate(block_rw):
    if entry_regex(_block_line) == _BLOCK_HTTPDNS_MATCHER:
        _source_line_number = None
        _section = None
        for _line_number, _raw_line in enumerate(extra_text.splitlines(), 1):
            _section_match = re.match(r'^\[([A-Za-z]+)\]\s*$', _raw_line)
            if _section_match:
                _section = _section_match.group(1)
            elif _section == 'Rewrite' and _raw_line.strip() == _block_line.strip():
                _source_line_number = _line_number
                break
        block_rewrite_exclusions.append({
            'source': 'block',
            'source_catalog': 'fmz200/wool_scripts blockAdsV2',
            'source_entry_index': _block_index,
            'source_line_number': _source_line_number,
            'input_line': _block_line,
            'matcher': _BLOCK_HTTPDNS_MATCHER,
            'action': split_action(_block_line)[1],
            'reason': (
                'Overbroad HTTPDNS path block: matcher catches active Tencent Cloud '
                'HTTPDNS endpoints 119.29.29.98 (HTTP) and 119.29.29.99 (HTTPS); '
                'the legacy 119.29.29.29 endpoint was retired.'
            ),
            'status': 'excluded_safety_guard',
        })
    else:
        _block_rw_kept.append(_block_line)
block_rw = _block_rw_kept
# Only remove source rules whose complete match set is already covered by a retained
# higher-priority rule with the same reject action. These are exact audited cases,
# not a general regex-subsumption heuristic.
_SEMANTIC_DUPLICATE_REWRITE_RULES = {
    'thelong': {
        r'^https?://vv\.video\.qq\.com/(diff|get)vmind': {
            'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'),
            'covered_by': r'^https?://vv\.video\.qq\.com/(?:diff|get)vmind',
            'reason': 'The retained base matcher uses a non-capturing group for the same diff/get paths and the same reject-dict action.',
        },
    },
    'aoomee': {
        r'^https://ssp\.soulapp\.cn/api/q': {
            'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'),
            'covered_by': r'^https?://ssp\.soulapp\.cn/api/q',
            'reason': 'The retained base matcher covers both HTTP and HTTPS for the same path with the same reject-dict action.',
        },
        r'^https?://hweb-manager\.huazhu\.com/notice/getAppPopupNotifyAlert(?:\?.*)?$': {
            'action_key': ('REJECT', 'reject_dict', 'reject_dict(200)'),
            'covered_by': r'^https?://hweb-manager\.huazhu\.com/notice/getAppPopupNotifyAlert',
            'reason': 'The retained base prefix matcher already covers the narrower optional-query form with the same reject-dict action.',
        },
    },
}

def exclude_audited_semantic_duplicates(lines, origins, source):
    specs = _SEMANTIC_DUPLICATE_REWRITE_RULES.get(source, {})
    kept_lines, kept_origins, exclusions = [], [], []
    if len(lines) != len(origins):
        raise RuntimeError(source + ' Rewrite source-origin alignment failed during duplicate filtering')
    for index, (line, origin) in enumerate(zip(lines, origins)):
        matcher = entry_regex(line)
        spec = specs.get(matcher)
        if spec is None:
            kept_lines.append(line)
            kept_origins.append(origin)
            continue
        if action_key(line) != spec['action_key']:
            raise RuntimeError(source + ' audited duplicate matcher action changed; manual review required: ' + line)
        record = {
            'source': source,
            'source_entry_index': index,
            'input_line': line,
            'matcher': matcher,
            'action': split_action(line)[1],
            'covered_by': spec['covered_by'],
            'reason': spec['reason'],
            'status': 'excluded_semantic_duplicate',
        }
        if source == 'thelong':
            record['source_file'], record['source_line_number'], record['source_raw_line'] = origin
            record['source_catalog'] = 'Thelongdarkorg/loon-plugins'
        else:
            record['source_file'], record['source_section'], record['source_section_entry_index'], record['source_raw_line'] = origin
            record['source_catalog'] = 'aoomee/Loon-Adblock-Plugins'
        exclusions.append(record)
    return kept_lines, kept_origins, exclusions

# Thelongdarkorg（标准 v1，直接保留）
thelong_rw, thelong_sc = [], []
thelong_rw_origins = []
thelong_rule, thelong_mitm = [], []
thelong_rule_generated = []
rule_scope_adjustments = []
thelong_duplicate_exclusions = []
if args.apps:
    for fname, atext in iter_app_plugins(args.apps):
        _, s = split_sections(atext)
        app_rewrite_lines = real_lines(s.get('Rewrite', []))
        # Capture origins before filtering so flattened indexes remain aligned with retained rules.
        app_rewrite_origins = []
        _origin_section = None
        for _line_number, _raw_line in enumerate(atext.splitlines(), 1):
            _section_match = re.match(r'^\[([A-Za-z]+)\]\s*\Z', _raw_line)
            if _section_match:
                _origin_section = _section_match.group(1)
            elif (_origin_section == 'Rewrite' and _raw_line.strip()
                  and not _raw_line.lstrip().startswith('#')):
                app_rewrite_origins.append((fname, _line_number, _raw_line.strip()))
        if len(app_rewrite_origins) != len(app_rewrite_lines):
            raise RuntimeError('Thelong Rewrite source-origin alignment failed: ' + fname)
        if fname == 'baidunetdisk_splash_ad_block.plugin':
            app_rewrite_lines, baidu_netdisk_adjustments = narrow_baidunetdisk_ad_image_host(
                app_rewrite_lines, 'thelong')
            block_scope_adjustments.extend(baidu_netdisk_adjustments)
            app_rewrite_lines, baidu_cdn_adjustments = narrow_baidunetdisk_cdn_subdomains(
                app_rewrite_lines, 'thelong')
            block_scope_adjustments.extend(baidu_cdn_adjustments)
        if _lite_advertising_guard_present and fname == 'jd_splash_ad_block.plugin':
            _kept_app_rewrite_lines = []
            _source_section = None
            _source_line_numbers = {}
            for _line_number, _raw_line in enumerate(atext.splitlines(), 1):
                _section_match = re.match(r'^\[(.+?)\]\s*$', _raw_line)
                if _section_match:
                    _source_section = _section_match.group(1).strip()
                elif _source_section == 'Rewrite' and _raw_line.strip():
                    _source_line_numbers.setdefault(_raw_line.strip(), _line_number)
            _kept_app_rewrite_origins = []
            for _line, _origin in zip(app_rewrite_lines, app_rewrite_origins):
                if entry_regex(_line) == _LITE_ADVERTISING_MATCHER:
                    if _line != _LITE_ADVERTISING_THELONG_RESPONSE:
                        raise RuntimeError('Thelong JD Lite 上游响应规则发生变化，拒绝扩大排除范围：' + _line)
                    lite_advertising_rewrite_exclusions.append({
                        'source': 'thelong',
                        'source_catalog': 'Thelongdarkorg/loon-plugins',
                        'source_file': fname,
                        'source_line_number': _source_line_numbers.get(_line),
                        'input_line': _line,
                        'matcher': _LITE_ADVERTISING_MATCHER,
                        'action': 'response-body-replace-regex jdLiteAdvertisingVO sooyaaabo',
                        'reason': 'The retained base request-phase reject terminates this URL before an upstream response exists; this response-body rewrite is unreachable and adds no ad-blocking effect.',
                        'status': 'excluded_unreachable_response_rule',
                    })
                else:
                    _kept_app_rewrite_lines.append(_line)
                    _kept_app_rewrite_origins.append(_origin)
            app_rewrite_lines = _kept_app_rewrite_lines
            app_rewrite_origins = _kept_app_rewrite_origins
        if fname == 'qqmusic_splash_ad_block.plugin':
            _, qqmusic_thelong_present = validate_qqmusic_sources(extra_text, atext)
            if qqmusic_thelong_present:
                app_rewrite_lines, qqmusic_thelong_adjustments = narrow_qqmusic_scope(
                    app_rewrite_lines, 'thelong')
                block_scope_adjustments.extend(qqmusic_thelong_adjustments)
        thelong_rw += app_rewrite_lines
        thelong_rw_origins += app_rewrite_origins
        thelong_sc += real_lines(s.get('Script', []))
        app_rule_lines = real_lines(s.get('Rule', []))
        if fname == 'baidunetdisk_splash_ad_block.plugin':
            app_rule_lines, generated_rules, adjustments = add_baidunetdisk_advlion_quic_rule(
                app_rule_lines, s.get('MITM', []), 'thelong')
            thelong_rule_generated.extend(generated_rules)
            rule_scope_adjustments.extend(adjustments)
        thelong_rule += app_rule_lines
        for l in s.get('MITM', []):
            if '=' in l:
                thelong_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# Generated parity rules are appended only after all upstream Rule rows so their
# synthetic source indexes cannot shift the exact origin mapping of later plugins.
thelong_rule.extend(thelong_rule_generated)
thelong_rw, thelong_rw_origins, thelong_duplicate_exclusions = exclude_audited_semantic_duplicates(
    thelong_rw, thelong_rw_origins, 'thelong')

# 天天基金 GetAppStartImg：保留响应信封并清空 datas，不能同时保留请求阶段硬拒绝。
# 上游 tiantianjijin_splash_ad_block.plugin 有抓包说明：App 需要 resultCode=0 的响应信封；
# reject/reject-dict 会让 App 走本地缓存回退，且请求被终止后响应 JSON 改写根本不会执行。
# 只有 Thelong 精确响应规则仍存在时，才排除 base 与 block 两路的精确 request reject。
_TTJJ_START_IMAGE_MATCHER = (
    r'^https?://appactive\.1234567\.com\.cn/AppoperationApi/OperationService/GetAppStartImg'
)
_TTJJ_START_IMAGE_RESPONSE = (
    r"^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg "
    r"response-body-json-jq '.datas = []'"
)
_TTJJ_START_IMAGE_REQUEST_ACTION = ('REJECT', 'reject', 'reject(404)')
ttjj_start_image_rewrite_exclusions = []
_ttjj_response_rows = [
    (index, line) for index, line in enumerate(thelong_rw)
    if entry_regex(line) == _TTJJ_START_IMAGE_MATCHER
]
if _ttjj_response_rows:
    if len(_ttjj_response_rows) != 1 or _ttjj_response_rows[0][1] != _TTJJ_START_IMAGE_RESPONSE:
        raise RuntimeError(
            'Thelong 天天基金 GetAppStartImg 响应规则发生变化，拒绝自动移除请求规则：'
            + '; '.join(line for _, line in _ttjj_response_rows)
        )

    _ttjj_reason = (
        'Thelong 天天基金插件基于 App 6.8.13 多次真机抓包，明确要求保留 resultCode=0 '
        '响应信封并仅清空 datas；请求阶段 reject 会终止请求、触发本地缓存回退，'
        '并使该响应 JSON 改写不可达。仅保留经上游原文确认的响应改写。'
    )

    def _exclude_ttjj_request_rejects(lines, source):
        kept = []
        for index, line in enumerate(lines):
            if entry_regex(line) != _TTJJ_START_IMAGE_MATCHER:
                kept.append(line)
                continue
            if action_key(line) != _TTJJ_START_IMAGE_REQUEST_ACTION:
                raise RuntimeError(
                    source + ' 天天基金 GetAppStartImg 请求动作发生变化，拒绝扩大排除范围：' + line
                )
            record = {
                'source': source,
                'source_entry_index': index,
                'input_line': line,
                'matcher': _TTJJ_START_IMAGE_MATCHER,
                'action': split_action(line)[1],
                'preserved_response_rule': _TTJJ_START_IMAGE_RESPONSE,
                'reason': _ttjj_reason,
                'status': 'excluded_conflicting_request_reject',
            }
            if source == 'base':
                record['source_catalog'] = 'R-Store converted Rewrite source'
            else:
                record['source_catalog'] = 'fmz200/wool_scripts blockAdsV2'
                record['source_line_number'] = next(
                    (number for number, raw in enumerate(extra_text.splitlines(), 1)
                     if raw.strip() == line.strip()),
                    None,
                )
            ttjj_start_image_rewrite_exclusions.append(record)
        return kept

    base_rw = _exclude_ttjj_request_rejects(base_rw, 'base')
    block_rw = _exclude_ttjj_request_rejects(block_rw, 'block')
# aoomee（v1/v2 混合；URL Rewrite 的 reject 并入 Rewrite；generic/cron 由合并器识别）
ao_rw, ao_sc, ao_rule, ao_mitm = [], [], [], []
ao_rw_origins = []
aoomee_duplicate_exclusions = []
if args.aoomee:
    for fname, s in iter_aoomee(args.aoomee):
        for _source_index, l in enumerate(real_lines(s.get('Rewrite', []))):
            ao_rw.append(convert_shadowrocket_line(l))
            ao_rw_origins.append((fname, 'Rewrite', _source_index, l))
        for _source_index, l in enumerate(real_lines(s.get('URL Rewrite', []))):
            toks = l.split()
            if len(toks) == 2 and toks[1] in _LEGACY_REJECT:
                ao_rw.append(l)
                ao_rw_origins.append((fname, 'URL Rewrite', _source_index, l))
        ao_sc += [convert_shadowrocket_line(l)
                  for l in real_lines(s.get('Script', []))]
        ao_rule += real_lines(s.get('Rule', []))
        for l in s.get('MITM', []):
            if '=' in l:
                ao_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
ao_rw, ao_rw_origins, aoomee_duplicate_exclusions = exclude_audited_semantic_duplicates(
    ao_rw, ao_rw_origins, 'aoomee')
# ---------------- zmjde 指定插件 ----------------
# App 高优先级（完整并入，同正则替换其他来源）：DiDi/PinDuoDuo + 闲鱼/淘宝/什么值得买；
# 通用 base 优先，只补 base 没有的（不覆盖）：Block_HTTPDNS/BlockAdvertisers + 可莉广告过滤器。
_ZMJ_APP = ('DiDi_remove_ads.lpx', 'PinDuoDuo_remove_ads.lpx',
            'FleaMarket_remove_ads.lpx', 'Taobao_remove_ads.lpx', 'smzdm_remove_ads.lpx')
_ZMJ_GENERAL = ('Block_HTTPDNS.lpx', 'BlockAdvertisers.lpx', 'Remove_ads_by_keli.lpx')
zmj_app_rw, zmj_app_sc, zmj_app_rule, zmj_app_mitm = [], [], [], []
zmj_gen_rw, zmj_gen_sc, zmj_gen_rule, zmj_gen_mitm = [], [], [], []


def _zmj_collect(s):
    rw, sc, rule = list(s.get('Rewrite', [])), list(s.get('Script', [])), list(s.get('Rule', []))
    hm = []
    for l in s.get('MITM', []):
        if '=' in l:
            hm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
    return rw, sc, rule, hm


if args.zmjde:
    pdir = os.path.join(args.zmjde, 'Plugin')
    if not os.path.isdir(pdir):
        pdir = args.zmjde
    for name, bucket in ([(n, 'app') for n in _ZMJ_APP]
                         + [(n, 'gen') for n in _ZMJ_GENERAL]):
        path = os.path.join(pdir, name)
        if not os.path.exists(path):
            raise SystemExit('zmjde 缺少插件文件: %s' % name)
        s = parse_loose_sections(open(path, encoding='utf-8').read())
        rw, sc, rule, hm = _zmj_collect(s)
        if bucket == 'app':
            zmj_app_rw += rw; zmj_app_sc += sc; zmj_app_rule += rule; zmj_app_mitm += hm
        else:
            zmj_gen_rw += rw; zmj_gen_sc += sc; zmj_gen_rule += rule; zmj_gen_mitm += hm

# ---------------- QuanX 单文件 App 插件（.conf，可重复，如瓜子影视）----------------
qxapp_rw, qxapp_mitm = [], []


def _qx_relit(s):
    """QuanX 正则 -> Loon v2 正则字面量 /pattern/，未转义的 / 转义"""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == '\\' and i + 1 < n:
            out.append(s[i:i + 2]); i += 2
        elif s[i] == '/':
            out.append(r'\/'); i += 1
        else:
            out.append(s[i]); i += 1
    return '/' + ''.join(out) + '/'


def parse_qx_app_file(path):
    """解析单个 QuanX .conf：返回 (Loon v2 规则行, MITM host)。
    目前覆盖该类文件实际出现的 jsonjq-response-body；未识别的动作跳过（不静默乱转）。"""
    hosts, out = [], []
    for raw in open(path, encoding='utf-8').read().split('\n'):
        line = raw.strip()
        if not line or line.startswith('//') or line.startswith('#'):
            continue
        if line.startswith('hostname'):
            hosts += [h.strip() for h in line.split('=', 1)[1].split(',') if h.strip()]
            continue
        if line.startswith('^http'):
            m = re.match(r'^(\S+)\s+url\s+(.+)$', line)
            if not m:
                continue
            jm = re.match(r"^jsonjq-response-body\s+'(.*)'\s*$", m.group(2))
            if jm:
                jq = jm.group(1).replace('`', '``')
                out.append('response if ${url} ~= %s then response.json.jq(`%s`)'
                           % (_qx_relit(m.group(1)), jq))
    return out, hosts


if args.qxapp:
    for path in args.qxapp:
        if not os.path.exists(path):
            raise SystemExit('qxapp 缺少文件: %s' % path)
        rw, hm = parse_qx_app_file(path)
        qxapp_rw += rw; qxapp_mitm += hm

# ---------------- 执行优先级合并 ----------------
# 位置顺序：base 骨架 -> block -> zmjde通用 -> thelong -> aoomee -> qx单文件App -> amapApp -> zmjdeApp；
# 数字越小优先级越高：amap App=-1（最高），zmjde App=0，qx 专属 App=1；通用源按既有顺序。
# MyBlockAds（标准 Loon v2，综合大合集）：prio=7 最低，只补现有源没有的规则，零回归。
if mb_text is not None:
    mb_sec = parse_loose_sections(mb_text)
    mb_rw = real_lines(mb_sec.get('Rewrite', []))
    mb_sc = real_lines(mb_sec.get('Script', []))
    mb_rule = real_lines(mb_sec.get('Rule', []))
    mb_mitm = []
    for l in mb_sec.get('MITM', []):
        if '=' in l:
            mb_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
else:
    mb_rw, mb_sc, mb_rule, mb_mitm = [], [], [], []
rw_feeds = [('base', 4, base_rw), ('block', 5, block_rw), ('zmjgen', 6, zmj_gen_rw),
            ('thelong', 3, thelong_rw), ('aoomee', 2, ao_rw),
            ('qxapp', 1, qxapp_rw), ('amap', -1, amap_rw), ('zmjapp', 0, zmj_app_rw),
            ('myblockads', 7, mb_rw)]
sc_feeds = [('base', 4, base_sc), ('block', 5, block_sc), ('zmjgen', 6, zmj_gen_sc),
            ('thelong', 3, thelong_sc), ('aoomee', 2, ao_sc),
            ('amap', -1, amap_sc), ('zmjapp', 0, zmj_app_sc), ('myblockads', 7, mb_sc)]
merged_rw, rw_unguarded = priority_merge([(p, x) for _, p, x in rw_feeds])
merged_sc, sc_unguarded = priority_merge([(p, x) for _, p, x in sc_feeds])
# 无守卫行（generic/cron）归入 Script 段末尾，再整体去重
merged_sc = dedup_keep_order(merged_sc + rw_unguarded + sc_unguarded)
merged_rw = dedup_keep_order(merged_rw)

# ---------------- Argument：blockAdsV2 + aoomee（YouTube 增强）----------------
arg_items = dedup_keep_order(real_lines(extra_sec.get('Argument', [])))
if args.aoomee:
    for fname, s in iter_aoomee(args.aoomee):
        arg_items += real_lines(s.get('Argument', []))
arg_items = dedup_keep_order(arg_items)

# ---------------- Rule：App 优先（aoomee -> thelong），再综合（block -> filter）----------------
_RT_NORM = {
    'domain': 'DOMAIN',
    'domain-suffix': 'DOMAIN-SUFFIX',
    'domainsuffix': 'DOMAIN-SUFFIX',  # 兼容历史无连字符写法
    'ip-cidr': 'IP-CIDR',
}
_POL_NORM = {'reject': 'REJECT', 'direct': 'DIRECT'}


def normalize_rule(line):
    """归一化 aoomee 小写类型/策略，IP-CIDR 补 no-resolve；组合规则原样返回。"""
    parts = [p.strip() for p in line.split(',')]
    t = _RT_NORM.get(parts[0].lower(), parts[0])
    if t not in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6'):
        return line
    pol = _POL_NORM.get(parts[2].lower(), parts[2])
    rest = parts[3:]
    if t in ('IP-CIDR', 'IP-CIDR6') and 'no-resolve' not in rest:
        rest.append('no-resolve')
    return ','.join([t, parts[1], pol] + rest)


rule_result = []
rule_idx = build_rule_index([])
rule_counts = collections.Counter()
rule_provenance_events = []
rule_source_indices = collections.Counter()


# ---------------- 功能长连接保护（避免误伤抖音私信等实时消息）----------------
# Frontier 是字节系 WebSocket 长连接网关（如 wss://frontier-im.douyin.com/ws/v2），
# 抖音私信/实时消息走这条长连接，不是广告域名；拦截会导致私信无法收发，
# 但 APNs 推送走苹果系统通道、不受影响，表现为"有推送却收发不了消息"。
# 故凡拦截目标是 Frontier 长连接的规则一律放行（含 frontier 即保护，覆盖精确域名与 AND/KEYWORD 组合）。
def is_frontier_guard(line):
    return 'frontier' in line.lower()


def is_tencent_httpdns_service_ip_block(line):
    """Protect Tencent's active HTTPDNS service IPs from exact-IP REJECT rules."""
    parts = [part.strip() for part in line.split(',')]
    return (
        len(parts) >= 3
        and parts[0] == 'IP-CIDR'
        and parts[1] in {'119.29.29.98/32', '119.29.29.99/32'}
        and parts[2] == 'REJECT'
    )


def add_rule(line, src):
    original_line = line
    line = normalize_rule(line)
    source_index = rule_source_indices[src]
    rule_source_indices[src] += 1
    event = {
        'source': src,
        'source_entry_index': source_index,
        'original_input_line': original_line,
        'normalized_line': line,
    }
    if is_tencent_httpdns_service_ip_block(line):
        event.update({
            'status': 'excluded_safety_guard',
            'matched_ip': line.split(',')[1].split('/')[0],
            'reason': (
                'Tencent Cloud documents 119.29.29.98 as its active HTTP HTTPDNS '
                'endpoint and 119.29.29.99 as its active HTTPS HTTPDNS endpoint; '
                'an exact-IP REJECT rule would disable those DNS resolution paths.'
            ),
        })
        rule_provenance_events.append(event)
        rule_counts[src + '_keep'] += 1
        return
    if is_frontier_guard(line):
        event.update({'status': 'excluded_safety_guard',
                      'reason': 'Frontier/WebSocket long-connection protection'})
        rule_provenance_events.append(event)
        rule_counts[src + '_keep'] += 1
        return
    if line in rule_result:
        previous = next((item for item in reversed(rule_provenance_events)
                         if item.get('status') == 'included'
                         and item.get('output_line') == line), None)
        event.update({'status': 'duplicate_exact', 'duplicate_of': line,
                      'duplicate_of_source': previous.get('source') if previous else None})
        rule_provenance_events.append(event)
        rule_counts[src + '_dup'] += 1
        return
    t = line.split(',')[0]
    if t in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6'):
        if rule_is_covered(line, rule_idx):
            covering = None
            for existing in rule_result:
                if rule_is_covered(line, build_rule_index([existing])):
                    covering = existing
                    break
            previous = next((item for item in reversed(rule_provenance_events)
                             if item.get('status') == 'included'
                             and item.get('output_line') == covering), None)
            event.update({
                'status': 'covered_by_existing_rule',
                'covered_by': covering,
                'covered_by_source': previous.get('source') if previous else None,
            })
            rule_provenance_events.append(event)
            rule_counts[src + '_dup'] += 1
            return
        add_to_index(line, rule_idx)
    rule_result.append(line)
    event.update({'status': 'included', 'output_line': line})
    rule_provenance_events.append(event)
    rule_counts[src + '_add'] += 1


if args.amap:
    for l in amap_rule:
        add_rule(l, 'amap')
if args.zmjde:
    for l in zmj_app_rule:
        add_rule(l, 'zmjapp')
if args.aoomee:
    for l in ao_rule:
        add_rule(l, 'aoomee')
if args.apps:
    for l in thelong_rule:
        add_rule(l, 'thelong')
for l in real_lines(extra_sec.get('Rule', [])):
    add_rule(l, 'block')
if args.zmjde:
    # 通用拦截器：以已有 Rule 为基础，语义覆盖判定后只补未覆盖项（不覆盖 base）
    for l in zmj_gen_rule:
        add_rule(l, 'zmjgen')
# R-Store 独立分流（filter），未覆盖才补
fstats = {'total': 0, 'covered': 0, 'added': 0}
if args.filter != 'none':
    if args.filter == 'fetch':
        try:
            ftext, used_url, _ = fetch_validated(
                [FILTER_URL] + FILTER_MIRRORS, fetch, validate_filter, 'R-Store filter')
            print('[fetch] 已获取并通过完整性检查 R-Store filter:', used_url)
        except Exception as e:
            raise SystemExit('R-Store filter 获取失败: %s' % e)
    else:
        ftext = open(args.filter, encoding='utf-8').read()
    for fr in dedup_keep_order(parse_qx_filter(ftext)):
        fstats['total'] += 1
        before = len(rule_result)
        add_rule(fr, 'filter')
        if len(rule_result) == before:
            fstats['covered'] += 1
        else:
            fstats['added'] += 1
for l in mb_rule:
    add_rule(l, 'myblockads')
rule_items = dedup_keep_order(rule_result)

# ---------------- MITM：base 主机 + 各来源收敛（守卫反查），再自愈 ----------------
mitm = []
for l in base_sec.get('MITM', []):
    if '=' in l:
        mitm += [x.strip() for x in l.split('=', 1)[1].split(',')
                 if x.strip() and not mitm_skip_host(x)]
# 守卫真实 host：用最终 Rewrite/Script（含全部来源），供通配 TLD/缺 TLD 反查
guard_real = guard_hosts_from_lines(merged_rw + merged_sc)
# qxapp 单文件（如瓜子影视）的规则守卫含 OR + 随机域名（[a-z0-9]+），guard 提取无法静态
# 解析出具体 host；其 hostname 行是权威声明，且这些 host 已验证被规则守卫匹配，
# 故补入需要集合，避免被 prune_unused_mitm 误判为无动作 host 而裁剪、导致 HTTPS 规则失效。
if args.qxapp:
    guard_real = set(guard_real) | {
        h for h in qxapp_mitm if not mitm_skip_host(h) and '*' not in h and '?' not in h}
extra_raw = []
for l in extra_sec.get('MITM', []):
    if '=' in l:
        extra_raw += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# The 119.29.29.* MITM wildcard is declared only by the unused ZhangLe Cai Fu Tong
# app-specific feed alongside its HTTPDNS blocking rule. Remove this source's
# declaration, but allow another independent source to retain it if needed.
_block_mitm_kept = []
for _host in extra_raw:
    if _host.lower() == '119.29.29.*':
        block_mitm_exclusions.append({
            'source': 'block',
            'source_catalog': 'fmz200/wool_scripts blockAdsV2 / ZhangLeCaiFuTong',
            'hostname': _host,
            'reason': 'Only declared by the unused ZhangLe Cai Fu Tong app-specific ad feed; its paired HTTPDNS blocking Rewrite is excluded.',
            'status': 'excluded_unused_app',
        })
    else:
        _block_mitm_kept.append(_host)
extra_raw = _block_mitm_kept
dropped = []
for h in extra_raw + thelong_mitm + ao_mitm + amap_mitm + zmj_app_mitm + zmj_gen_mitm + qxapp_mitm + mb_mitm:
    got = normalize_extra_host(h, guard_real)
    # 跳过证书绑定域（如 amemv）：从源头不进 MITM，不使用负向语法
    got = [x for x in got if not mitm_skip_host(x)]
    if not got:
        dropped.append(h)
    else:
        mitm += got
mitm = dedup_keep_order(mitm)


def _mitm_covered(host, hostset):
    if host in hostset:
        return True
    return any(m.startswith('*.') and host.endswith('.' + m[2:])
               for m in hostset)


mitm_healed = []
# 必须同时扫描 Rewrite + Script（Script 段的 http(s)-request/response 守卫同样需要 MITM）
for _h in sorted(guard_hosts_from_lines(merged_rw + merged_sc)):
    # 证书绑定域（如 amemv）整体 pass：守卫退化出的 *.amemv.com 不补进 MITM
    if mitm_skip_host(_h):
        continue
    # 只补具体 host：守卫退化出的整域通配（*.域）不补，避免 pinning 域被强制 MITM 而握手失败
    if '*' in _h or '?' in _h:
        continue
    if not _mitm_covered(_h, set(mitm)):
        mitm.append(_h)
        mitm_healed.append(_h)
mitm = dedup_keep_order(mitm)
# 最终输出前统一清理所有来源（包括 base 原有声明及自愈结果）中的 IP literal。
mitm_ip_dropped = [h for h in mitm if is_ip_literal_host(h)]
if mitm_ip_dropped:
    mitm = [h for h in mitm if not is_ip_literal_host(h)]
if any(is_ip_literal_host(h) for h in mitm):
    raise RuntimeError('MITM hostname invariant failed: IP literal remained')


def host_zone_from_regex(rx):
    """从 entry_regex 输出提取 host 部分（起始 ^ 可选），无法提取返回 None。"""
    # Accept both common scheme spellings: https?:// and http[s]?://.
    m = re.match(r'\^?(?:https?\??|http\[s\]\??)://', rx)
    if not m:
        return None
    rest = rx[m.end():]
    out, i, in_class, class_first = [], 0, False, False
    while i < len(rest):
        ch = rest[i]
        if ch == '\\' and i + 1 < len(rest):
            # Escaped brackets are literals and must not change class state.
            if rest[i + 1] == '/' and not in_class:
                break
            out.append(rest[i:i + 2])
            if in_class:
                class_first = False
            i += 2
            continue
        if not in_class:
            if ch == '/':
                break
            if ch == '[':
                in_class, class_first = True, True
            out.append(ch)
            i += 1
            continue

        # In a character class, a leading ']' (after optional '^') is a
        # literal member, not the closing delimiter: e.g. []/] and [^]/].
        if class_first and ch == '^':
            out.append(ch)
            i += 1
            continue
        if ch == ']' and class_first:
            out.append(ch)
            class_first = False
            i += 1
            continue
        if ch == ']':
            in_class = False
            out.append(ch)
            i += 1
            continue
        # ICU/POSIX-style nested class operators [:...:], [. ... .], [=...=]
        # contain their own closing bracket; do not close the outer class.
        if ch == '[' and i + 1 < len(rest) and rest[i + 1] in ':.=':
            marker = rest[i + 1]
            end = rest.find(marker + ']', i + 2)
            if end >= 0:
                out.append(rest[i:end + 2])
                class_first = False
                i = end + 2
                continue
        out.append(ch)
        class_first = False
        i += 1
    zone = ''.join(out)
    # A path may begin inside an optional group, e.g. (\/mkt)?.
    # The opening parenthesis belongs to the path, not the authority.
    # Remove only unmatched trailing open groups; balanced host groups remain intact.
    while zone.endswith('('):
        depth, escaped, in_class = 0, False, False
        for ch in zone:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
            elif ch == '[':
                in_class = True
            elif ch == ']':
                in_class = False
            elif not in_class and ch == '(':
                depth += 1
            elif not in_class and ch == ')':
                depth -= 1
        if depth <= 0:
            break
        zone = zone[:-1]
    return zone


def is_narrow_host_pattern(pat):
    """含长度>=3 的连续字母数字字面片段即视为针对性窄模式；否则为匹配一切的宽泛模式。
    先剔除字符类 [...]（否定字符类里的字母并非字面序列），避免伪窄模式。"""
    stripped = re.sub(r'\[.*?\]', '', pat)
    return any(len(x) >= 3 for x in re.findall(r'[A-Za-z0-9]+', stripped))


def compiled_narrow_hosts(rule_lines):
    """从规则行提取编译后的窄 host 正则（去重，跳过不可编译模式）。"""
    out = {}
    for l in rule_lines:
        rx = entry_regex(l)
        if not rx:
            continue
        z = host_zone_from_regex(rx)
        if not z or not is_narrow_host_pattern(z):
            continue
        try:
            out.setdefault(z, re.compile('^(?:%s)$' % z, re.IGNORECASE))
        except re.error:
            pass
    return out


def strip_host_port(p):
    """剥离 host 模式末尾端口部分（:1234 / :\\d+ / :\\d{4} / \\:\\w+ / (?::443)?）。"""
    p = re.sub(r'\(:?\\?:?\d+\)\?', '', p)
    p = re.sub(r'\\?:[\w\\+{}]+$', '', p)
    return p


def expand_or_patterns(z, limit=64):
    """展开 OR 分组为多个模式（笛卡尔积，上限 limit），返回模式列表；可选分组先取其内容。
    含裸 | 但无匹配括号的损坏模式不展开；无进展即终止，避免无限循环。"""
    s = z.replace('?:', '')
    s = re.sub(r'\(([^()]*)\)\?', r'\1', s)
    out = [s]
    while any('|' in x for x in out):
        if len(out) >= limit:
            break
        nxt = []
        changed = False
        for p in out:
            m = re.search(r'\(([^()|]*\|[^()]*)\)', p)
            if not m:
                nxt.append(p)
                continue
            changed = True
            for opt in m.group(1).split('|'):
                nxt.append(p[:m.start()] + opt + p[m.end():])
        if not changed:
            break
        out = nxt
    return out[:limit]


def materialize_hosts(z):
    """展开 OR 全分支，对每个无 OR 模式生成可信样本，返回去重样本集合。"""
    res = set()
    for p in expand_or_patterns(z):
        zc = strip_host_port(p)
        if '(' in zc or ')' in zc:
            continue
        try:
            samp = materialize_host(p)
            if re.compile('^(?:%s)$' % zc, re.IGNORECASE).match(samp):
                res.add(samp)
        except (re.error, TypeError):
            pass
    return res


def materialize_host(z):
    """把 host 正则里的通配构造替换成合法占位，生成该模式确实能匹配的一个具体样本 host（用原模式验证）。
    用于判断标准通配 *.X 是否被规则需要：规则样本是 X 的子域则通配需保留。"""
    s = z.replace('?:', '')
    s = re.sub(r'\(:?\\?:?\d+\)\?', '', s)
    s = re.sub(r'\\?:[\w\\+{}]+$', '', s)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\(([^()]*)\)\?', r'\1', s)
        s = re.sub(r'\(([^()|]*\|[^()]*)\)', lambda m: m.group(1).split('|')[0], s)

    def wrep(m):
        n = m.group(1)
        if n in ('+', '*', ''):
            return 'aaa'
        if ',' in n:
            lo = n.split(',')[0]
            return 'a' * (int(lo) if lo else 1)
        return 'a' * int(n)
    s = re.sub(r'\\w\{(\d+(?:,\d+)?)\}', wrep, s)
    s = re.sub(r'\\w[+*]', 'aaa', s)
    s = re.sub(r'\\w', 'a', s)

    def drep(m):
        n = m.group(1)
        if n in ('+', '*', '?', ''):
            return '1'
        if ',' in n:
            lo = n.split(',')[0]
            return '1' * (int(lo) if lo else 1)
        return '1' * int(n)
    s = re.sub(r'\\d\{(\d+(?:,\d+)?)\}', drep, s)
    s = re.sub(r'\\d[+*?]?', '1', s)

    def crep(m):
        content, quant = m.group(1), m.group(2)
        length = 1
        if quant and quant.isdigit():
            length = int(quant)
        elif quant and ',' in quant:
            lo = quant.split(',')[0]
            length = int(lo) if lo else 1
        chars = re.sub(r'[^\w]', '', content)
        ch = chars[0] if chars else ('1' if re.match(r'^[\d\-]+$', content) else 'a')
        return (ch * length) if length > 1 else ch
    s = re.sub(r'\[([^\]]*)\](?:\{(\d+(?:,\d+)?)\}|([+*?]))?', crep, s)

    def dot_rep(m):
        nxt = s[m.end():m.end() + 2]
        # 后紧跟转义点则用纯标签；否则带点，生成点分离子域（避免前缀粘连成不同域）
        return 'abc' if nxt == '\\.' else 'abc.'
    s = re.sub(r'\.\*|\.\+\??', dot_rep, s)
    s = re.sub(r'\{\d+(?:,\d+)?\}', '', s)
    s = re.sub(r'(?<=[A-Za-z0-9)])[?+*]', '', s)
    s = s.replace('\\.', '.').replace('\\-', '-')
    s = re.sub(r'[(){}]', '', s)
    s = re.sub(r':.*$', '', s)
    s = re.sub(r'\.+', '.', s).strip('.')
    return s


def matcher_may_use_https(text):
    """判断 URL matcher 是否可能匹配 HTTPS；纯 HTTP 嵌入捕获组不需要 MITM。"""
    # 仅检查触发器部分，排除 script-path / then 后的远程脚本资源 URL。
    head = text.split(' then ', 1)[0].split('script-path=', 1)[0]
    normalized = head.replace(r'\/', '/')
    return bool(re.search(
        r'https://|https\?://|http\(s\)\?://|http\(\?:s\)\?://|http\[s\]\?://',
        normalized, re.IGNORECASE
    ))


def compiled_host_patterns(rule_lines):
    """编译 host 正则；遇到 Python 无法解析的模式时返回不确定标记，禁止激进裁剪。"""
    out, uncertain = {}, False
    for line in rule_lines:
        if re.match(r'^(?:generic|cron)\b', line.strip()):
            continue
        rx = entry_regex(line)
        if not rx:
            if matcher_may_use_https(line):
                uncertain = True
            continue
        zone = host_zone_from_regex(rx)
        if not zone:
            if matcher_may_use_https(rx):
                uncertain = True
            continue
        try:
            out.setdefault(zone, re.compile('^(?:%s)$' % zone, re.IGNORECASE))
        except re.error:
            uncertain = True
    return out, uncertain


def prune_unused_mitm(mitm_hosts, rule_lines):
    """按最终合并后的规则判断 MITM 用途，避免跨来源共享域名被误裁剪。"""
    all_patterns, uncertain = compiled_host_patterns(rule_lines)
    if uncertain:
        # Python re 与 Loon/ICU 不完全同构；无法解析时宁可保留 MITM，不冒险误删。
        return list(mitm_hosts)
    narrow = {z: rc for z, rc in all_patterns.items() if is_narrow_host_pattern(z)}

    def trusted_samples(zdict):
        out = set()
        for z in zdict:
            out |= materialize_hosts(z)
        return out

    all_samples = trusted_samples(narrow)
    kept_conc = [
        h for h in mitm_hosts
        if not h.startswith('*.') and not h.startswith('-')
        and any(rc.match(h) for rc in all_patterns.values())
    ]

    kept_wild = []
    for pattern in mitm_hosts:
        if not pattern.startswith('*.'):
            continue
        suffix = pattern[2:]
        probes = (suffix, 'probe.' + suffix, 'probe.probe.' + suffix)
        if (any(sample.endswith('.' + suffix) for sample in all_samples)
                or any(rc.match(probe) for rc in all_patterns.values() for probe in probes[1:])):
            kept_wild.append(pattern)

    neg = [h for h in mitm_hosts if h.startswith('-')]
    return kept_conc + kept_wild + neg

# 自动裁剪：仅按最终合并后的 Rewrite/Script host 正则判断，避免跨来源共享域名误删。
_mitm_before_prune = len(mitm)
mitm = prune_unused_mitm(mitm, merged_rw + merged_sc)
mitm_pruned = _mitm_before_prune - len(mitm)
# The three exact ZhangLe hosts become orphaned after all dedicated Rewrite rules
# are excluded. The general MITM pruner intentionally fails closed when any
# host pattern cannot be analyzed; remove only these exact app-specific hosts
# after checking whether any final Rewrite/Script matcher could target them.
_ZHANGLE_UNUSED_MITM_HOSTS = {
    'c.zhangle.com',
    'live.inst-service.htsc.com',
    'geetest.htsc.com',
}
zhangle_mitm_exclusions = []
_kept_zhangle_mitm = []
for _host in mitm:
    _host_lower = _host.lower()
    if _host_lower not in _ZHANGLE_UNUSED_MITM_HOSTS:
        _kept_zhangle_mitm.append(_host)
        continue
    _could_be_referenced = False
    _reference_reason = None
    for _line in merged_rw + merged_sc:
        # Generic/Cron/Network Changed scripts are manual or event/schedule
        # actions. Their script-path URLs identify downloaded code, not an HTTP
        # request hostname that requires MITM coverage.
        if re.match(r'^(?:generic|cron|network-changed)\b', _line.strip(), re.IGNORECASE):
            continue
        # MITM only serves HTTPS requests; HTTP-only matchers cannot justify TLS hosts.
        if not matcher_may_use_https(_line):
            continue
        _rx = entry_regex(_line)
        if not _rx:
            if matcher_may_use_https(_line):
                _could_be_referenced = True
                _reference_reason = ('unparsed_https_matcher', _line.strip(), '')
                break
            continue
        _zone = host_zone_from_regex(_rx)
        if not _zone:
            if matcher_may_use_https(_rx):
                _could_be_referenced = True
                _reference_reason = ('unextractable_https_host', _line.strip(), _rx)
                break
            continue
        try:
            if re.compile('^(?:' + _zone + ')$', re.IGNORECASE).match(_host_lower):
                _could_be_referenced = True
                _reference_reason = ('host_regex_match', _line.strip(), _zone)
                break
        except re.error:
            # ICU's \cX escape denotes a control character. Control characters
            # cannot occur in a DNS hostname, so this matcher cannot reference
            # any valid MITM host even though Python re rejects the syntax.
            if re.search(r'\\c[A-Za-z]', _zone):
                continue
            # Python may not understand ICU constructs such as \p{L}.
            # Use a literal suffix as a conservative host-level fallback.
            _normalized_zone = _zone.lower().replace(r'\.', '.')
            _suffix_match = re.search(
                r'([a-z0-9-]+(?:\.[a-z0-9-]+)+)$', _normalized_zone
            )
            if (_host_lower in _normalized_zone or not _suffix_match
                    or _host_lower == _suffix_match.group(1)
                    or _host_lower.endswith('.' + _suffix_match.group(1))):
                _could_be_referenced = True
                _reference_reason = ('python_regex_fallback', _line.strip(), _zone)
                break
    if _could_be_referenced:
        print('  [MITM 保留诊断] %s <- %s | %s | %s' % (
            _host, _reference_reason[0], _reference_reason[2],
            _reference_reason[1][:240]
        ))
        _kept_zhangle_mitm.append(_host)
        continue
    zhangle_mitm_exclusions.append({
        'source': 'merged_mitm',
        'source_catalog': 'R-Store / blockAdsV2 / merged app MITM',
        'hostname': _host,
        'reason': (
            'The three ZhangLe-only Rewrite rules are excluded and no final '
            'Rewrite/Script matcher can be shown to target this exact host; '
            'retaining it would add unused TLS interception without ad-blocking effect.'
        ),
        'status': 'excluded_unused_app',
    })
mitm = _kept_zhangle_mitm


# ---------------- 输出 ----------------
today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
header = [
    '#!name=R-Store × blockAdsV2 × 独立 App 去广告净化合集',
    '#!desc=合并 R-Store、blockAdsV2、Thelongdarkorg、aoomee、zmjde、高德地图、ddgksf2013 瓜子；'
    '按 URL 正则去重，专属 App 插件优先、同正则替换综合源；[Rule] 已含多套分流，单插件自包含',
    '#!author=zirawell / fmz200 / Thelongdarkorg / aoomee / zmjde / ddgksf2013（本仓库自动合并）',
    '#!homepage=https://github.com/XcvcvX/loon-change',
    '#!merged-at=%s' % today,
    '#!note=高德地图独立 App 规则优先级最高；不同动作保留，重复动作按来源优先级；脚本/JQ 依赖本仓库镜像。',
    '#!sources=R-Store(QuanX->Loon)+blockAdsV2+Thelongdarkorg+aoomee+zmjde+RuCu6-amap+ddgksf2013/GuaZiVideoAds',
    '',
]
out = list(header)
if arg_items:
    out += ['[Argument]'] + arg_items + ['']
if rule_items:
    out += ['[Rule]'] + rule_items + ['']
out += ['[Rewrite]'] + merged_rw + ['']
out += ['[Script]'] + merged_sc + ['']
out += ['[MITM]', 'hostname = ' + ', '.join(mitm), '']

if args.provenance_out:
    def _provenance_key(line):
        uk = unguarded_key(line)
        if uk is not None:
            return ('unguarded',) + tuple(uk)
        rx = entry_regex(line)
        if not rx:
            return ('unparsed', line.strip())
        return ('guarded', rx, action_key(line))

    def _section_provenance(feeds, output_lines, section):
        candidates = collections.defaultdict(list)
        for source, priority, lines, input_section in feeds:
            for index, line in enumerate(lines):
                key = _provenance_key(line)
                eligible = (input_section == section or
                            (section == 'Script' and input_section == 'Rewrite'
                             and key[0] == 'unguarded'))
                if eligible:
                    candidates[key].append({
                        'source': source, 'priority': priority,
                        'source_entry_index': index, 'input_section': input_section,
                        'input_line': line,
                    })
        records = []
        for output_index, output_line in enumerate(output_lines, 1):
            key = _provenance_key(output_line)
            matches = candidates.get(key, [])
            if matches:
                if key[0] == 'unguarded':
                    winner = matches[0]
                    for candidate in matches[1:]:
                        if (is_v2_line(candidate['input_line'])
                                and not is_v2_line(winner['input_line'])):
                            winner = candidate
                else:
                    winner = sorted(
                        matches,
                        key=lambda item: (item['priority'],
                                          0 if is_v2_line(item['input_line']) else 1)
                    )[0]
                source_rows = []
                for candidate in matches:
                    row = dict(candidate)
                    origin = source_origins.get((candidate['source'], candidate['input_section'], candidate['source_entry_index']))
                    if origin:
                        row.update(origin)
                    row['disposition'] = (
                        'selected' if candidate is winner else 'duplicate_same_semantics'
                    )
                    source_rows.append(row)
            else:
                source_rows = []
            records.append({
                'section': section,
                'output_entry_index': output_index,
                'output_line': output_line,
                'canonical_key': repr(key),
                'sources': source_rows,
                'trace_status': 'mapped' if source_rows else 'unmapped_or_generated',
            })
        return records

    # Multi-file upstream sources: retain exact plugin filename and original 1-based line.
    # Indices mirror the flattened feeds assembled above; no rule ordering is changed.
    source_origins = {}

    def _record_origin(source, section, index, filename, line_number, raw_line,
                       original_section=None):
        source_origins[(source, section, index)] = {
            'source_file': filename,
            'source_line_number': line_number,
            'source_raw_line': raw_line,
            'source_original_section': original_section or section,
        }

    def _raw_rows(path):
        current = None
        with open(path, encoding='utf-8') as source_handle:
            for line_number, raw in enumerate(source_handle, 1):
                match = re.match(r"^\[(.+?)\]\s*$", raw)
                if match:
                    current = match.group(1).strip()
                    continue
                value = raw.strip()
                # Match parse_loose_sections()/real_lines(): only '#' is currently
                # treated as a comment. Even a '//' row occupies a feed index.
                # Skipping it here shifts all later source origins.
                if current and value and not value.startswith('#'):
                    yield current, line_number, value

    if args.apps:
        for index, (filename, line_number, raw_line) in enumerate(thelong_rw_origins):
            _record_origin('thelong', 'Rewrite', index, filename, line_number, raw_line)
        indices = {'Rewrite': 0, 'Script': 0, 'Rule': 0}
        for filename in sorted(x for x in os.listdir(args.apps)
                               if x.endswith('.plugin')
                               and (x.endswith('_ad_block.plugin') or x.endswith('_splash_ad_block.plugin'))
                               and not x.startswith('ai_auto_node')):
            path = os.path.join(args.apps, filename)
            for section, line_number, raw_line in _raw_rows(path):
                if section not in indices or section == 'Rewrite':
                    continue
                _record_origin('thelong', section, indices[section], filename,
                               line_number, raw_line)
                indices[section] += 1

    if args.aoomee:
        pdir = os.path.join(args.aoomee, 'plugins')
        if not os.path.isdir(pdir):
            pdir = args.aoomee

        # Use the retained origin list after semantic duplicate filtering.
        # Recounting all upstream rows here would include excluded entries and
        # shift every later source index, even though ao_rw no longer contains them.
        line_lookup = {}
        for filename in sorted(x for x in os.listdir(pdir)
                               if x.endswith('.plugin') or x.endswith('.lpx')):
            path = os.path.join(pdir, filename)
            current_section = None
            section_indices = collections.defaultdict(int)
            with open(path, encoding='utf-8') as source_handle:
                for line_number, raw in enumerate(source_handle, 1):
                    section_match = re.match(r'^\[(.+?)\]\s*$', raw)
                    if section_match:
                        current_section = section_match.group(1).strip()
                        continue
                    value = raw.strip()
                    if current_section and value and not value.startswith('#'):
                        section_index = section_indices[current_section]
                        line_lookup[(filename, current_section, section_index)] = line_number
                        section_indices[current_section] += 1

        for feed_index, (filename, original_section, section_index, raw_line) in enumerate(ao_rw_origins):
            line_number = line_lookup.get((filename, original_section, section_index))
            if line_number is None:
                raise RuntimeError(
                    'aoomee Rewrite provenance cannot locate retained source row: '
                    + filename + ':' + original_section + ':' + str(section_index)
                )
            _record_origin(
                'aoomee', 'Rewrite', feed_index,
                ('plugins/' if pdir.endswith('/plugins') else '') + filename,
                line_number, raw_line, original_section=original_section
            )

    if args.zmjde:
        pdir = os.path.join(args.zmjde, 'Plugin')
        if not os.path.isdir(pdir):
            pdir = args.zmjde
        indices = {'Rewrite': 0, 'Script': 0, 'Rule': 0}
        for filename in _ZMJ_APP:
            path = os.path.join(pdir, filename)
            for section, line_number, raw_line in _raw_rows(path):
                if section not in indices:
                    continue
                _record_origin('zmjapp', section, indices[section],
                               ('Plugin/' if pdir.endswith('/Plugin') else '') + filename,
                               line_number, raw_line)
                indices[section] += 1

    rw_provenance_feeds = [(source, priority, lines, 'Rewrite')
                           for source, priority, lines in rw_feeds]
    sc_provenance_feeds = [(source, priority, lines, 'Script')
                           for source, priority, lines in sc_feeds]
    sc_provenance_feeds += [
        (source, priority,
         [line for line in lines if unguarded_key(line) is not None], 'Rewrite')
        for source, priority, lines in rw_feeds
    ]
    rewrite_provenance = _section_provenance(
        rw_provenance_feeds, merged_rw, 'Rewrite')
    script_provenance = _section_provenance(
        sc_provenance_feeds, merged_sc, 'Script')
    # Fail closed if an AOOMEE source origin no longer describes the exact
    # flattened feed entry. This catches line-index drift before publication.
    for provenance_record in rewrite_provenance:
        for source_row in provenance_record.get('sources', []):
            if source_row.get('source') != 'aoomee':
                continue
            raw_line = source_row.get('source_raw_line')
            input_line = source_row.get('input_line')
            original_section = source_row.get('source_original_section')
            if not raw_line or not input_line or not original_section:
                raise RuntimeError('aoomee Rewrite provenance is missing source-origin fields: '
                                   + provenance_record.get('output_line', ''))
            expected_line = (convert_shadowrocket_line(raw_line)
                             if original_section == 'Rewrite' else raw_line.strip())
            if expected_line != input_line:
                raise RuntimeError(
                    'aoomee Rewrite provenance source-origin mismatch: '
                    + str(source_row.get('source_file')) + ':'
                    + str(source_row.get('source_line_number')) + ' -> '
                    + provenance_record.get('output_line', '')
                )
    rule_output_index = {line: index for index, line in enumerate(rule_items, 1)}
    for event in rule_provenance_events:
        origin = source_origins.get((event.get('source'), 'Rule', event.get('source_entry_index')))
        if origin:
            event.update(origin)
        if event.get('status') == 'included':
            event['output_entry_index'] = rule_output_index.get(event['output_line'])
    for adjustment in rule_scope_adjustments:
        matches = [
            event for event in rule_provenance_events
            if event.get('source') == adjustment['source']
            and event.get('original_input_line') == adjustment['output_line']
        ]
        if len(matches) != 1:
            raise RuntimeError(
                '百度网盘 advlion.com QUIC 补充规则来源追溯不唯一：'
                + adjustment['output_line']
            )
        matches[0].update({
            'source_file': adjustment['source_file'],
            'source_original_section': 'MITM-derived Rule',
            'generated_from_mitm_host': adjustment['mitm_host'],
            'generated_from_related_rule': adjustment['related_existing_rule'],
        })
    upstream_revisions = {}
    if args.source_report and os.path.isfile(args.source_report):
        try:
            with open(args.source_report, encoding='utf-8') as source_file:
                upstream_revisions = json.load(source_file)
        except (OSError, ValueError) as exc:
            raise SystemExit('来源追溯无法读取 source-report: %s' % exc)
    rule_report = {
        'schema_version': 1,
        'upstream_revisions': upstream_revisions,
        'repository': 'XcvcvX/loon-change',
        'scope': ['Rewrite', 'Script', 'Rule'],
        'rewrite_exclusions': zhangle_rewrite_exclusions + zhangle_block_rewrite_exclusions + mgtv_unused_indexes_rewrite_exclusions + block_rewrite_exclusions + lite_advertising_rewrite_exclusions + ttjj_start_image_rewrite_exclusions + thelong_duplicate_exclusions + aoomee_duplicate_exclusions,
        'mitm_exclusions': block_mitm_exclusions + zhangle_mitm_exclusions,
        'scope_adjustments': block_scope_adjustments,
        'rule_scope_adjustments': rule_scope_adjustments,
        'limitations': [
            'source_entry_index is the ordinal within the extracted source feed, not the original upstream file line number',
            'exact source filename and 1-based line attribution is included for Thelongdarkorg, aoomee, and zmjde App plugin feeds; other sources retain feed indices until their source mapping is added',
            'normalization and source conversion may mean input_line differs from upstream raw text',
            'MITM hostname provenance and Argument provenance are not included in this first batch',
            'provenance does not prove that a rule is effective or safe at runtime'
        ],
        'source_catalog': {
            'base': 'R-Store converted rewrite source',
            'block': 'fmz200/wool_scripts blockAdsV2',
            'zmjgen': 'zmjde/loon-plugins general plugins',
            'thelong': 'Thelongdarkorg/loon-plugins',
            'aoomee': 'aoomee/Loon-Adblock-Plugins',
            'qxapp': 'QuanX single-file app source (GuaZiVideoAds)',
            'amap': 'ifflagged/Romeo / RuCu6 Amap plugin',
            'zmjapp': 'zmjde/loon-plugins app plugins',
            'myblockads': 'RuCu6 MyBlockAds',
            'filter': 'zirawell/R-Store allAdBlock filter'
        },
        'summary': {
            'rewrite_output_entries': len(rewrite_provenance),
            'script_output_entries': len(script_provenance),
            'rule_output_entries': len(rule_items),
            'rule_source_events': len(rule_provenance_events),
            'rule_included_events': sum(1 for event in rule_provenance_events
                                        if event['status'] == 'included'),
            'rule_covered_or_duplicate_events': sum(
                1 for event in rule_provenance_events
                if event['status'] in ('duplicate_exact', 'covered_by_existing_rule')),
            'rule_safety_excluded_events': sum(
                1 for event in rule_provenance_events
                if event['status'] == 'excluded_safety_guard'),
            'rule_scope_adjustments': len(rule_scope_adjustments),
        },
        'rewrite': rewrite_provenance,
        'script': script_provenance,
        'rule_events': rule_provenance_events,
    }
    with open(args.provenance_out, 'w', encoding='utf-8') as provenance_file:
        json.dump(rule_report, provenance_file, ensure_ascii=False, indent=2)
        provenance_file.write('\n')
    print('[provenance] 已生成逐条来源追溯:', args.provenance_out)

open(args.out, 'w', encoding='utf-8').write('\n'.join(out))

print('\n[merge] 输出:', args.out)
print('  Rewrite：%d 条；Script：%d 条（含 generic/cron 无守卫行）'
      % (len(merged_rw), len(merged_sc)))
print('  Rule   ：%d 条；Argument：%d 个开关' % (len(rule_items), len(arg_items)))
if args.amap:
    print('  高德 App：Rewrite %d / Script %d / Rule %d / MITM %d（priority=-1，最高）'
          % (len(amap_rw), len(amap_sc), len(amap_rule), len(amap_mitm)))
print('  Rule 来源：aoomee 新增 %d（跳过 %d）；thelong 新增 %d（跳过 %d）；'
      'block 新增 %d（跳过 %d）'
      % (rule_counts['aoomee_add'], rule_counts['aoomee_dup'],
         rule_counts['thelong_add'], rule_counts['thelong_dup'],
         rule_counts['block_add'], rule_counts['block_dup']))
if args.filter != 'none':
    print('  分流补全：R-Store %d 条，已覆盖 %d，补入 %d'
          % (fstats['total'], fstats['covered'], fstats['added']))
print('  MITM   ：%d 个主机（无法收敛丢弃 %d，IP 地址清理 %d，自动裁剪无动作 %d）'
      % (len(mitm), len(dropped), len(mitm_ip_dropped), mitm_pruned))
if mitm_pruned:
    print('  MITM 自动裁剪：移除 %d 个不服务任何规则、仅解密的冗余 host' % mitm_pruned)
print('  MITM 自愈补全 %d 个%s' % (
    len(mitm_healed), '：' + ', '.join(mitm_healed[:15]) if mitm_healed else ''))
if dropped:
    print('  丢弃的 hostname：', ', '.join(dropped[:20]))
