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
import argparse, datetime, ipaddress, os, re, sys, urllib.request

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

# 第三方融合插件（APP启动页去广告ultra+）：QuanX/Shadowrocket 段名，需清洗后并入去重
MIX_URL = 'https://yfamilys.com/plugin/adultraplus.plugin'

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
HOST_OK = re.compile(r'^(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$')
IP_OK = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')

# 真实 TLD 白名单：用于 hostname 收敛时排除缺 TLD 的非法项、可选组截断的残缺 host
_KNOWN_TLD = {
    'com', 'net', 'org', 'gov', 'edu', 'mil', 'asia', 'app', 'io', 'me', 'cc', 'tv', 'co', 'info',
    'so', 'group', 'ltd',
    'xyz', 'top', 'vip', 'shop', 'site', 'online', 'store', 'tech', 'dev', 'ai', 'cloud', 'live',
    'press', 'pro', 'name', 'mobi', 'biz', 'club', 'fun', 'games', 'news', 'blog', 'wiki', 'link',
    'run', 'space', 'today', 'work', 'design', 'media', 'world', 'life', 'health', 'art', 'photo',
    'video', 'chat', 'plus', 'one', 'cn', 'hk', 'tw', 'jp', 'us', 'uk', 'de', 'fr', 'kr', 'sg',
    'au', 'ca', 'ru', 'br', 'in', 'it', 'es', 'nl', 'se', 'no', 'fi', 'dk', 'ch', 'at', 'be',
    'nz', 'ie', 'pt', 'gr', 'pl', 'tr', 'mx', 'ar', 'za', 'th', 'vn', 'my', 'ph', 'id', 'il',
    'sa', 'ae', 'cz', 'hu', 'ro', 'sk', 'bg', 'hr', 'lt', 'lv', 'ee', 'si', 'is', 'lu', 'mt',
}

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True, help='base 插件（R-Store 产物）')
ap.add_argument('--extra', required=True,
                help='blockAdsV2 路径；传 fetch 则从上游拉取（含镜像回退）')
ap.add_argument('--filter', default='fetch',
                help='R-Store 分流来源：fetch（默认，含镜像）/ 本地路径 / none（不补全 [Rule]）')
ap.add_argument('--apps', default=None,
                help='Thelongdarkorg/loon-plugins 仓库目录（可选）；遍历其中去广告插件并入，'
                     '仅识别 *_ad_block.plugin / *_splash_ad_block.plugin，跳过 ai_auto_node')
ap.add_argument('--mix', default=None,
                help='第三方融合插件（adultraplus）：fetch/URL/本地路径；清洗（只取去广告 reject+v2，'
                     '剔除重定向/破解私货）后按正则去重并入')
ap.add_argument('--aoomee', default=None,
                help='aoomee/Loon-Adblock-Plugins 仓库目录（工作流 clone 后传入）；遍历其中 '
                     '.plugin/.lpx 独立 App 插件并入，独立 App 插件优先级最高（同正则替换其他来源）')
ap.add_argument('--zmjde', default=None,
                help='zmjde/loon-plugins 仓库目录（工作流 clone 后传入）；读取其中 4 个指定 .lpx：'
                     'DiDi/PinDuoDuo 作为 App 高优先级完整并入，Block_HTTPDNS/BlockAdvertisers 以 base 优先只补不覆盖')
ap.add_argument('--qxapp', action='append', default=None,
                help='QuanX 单文件 App 插件（.conf，如瓜子影视）本地路径，可重复传入；'
                     '脚本内解析 hostname 并把 qx 规则转为 Loon v2，按专属 App 高优先级完整并入')
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


def fetch_mix(url, retries=12):
    """adultraplus 站走 Cloudflare、连接易随机切断且忽略 Range（无法断点续传），
    需多次重试，直到某次完整读取（read 不抛异常）。"""
    import gzip, time
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip', 'Connection': 'close'})
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
            return raw.decode('utf-8')
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError('mix 下载失败: %s' % last)


def parse_mix_sections(text):
    """宽松段名解析，识别 [URL Rewrite] 等含空格段名（split_sections 只认单词段），
    返回 {段名: [行]}（不含空行/注释）。"""
    out, cur = {}, None
    for line in text.split('\n'):
        m = re.match(r'^\[(.+?)\]\s*$', line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur is not None and line.strip() and not line.lstrip().startswith('#'):
            out[cur].append(line)
    return out


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
def guard_hosts_from_lines(lines):
    """从 Rewrite/Script 守卫提取 Loon 合法 hostname 集合：
    - 完整明确 host：要求 HOST_OK 且最后标签在真实 TLD 白名单；
    - 含通配/OR 的守卫：退化为 *.末尾连续字面标签（只取纯字面标签，不臆造）；
    只取 then/script-path 之前的守卫（排除 jq body 与脚本资源地址）；
    自动排除裸 IP、通配 IP 与仅 http:// 的 host。"""
    https, http_only = set(), set()
    for l in lines:
        head = l.split(' then ', 1)[0].split('script-path=', 1)[0]
        clean = head.replace('\\/', '/').replace('\\.', '.')
        for proto, zone in re.findall(r'(https?\??)://([^/\s]+)', clean):
            result = None
            # 1) 完整字面 host
            if HOST_OK.match(zone) and zone.rsplit('.', 1)[-1] in _KNOWN_TLD:
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
                if (len(lit) >= need and lit[-1] in _KNOWN_TLD
                        and not is_public_suffix('.'.join(lit[-need:]))):
                    result = '*.' + '.'.join(lit)
            if not result:
                continue
            if proto == 'http':
                http_only.add(result)
            else:                                 # https 或 https?：可能走 TLS
                https.add(result)
                http_only.discard(result)
    return https - http_only


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
    裸 IP / 通配 IP 丢弃；缺 TLD / 通配 TLD 项先字符串收敛，失败再用守卫真实 host 反查。"""
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
        return x.rsplit('.', 1)[-1] in _KNOWN_TLD

    out = []
    # 具体域名
    if '*' not in h and '?' not in h:
        if HOST_OK.match(h) and has_real_tld(h) and not is_public_suffix(h):
            out = [h]
    # 标准 *.后缀
    elif h.startswith('*.') and '*' not in h[2:] and '?' not in h[2:]:
        if HOST_OK.match(h[2:]) and has_real_tld(h) and not is_public_suffix(h[2:]):
            out = [h]
    # 中间/前缀通配（m*.amap.com、*-spclient、*default...）：退化为 *.最长字面后缀
    else:
        lit = []
        for lab in reversed([x for x in h.split('.') if x]):
            if '*' in lab or '?' in lab:
                break
            lit.append(lab)
        lit = lit[::-1]
        need = 3 if '.'.join(lit[-2:]).lower() in PUBLIC_SUFFIX_2L else 2
        res = '*.' + '.'.join(lit)
        if (len(lit) >= need and re.match(r'^\*\.[A-Za-z0-9\-\.]+$', res)
                and has_real_tld(res) and not is_public_suffix('.'.join(lit[-need:]))):
            out = [res]

    # 字符串无法安全收敛（缺 TLD 等）：用守卫真实 host 反查，不臆造 TLD
    if not out and guard_hosts:
        out = host_wildcard_resolve(guard_pat, guard_hosts)
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
# 优先级（数字小=高）：zmjde App(0) > aoomee(1) > Thelongdarkorg(2) > base/R-Store(3)
#                     > blockAdsV2(4) > zmjde 通用(5) > adultraplus(6)
# DiDi/PinDuoDuo（zmjde App）完整并入、同正则替换其他来源；
# Block_HTTPDNS/BlockAdvertisers（zmjde 通用）低于 base，只补 base 没有的。
# ============================================================================
import collections

# ---------------- 读取 base / extra ----------------
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

# ---------------- legacy 旧行转换（blockAdsV2 / adultraplus 复用）----------------
_LEGACY_REJECT = {
    'reject': 'reject(404)', 'reject-200': 'reject(200)',
    'reject-img': 'reject_img(200)', 'reject-dict': 'reject_dict(200)',
    'reject-array': 'reject_array(200)', 'reject-video': 'reject_video(200)',
}


def convert_legacy_line(line):
    """把 QuanX 旧写法转成 Loon v2；无法安全转换返回 None（丢弃）。"""
    s = line.strip()
    toks = s.split()
    if len(toks) == 2 and toks[1] in _LEGACY_REJECT:
        return ('request if ${url} ~= /%s/ then %s'
                % (toks[0], _LEGACY_REJECT[toks[1]]))
    if s.endswith(' 302') and 'close_ad=' in s:
        m = re.match(r'^(\^.+?)\s+\$1true\$2\s+302$', s)
        if m:
            return ('request if ${url} ~= /%s/ as m then redirect(302, "${m.1}true${m.2}")'
                    % m.group(1))
    m = re.match(r'^(\^.+?)\s+302\s+(\S+)$', s)
    if m and 'zhihu' in s:
        tgt = m.group(2).replace('$1', '${m.1}')
        return ('request if ${url} ~= /%s/ as m then redirect(302, "%s")'
                % (m.group(1), tgt))
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


# ---------------- 动作签名：区分"拒绝家族折叠"与"互补动作并存" ----------------
def split_action(line):
    """返回 (v2/v1, 动作部分)。v2 取 then 之后；v1 去掉首段正则。"""
    s = line.strip()
    if re.match(r'^(request|response)\b', s) and ' then ' in s:
        return 'v2', s.split(' then ', 1)[1].strip()
    head = s.split(None, 1)[0]
    return 'v1', s[len(head):].strip()


def action_key(line):
    """拒绝家族（reject/reject-*/reject(_*)）同正则折叠为一个签名；
    其余动作按 (动作名, 完整动作) 独立，互补动作（jq+header-del 等）得以并存。"""
    _, action = split_action(line)
    if re.match(r'^reject', action):
        return ('REJECT',)
    name = re.split(r'[\s(]', action, 1)[0]
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
# blockAdsV2
block_rw = prep_block_lines(extra_sec.get('Rewrite', []))
block_sc = prep_block_lines(extra_sec.get('Script', []))
# Thelongdarkorg（标准 v1，直接保留）
thelong_rw, thelong_sc = [], []
thelong_rule, thelong_mitm = [], []
if args.apps:
    for fname, atext in iter_app_plugins(args.apps):
        _, s = split_sections(atext)
        thelong_rw += real_lines(s.get('Rewrite', []))
        thelong_sc += real_lines(s.get('Script', []))
        thelong_rule += real_lines(s.get('Rule', []))
        for l in s.get('MITM', []):
            if '=' in l:
                thelong_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# aoomee（v1/v2 混合；URL Rewrite 的 reject 并入 Rewrite；generic/cron 由合并器识别）
ao_rw, ao_sc, ao_rule, ao_mitm = [], [], [], []
if args.aoomee:
    for fname, s in iter_aoomee(args.aoomee):
        ao_rw += [convert_shadowrocket_line(l)
                  for l in real_lines(s.get('Rewrite', []))]
        for l in real_lines(s.get('URL Rewrite', [])):
            toks = l.split()
            if len(toks) == 2 and toks[1] in _LEGACY_REJECT:
                ao_rw.append(l)
        ao_sc += [convert_shadowrocket_line(l)
                  for l in real_lines(s.get('Script', []))]
        ao_rule += real_lines(s.get('Rule', []))
        for l in s.get('MITM', []):
            if '=' in l:
                ao_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# adultraplus（清洗：只取去广告 reject+v2，剔除私货）
mix_rw, mix_sc, mix_mitm = [], [], []
mix_guard_lines = []
mix_stats = {'rw_added': 0, 'sc_added': 0, 'non_ad_drop': 0}
if args.mix:
    if args.mix == 'fetch':
        mtext = fetch_mix(MIX_URL)
        print('[fetch] 已获取 adultraplus（含重试）')
    elif args.mix.startswith('http'):
        mtext = fetch_mix(args.mix)
        print('[fetch] 已获取 mix:', args.mix)
    else:
        mtext = open(args.mix, encoding='utf-8').read()
    mix_sec = parse_mix_sections(mtext)
    mix_guard_lines = (real_lines(mix_sec.get('URL Rewrite', []))
                       + real_lines(mix_sec.get('Rewrite', []))
                       + real_lines(mix_sec.get('Script', [])))
    for l in real_lines(mix_sec.get('URL Rewrite', [])):
        toks = l.split()
        if len(toks) != 2 or toks[1] not in _LEGACY_REJECT:
            mix_stats['non_ad_drop'] += 1
            continue
        mix_rw.append(convert_legacy_line(l))
    mix_rw += real_lines(mix_sec.get('Rewrite', []))
    mix_sc += real_lines(mix_sec.get('Script', []))
    for l in mix_sec.get('MITM', []):
        if '=' in l:
            mix_mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]

# ---------------- zmjde 四个指定插件 ----------------
# DiDi/PinDuoDuo：App 高优先级（完整并入，同正则替换其他来源）；
# Block_HTTPDNS/BlockAdvertisers：base 优先，只补 base 没有的（不覆盖）。
_ZMJ_APP = ('DiDi_remove_ads.lpx', 'PinDuoDuo_remove_ads.lpx')
_ZMJ_GENERAL = ('Block_HTTPDNS.lpx', 'BlockAdvertisers.lpx')
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
# 位置顺序：base 骨架 -> block -> zmjde通用 -> mix -> thelong -> aoomee -> qx单文件App -> zmjdeApp；
# 同正则由 prio 决定覆盖（zmjde App 最高，qx 专属 App 次之；zmjde 通用低于 base、只补不覆盖）
rw_feeds = [('base', 4, base_rw), ('block', 5, block_rw), ('zmjgen', 6, zmj_gen_rw),
            ('mix', 7, mix_rw), ('thelong', 3, thelong_rw), ('aoomee', 2, ao_rw),
            ('qxapp', 1, qxapp_rw), ('zmjapp', 0, zmj_app_rw)]
sc_feeds = [('base', 4, base_sc), ('block', 5, block_sc), ('zmjgen', 6, zmj_gen_sc),
            ('mix', 7, mix_sc), ('thelong', 3, thelong_sc), ('aoomee', 2, ao_sc),
            ('zmjapp', 0, zmj_app_sc)]
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
_RT_NORM = {'domain': 'DOMAIN', 'ip-cidr': 'IP-CIDR', 'domainsuffix': 'DOMAIN-SUFFIX'}
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


def add_rule(line, src):
    line = normalize_rule(line)
    if line in rule_result:
        rule_counts[src + '_dup'] += 1
        return
    t = line.split(',')[0]
    if t in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6'):
        if rule_is_covered(line, rule_idx):
            rule_counts[src + '_dup'] += 1
            return
        add_to_index(line, rule_idx)
    rule_result.append(line)
    rule_counts[src + '_add'] += 1


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
    for fr in dedup_keep_order(parse_qx_filter(ftext)):
        fstats['total'] += 1
        before = len(rule_result)
        add_rule(fr, 'filter')
        if len(rule_result) == before:
            fstats['covered'] += 1
        else:
            fstats['added'] += 1
rule_items = dedup_keep_order(rule_result)

# ---------------- MITM：base 主机 + 各来源收敛（守卫反查），再自愈 ----------------
mitm = []
for l in base_sec.get('MITM', []):
    if '=' in l:
        mitm += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
# 守卫真实 host：用最终 Rewrite/Script（含全部来源），供通配 TLD/缺 TLD 反查
guard_real = guard_hosts_from_lines(merged_rw + merged_sc)
extra_raw = []
for l in extra_sec.get('MITM', []):
    if '=' in l:
        extra_raw += [x.strip() for x in l.split('=', 1)[1].split(',') if x.strip()]
dropped = []
for h in extra_raw + thelong_mitm + ao_mitm + zmj_app_mitm + zmj_gen_mitm + qxapp_mitm + mix_mitm:
    got = normalize_extra_host(h, guard_real)
    if not got:
        dropped.append(h)
    else:
        mitm += got
mitm = dedup_keep_order(mitm)


def _mitm_covered(host, hostset):
    if host in hostset:
        return True
    return any(m.startswith('*.') and (host == m[2:] or host.endswith('.' + m[2:]))
               for m in hostset)


mitm_healed = []
# 必须同时扫描 Rewrite + Script（Script 段的 http(s)-request/response 守卫同样需要 MITM）
for _h in sorted(guard_hosts_from_lines(merged_rw + merged_sc)):
    if not _mitm_covered(_h, set(mitm)):
        mitm.append(_h)
        mitm_healed.append(_h)
mitm = dedup_keep_order(mitm)

# ---------------- 输出 ----------------
today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
header = [
    '#!name=R-Store × blockAdsV2 × 独立 App 去广告净化合集',
    '#!desc=合并 R-Store、blockAdsV2、Thelongdarkorg、aoomee、zmjde、ddgksf2013 瓜子、adultraplus；'
    '按 URL 正则去重，专属 App 插件优先、同正则替换综合源；[Rule] 已含多套分流，单插件自包含',
    '#!author=zirawell / fmz200 / Thelongdarkorg / aoomee / zmjde / ddgksf2013 / yfamilys（本仓库自动合并）',
    '#!homepage=https://github.com/XcvcvX/loon-change',
    '#!merged-at=%s' % today,
    '#!note=专属 App 插件（zmjde/qx 单文件/aoomee/Thelongdarkorg）优先级最高；新旧语法同段混用，Loon 均支持。',
    '#!sources=R-Store(QuanX->Loon)+blockAdsV2+Thelongdarkorg+aoomee+zmjde+ddgksf2013/GuaZiVideoAds+yfamilys/adultraplus',
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
open(args.out, 'w', encoding='utf-8').write('\n'.join(out))

print('\n[merge] 输出:', args.out)
print('  Rewrite：%d 条；Script：%d 条（含 generic/cron 无守卫行）'
      % (len(merged_rw), len(merged_sc)))
print('  Rule   ：%d 条；Argument：%d 个开关' % (len(rule_items), len(arg_items)))
print('  Rule 来源：aoomee 新增 %d（跳过 %d）；thelong 新增 %d（跳过 %d）；'
      'block 新增 %d（跳过 %d）'
      % (rule_counts['aoomee_add'], rule_counts['aoomee_dup'],
         rule_counts['thelong_add'], rule_counts['thelong_dup'],
         rule_counts['block_add'], rule_counts['block_dup']))
if args.filter != 'none':
    print('  分流补全：R-Store %d 条，已覆盖 %d，补入 %d'
          % (fstats['total'], fstats['covered'], fstats['added']))
print('  MITM   ：%d 个主机（无法收敛丢弃 %d）' % (len(mitm), len(dropped)))
if mitm_healed:
    print('  MITM 自愈补全 %d 个：%s' % (len(mitm_healed), ', '.join(mitm_healed[:15])))
if dropped:
    print('  丢弃的 hostname：', ', '.join(dropped[:20]))
if args.mix:
    print('  Mix    ：adultraplus 清洗，非去广告私货剔除 %d' % mix_stats['non_ad_drop'])
#（注：内容由AI生成）
