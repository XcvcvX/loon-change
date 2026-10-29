#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quantumult X rewrite (allAdRewrite.conf) -> Loon 原生插件(.plugin)
不是简单的字段顺序调换，而是按 Loon 官方语法做语义级映射：
  - 原子组 (?>...)  ->  非捕获组 (?:...)   （ICU 正则不支持原子组）
  - QuanX rewrite 脚本  ->  Loon [Script] 段 http-response/http-request
  - jq / echo-response / 302  ->  Loon 新版 Rewrite 语法
  - url request-header  -> header-replace-regex（按 Header 名改写，而非整块文本替换）

用法：
  python3 convert_qx2loon.py                          # 拉取上游最新规则，输出 allAdRewrite.plugin
  python3 convert_qx2loon.py -i local.conf -o out.plugin
"""
import argparse, collections, datetime, os, re, sys, urllib.request

# 上游 Quantumult X 规则源（zirawell/R-Store）
UPSTREAM = ('https://raw.githubusercontent.com/zirawell/R-Store/main/'
            'Rule/QuanX/Adblock/All/rewrite/allAdRewrite.conf')
# 上游不可达时的镜像
MIRRORS = [
    'https://cdn.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/rewrite/allAdRewrite.conf',
    'https://fastly.jsdelivr.net/gh/zirawell/R-Store@main/Rule/QuanX/Adblock/All/rewrite/allAdRewrite.conf',
]

ap = argparse.ArgumentParser()
ap.add_argument('-i', '--input', help='本地 QuanX 规则文件；不指定则从上游拉取')
ap.add_argument('-o', '--output', default='allAdRewrite.plugin', help='输出 .plugin 路径')
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

# ================= 二进制 body 脚本识别 =================
# Loon 中 http-response 脚本拿到的 $response.body 默认是字符串；
# 只有声明 binary-body-mode=true 时才是 Uint8Array。
# protobuf 类脚本（直接按字节 slice / DataView / fromBinary）若拿到字符串，
# 会解析失败、$done({}) 放空响应，导致 App 一直转圈（如 YouTube 首页刷不出）。
# 这些脚本需要 binary-body-mode=true：
BINARY_BODY_SCRIPTS = {
    'youtube.js',        # 自定义 protobuf 框架，fromBinary 要求 Uint8Array
    'bilibiliProtoA.js',  # protobuf，按字节 slice + ungzip
    'tiebaProto.js',      # 非 QuanX 分支直接把 $response.body 当字节
    'spotify.js',         # 同上
    'baiduMap.js',        # 同上，DataView 读取
}

# 内容启发式（强特征，命中即判定需二进制），用于覆盖未来新增的同类脚本
_BIN_PATTERNS = [
    re.compile(r'isQuanX\s*\?\s*new\s+Uint8Array\(\s*\$response\.bodyBytes\s*\)'
               r'\s*:\s*\$response\.body'),
    re.compile(r'can not get binaryBody'),
]


def _script_mirror(u):
    """raw.githubusercontent.com 不可达时，回退到 jsDelivr 取脚本内容"""
    m = re.match(r'^https?://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/(.+)$', u)
    if not m:
        return None
    return 'https://cdn.jsdelivr.net/gh/%s@%s' % (m.group(1), m.group(2))


def detect_binary_scripts():
    """结合"已知名单 + 内容启发式"，返回需要二进制 body 的脚本【文件名】集合。
    脚本下载为尽力而为：失败则只依赖已知名单，绝不阻塞转换。"""
    need = set(BINARY_BODY_SCRIPTS)
    js_urls = set(re.findall(
        r'script-(?:response|request)-(?:body|header)\s+(\S+)', raw))
    for u in sorted(js_urls):
        content, got = None, None
        for cand in [u, _script_mirror(u)]:
            if not cand:
                continue
            try:
                content = fetch(cand, timeout=15)
                got = cand
                break
            except Exception as e:
                last = e
        if content is None:
            print('[binary] 探测失败，跳过启发式: %s' % u, file=sys.stderr)
            continue
        if any(p.search(content) for p in _BIN_PATTERNS):
            need.add(os.path.basename(u))
            print('[binary] 启发式判定需二进制: %s (%s)' % (os.path.basename(u), got))
    return need


BINARY_NEEDED = detect_binary_scripts()

lines = raw.split('\n')

# 上游标注"⚠️域名[xxx]可能导致功能异常，请自行选择"的主机：默认不自动补全，
# 交由用户自行决定是否启用（属于上游故意默认关闭，不是缺口）
WARNING_HOSTS = set(re.findall(r'域名\[([A-Za-z0-9.\-]+)\]', raw))

rewrite, scripts, skipped = [], [], []
mitm_hosts = []
stats = collections.Counter()
tag_count = collections.Counter()
cur_code = 'AD'

REJECTS = {'reject', 'reject-200', 'reject-img', 'reject-dict', 'reject-array'}


def fix_re(s):
    """ICU 正则不支持原子组 (?>)，统一降级为 (?:)；顺带修正源文件中的转义笔误"""
    s = s.replace('(?>', '(?:')
    s = s.replace('.\\c', '\\.c')      # 源文件笔误：res\.kfc\.com.\cn -> res\.kfc\.com\.cn
    return s


def sp(s):
    """legacy 语法按空格切分参数，值里的空格需写成 \\x20"""
    return s.replace(' ', r'\x20')


def relit(s):
    """转成新语法的正则字面量 /pattern/ ，未转义的 / 需转义"""
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            out.append(s[i:i + 2]); i += 2
        elif s[i] == '/':
            out.append(r'\/'); i += 1
        else:
            out.append(s[i]); i += 1
    return '/' + ''.join(out) + '/'


def make_tag(code):
    tag_count[code] += 1
    return code if tag_count[code] == 1 else '%s-%d' % (code, tag_count[code])


def upstream_302_fix(s, urlre, target):
    """定向修正上游已知缺陷（仅匹配特征，不污染通用逻辑）。
    Spotify artistview 规则上游用了原子组 (?>...) 当子域名，而原子组不捕获，
    导致 $1 实际是端口组 (:443)?、$2 才是 artist，拼出 https://.spotify.com/... 非法URL。
    改为显式捕获子域名、端口组改非捕获，使 $1=子域名、$2=artist。"""
    if 'spotify' in s and 'artistview' in s and 'platform=iphone' in s:
        urlre = (r'^https?:\/\/(gae2-spclient|guc3-spclient|spclient\.wg)'
                 r'\.spotify\.com(?::443)?\/artistview\/v1\/artist\/(.*)&platform=iphone')
        target = 'https://$1.spotify.com/artistview/v1/artist/$2&platform=ipad'
        return urlre, target
    return urlre, target


for line in lines:
    s = line.strip()

    # ---- 空行 ----
    if not s:
        rewrite.append('')
        continue

    # ---- App 分组注释：提取代号用于脚本 tag ----
    m = re.match(r'^#\s*>\s*(.+?)\s*[-–]\s*([A-Za-z0-9_]+)\s*$', s)
    if m:
        cur_code = m.group(2)
        rewrite.append(line.rstrip())
        continue

    # ---- 其它注释 ----
    if s.startswith('#'):
        if s.startswith('#!'):
            continue          # QuanX 元数据头/策略说明，头部已重写，丢弃避免误导
        rewrite.append(line.rstrip())
        continue

    # ---- MitM 主机名 ----
    if s.startswith('hostname'):
        for h in s.split('=', 1)[1].split(','):
            h = h.strip()
            if h:
                mitm_hosts.append(h)
        continue

    # ---- 规则行：<url-regex> url <action> ... ----
    m = re.match(r'^(\S+)\s+url\s+(.+)$', s)
    if not m:
        # <url-re> <body-re> url-and-header <action> 这类复合匹配
        m2 = re.match(r'^(\S+)\s+(\S+)\s+url-and-header\s+(\S+)$', s)
        if m2:
            skipped.append((s, 'url-and-header 为 QuanX 复合匹配(URL+Header)，Loon 无对应动作'))
            stats['url-and-header(跳过)'] += 1
            continue
        skipped.append((s, '无法解析'))
        stats['无法解析'] += 1
        continue

    urlre, rest = fix_re(m.group(1)), m.group(2)
    act = rest.split(' ')[0].split('\t')[0]

    # ===== 1. reject 系列 =====
    if act in REJECTS and rest.strip() == act:
        rewrite.append('%s %s' % (urlre, act))
        stats[act] += 1
        continue

    # ===== 2. 脚本类 -> [Script] 段 =====
    m = re.match(r'^(script-response-body|script-request-body|script-request-header|script-response-header)\s+(\S+)$', rest)
    if m:
        kind, js = m.group(1), m.group(2)
        if kind.startswith('script-response'):
            phase = 'http-response'
        else:
            phase = 'http-request'
        tag = make_tag(cur_code)
        binflag = ',binary-body-mode=true' if os.path.basename(js) in BINARY_NEEDED else ''
        scripts.append('%s %s script-path=%s,tag=%s,requires-body=true%s'
                       % (phase, urlre, js, tag, binflag))
        stats[kind + ' -> ' + phase] += 1
        continue

    # ===== 3. 响应体正则替换 =====
    m = re.match(r'^response-body\s+(.+?)\s+response-body\s+(.+)$', rest)
    if m:
        frm, to = fix_re(m.group(1)), m.group(2)
        rewrite.append('%s response-body-replace-regex %s %s' % (urlre, sp(frm), sp(to)))
        stats['response-body -> response-body-replace-regex'] += 1
        continue

    # ===== 4. jq（改用新语法：表达式含空格，legacy 按空格切分会解析失败）=====
    m = re.match(r"^jsonjq-response-body\s+'(.*)'\s*$", rest) or \
        re.match(r"^jsonjq-response-body\s+'?(.*?)'?$", rest)
    if m:
        jq = m.group(1)
        if '`' in jq:
            jq = jq.replace('`', '``')
        rewrite.append('response if ${url} ~= %s then response.json.jq(`%s`)'
                       % (relit(urlre), jq))
        stats['jsonjq -> 新语法 response.json.jq'] += 1
        continue

    # ===== 5. echo-response（返回固定数据文件，用新语法 mock_file 直连远程 URL）=====
    m = re.match(r'^echo-response\s+(\S+)\s+echo-response\s+(\S+)$', rest)
    if m:
        ctype, url = m.group(1), m.group(2)
        dt = 'json' if 'json' in ctype.lower() else ctype
        rewrite.append('response if ${url} ~= %s then response.body.mock_file("%s", "%s", 200)'
                       % (relit(urlre), dt, url))
        stats['echo-response -> 新语法 response.body.mock_file'] += 1
        continue

    # ===== 6. 302（用新语法 redirect，可用捕获组 ${m.n} 还原 $1/$2）=====
    m = re.match(r'^302\s+(\S+)$', rest)
    if m:
        target = m.group(1)
        urlre, target = upstream_302_fix(s, urlre, target)
        n = len(re.findall(r'\(\?:(?!\?)|(?<!\\)\((?!\?)', urlre))
        target = re.sub(r'\$(\d)', r'${m.\1}', target)
        if '$' in target:
            rewrite.append('request if ${url} ~= %s as m then redirect(302, "%s")'
                           % (relit(urlre), target))
            stats['302 -> 新语法 redirect(302)'] += 1
        else:
            rewrite.append('%s 302 %s' % (urlre, target))
            stats['302'] += 1
        continue

    # ===== 7. 请求体替换 =====
    m = re.match(r'^request-body\s+(.+?)\s+request-body\s+(.+)$', rest)
    if m:
        frm, to = fix_re(m.group(1)), m.group(2)
        rewrite.append('%s request-body-replace-regex %s %s' % (urlre, sp(frm), sp(to)))
        stats['request-body -> request-body-replace-regex'] += 1
        continue

    # ===== 8. 请求头整块替换 -> 按名改写 =====
    m = re.match(r'^request-header\s+(.+?)\s+request-header\s+(.+)$', rest)
    if m:
        repl = m.group(2)
        # 替换值形如 $1Accept-Language: en-us$2，需剔除反向引用再取头名/值
        hm = re.search(r'([A-Za-z][A-Za-z0-9\-]*)\s*:\s*([^\s\\$]*)', repl)
        if hm and ':' in repl:
            hname, hval = hm.group(1), hm.group(2).strip()
            rewrite.append('%s header-replace-regex %s ^.*$ %s' % (urlre, hname, sp(hval) or 'en-us'))
            stats['request-header -> header-replace-regex'] += 1
        else:
            skipped.append((s, 'request-header 整块替换无法自动改写'))
            stats['request-header(跳过)'] += 1
        continue

    skipped.append((s, '未知动作: ' + act))
    stats['未知动作'] += 1


# ================= MitM 主机名规范化 =================
# Loon 的 hostname 仅支持：具体域名、*.后缀 通配、- 前缀排除。
# QuanX 允许中间/后缀通配（如 i*.hoopchina.com.cn、*tieba*.baidu.com），必须做语义收敛：
#   1) 优先从规则正则展开出具体域名
#      （如 cupid\.51job(app)?\.com -> cupid.51job.com / cupid.51jobapp.com）
#   2) 无法展开时退化为 *.最长字面后缀
#      （如 interface*.music.163.com -> *.music.163.com）
#   3) 绝不输出公共后缀（*.com.cn、*.net.cn 之类）——否则 Loon 会解密该后缀下
#      所有域名的流量，iOS 系统服务（如 p203-contacts.icloud.com.cn）校验证书
#      失败，就会弹“无法验证服务器身份”

# 常见两级公共后缀（其 registrable domain 需取三级）
PUBLIC_SUFFIX_2L = {
    'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'ac.cn', 'mil.cn',
    'com.hk', 'com.tw', 'com.au', 'com.sg', 'com.my', 'com.vn', 'com.ph',
    'com.br', 'com.mx', 'com.tr', 'co.jp', 'or.jp', 'ne.jp', 'ac.jp',
    'co.uk', 'org.uk', 'ac.uk', 'co.kr', 'or.kr', 'co.in', 'co.nz',
    'co.th', 'co.id',
}

HOST_OK = re.compile(r'^(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$')


def is_public_suffix(d):
    """裸 TLD 或已知两级公共后缀"""
    labels = d.split('.')
    if len(labels) == 1:
        return True
    return len(labels) == 2 and d.lower() in PUBLIC_SUFFIX_2L


def rule_host_regexes():
    """从规则行提取 host 部分正则，如 cupid\\.51job(app)?\\.com"""
    out, hp = [], re.compile(r'\^https\??:\\?/\\?/')
    for l in lines:
        if not l.startswith('^http'):
            continue
        m = hp.match(l)
        if not m:
            continue
        rest = l[m.end():]
        idx = [x for x in (rest.find('\\/'), rest.find(' ')) if x >= 0]
        # 原子组 (?>...) 先降级为 (?:...)，便于后续枚举“或”分支
        out.append(fix_re(rest[:min(idx)] if idx else rest))
    return out


def split_top(inner):
    """按顶层 | 切分（忽略嵌套括号与转义内的 |）"""
    parts, depth, cur, i = [], 0, '', 0
    while i < len(inner):
        ch = inner[i]
        if ch == '\\':
            cur += inner[i:i + 2]; i += 2; continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == '|' and depth == 0:
            parts.append(cur); cur = ''
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return parts


def expand_host_regex(hre, limit=12):
    """把简单的 host 正则展开为具体域名列表；遇 \\d/\\w/字符组/重复量词等不可枚举结构时返回 None"""
    variants, i, n = [''], 0, len(hre)
    while i < n:
        c = hre[i]
        if c == '\\':
            if i + 1 >= n or hre[i + 1] in 'dwsWSD':
                return None
            variants = [v + hre[i + 1] for v in variants]
            i += 2
        elif c == '(':
            j, depth = i + 1, 1
            while j < n and depth:
                if hre[j] == '\\':
                    j += 2
                    continue
                if hre[j] == '(':
                    depth += 1
                elif hre[j] == ')':
                    depth -= 1
                j += 1
            if depth:
                return None
            inner = hre[i + 1:j - 1]
            if inner.startswith('?:'):
                inner = inner[2:]        # 非捕获组：枚举“或”分支方式与捕获组相同
            elif inner.startswith('?'):
                return None              # (?i) 等其它扩展，host 里罕见，保守放弃
            opts = []
            for a in split_top(inner):
                ea = expand_host_regex(a, limit)
                if ea is None:
                    return None
                opts.extend(ea)
            if j < n and hre[j] == '?':
                opts.append('')          # (x)? 可选
                j += 1
            elif j < n and hre[j] in '*+':
                return None
            variants = [v + o for v in variants for o in opts]
            if len(variants) > limit:
                return None
            i = j
        elif c == '.':
            if i + 1 < n and hre[i + 1] in '*+':
                return None              # .* / .+ 不可枚举
            variants = [v + '.' for v in variants]   # host 里未转义的点按字面点处理
            i += 1
        elif c in '*+?[]{}':
            return None
        else:
            variants = [v + c for v in variants]
            i += 1
    return variants


def sample_host_regex(hre):
    """生成 host 正则的一个“样本串”（\\d->0, \\w->a, 取第一个分支……），
    用于判断该正则与某个通配 hostname 是否相关"""
    out, i, n = [], 0, len(hre)
    while i < n:
        c = hre[i]
        if c == '\\':
            nc = hre[i + 1] if i + 1 < n else ''
            if nc in 'dD':
                out.append('0')
            elif nc in 'wW':
                out.append('a')
            elif nc in 'sS':
                out.append(' ')
            else:
                out.append(nc)
            i += 2
        elif c == '(':
            j, depth = i + 1, 1
            while j < n and depth:
                if hre[j] == '\\':
                    j += 2
                    continue
                if hre[j] == '(':
                    depth += 1
                elif hre[j] == ')':
                    depth -= 1
                j += 1
            inner = hre[i + 1:j - 1]
            if inner.startswith('?') and len(inner) > 2 and inner[1] in ':>':
                inner = inner[2:]
            elif inner.startswith('?'):
                inner = ''
            out.append(split_top(inner)[0])
            if j < n and hre[j] in '?*+':
                j += 1
            i = j
        elif c == '[':
            j = hre.find(']', i)
            out.append('a')
            i = (j + 1) if j >= 0 else n
        elif c in '{':
            j = hre.find('}', i)
            i = (j + 1) if j >= 0 else n
        elif c == '.':
            out.append('.')
            i += 1
            if i < n and hre[i] in '*+':
                out.append('a')
                i += 1
        elif c in '?*+':
            if c == '?' and out:
                out.pop()
            elif c == '+' and out:
                out.append(out[-1])
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


HOST_RE_LIST = rule_host_regexes()
HOST_SAMPLES = [(r, sample_host_regex(r)) for r in HOST_RE_LIST]


def _concrete_of(hre):
    """一条 host 正则能枚举到的具体主机；不可枚举（\\d/\\w 等）返回 None"""
    ex = expand_host_regex(hre)
    if not ex:
        return None
    out = []
    for c in ex:
        c = c.rstrip('.')
        if HOST_OK.match(c) and not is_public_suffix(c) and c not in out:
            out.append(c)
    return out or None


# 每条规则的“全部具体主机”（含“或”组的所有分支），用于可靠判断 hostname 是否匹配规则
HOST_CONCRETE = [(r, _concrete_of(r)) for r in HOST_RE_LIST]

# 全部可枚举规则主机的集合（O(1) 查找），用于快速筛选 typo 候选
ALL_RULE_HOSTS = set()
for _, concrete in HOST_CONCRETE:
    if concrete:
        ALL_RULE_HOSTS.update(concrete)


def _glob_matches_samples(glob):
    """hostname glob（如 *.sohu.com）是否匹配至少一条规则。
    可枚举规则检查其【全部】具体主机（避免只取“或”组首分支导致误判），
    不可枚举规则退而检查其样本串。"""
    gre = re.compile('^' + re.escape(glob)
                     .replace(r'\*', '.*').replace(r'\?', '.') + '$', re.I)
    for hre, concrete in HOST_CONCRETE:
        if concrete:
            if any(gre.match(c) for c in concrete):
                return True
        else:
            sample = dict(HOST_SAMPLES)[hre]
            if gre.match(sample):
                return True
    return False


# 记录“hostname 拼写错误 -> 修正后”的修复，便于核对
typo_hosts = {}


def repair_hostname_typo(h):
    """修正上游 hostname 中的拼写错误（如 *.souhu.com 应为 *.sohu.com）。
    判定极保守：仅当该 hostname 不匹配任何规则、且存在唯一的“单字符编辑”
    （删除/替换/插入一个字母）版本能匹配规则时才修复；否则返回 None。
    候选筛选走 O(1) 集合查找，仅对最终候选做一次完整复核。"""
    pre, body = '', h
    if body.startswith('*.'):
        pre, body = '*.', body[2:]
    if '*' in body or '?' in body or not body:
        return None

    def _fast_match(c):
        """c（无通配的域名部分）是否对应到规则主机：通配候选看后缀，具体看集合"""
        if pre == '*.':
            return any(x == c or x.endswith('.' + c) for x in ALL_RULE_HOSTS)
        return c in ALL_RULE_HOSTS

    # 廉价集合初判；集合未命中（可能是不可枚举规则）再做一次完整检查
    if _fast_match(body) or _glob_matches_samples(h):
        return None

    cands = set()
    for i in range(len(body)):
        cands.add(body[:i] + body[i + 1:])              # 删除
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            if ch != body[i]:
                cands.add(body[:i] + ch + body[i + 1:])  # 替换
    for i in range(len(body) + 1):
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            cands.add(body[:i] + ch + body[i:])          # 插入
    good = sorted(c for c in cands if _fast_match(c))
    if len(good) == 1:
        final = pre + good[0]
        if _glob_matches_samples(final):                # 最终候选完整复核一次
            typo_hosts[h] = final
            return final
    return None

# 记录“缺 TLD 主机名 -> 补全后主机名”的修复，便于核对
repaired_hosts = {}


def _collect_rule_hosts():
    """从规则正则枚举全部具体域名（用于补全上游缺 TLD 的 hostname）"""
    out = set()
    for hre in HOST_RE_LIST:
        ex = expand_host_regex(hre)
        if ex:
            for c in ex:
                c = c.rstrip('.')
                if HOST_OK.match(c) and not is_public_suffix(c):
                    out.add(c)
    return out


RULE_CONCRETE_HOSTS = _collect_rule_hosts()


def repair_missing_tld(h):
    """上游个别 hostname 缺 TLD（如 img.yun.01zhuanche，应为 img.yun.01zhuanche.com）。
    真实 TLD 只含字母，故末段含数字即判定为缺 TLD。
    若规则里存在唯一的、以该串为前缀的具体域名，则补全；否则返回 None。"""
    cands = sorted(c for c in RULE_CONCRETE_HOSTS if c.startswith(h + '.'))
    if len(cands) == 1:
        repaired_hosts[h] = cands[0]
        return cands[0]
    return None


def concrete_from_rules(glob):
    """以源通配 hostname 作 glob，从规则正则展开具体域名。
    仅当【所有相关规则正则都可枚举】时才返回具体域名列表；
    只要有相关正则不可枚举（如 m\\d\\.amap\\.com），返回 None 走通配兜底，
    避免具体域名列表覆盖不全导致部分规则失效"""
    gre = re.compile('^' + re.escape(glob)
                     .replace(r'\*', '.*').replace(r'\?', '.') + '$', re.I)
    found = []
    for hre, sample in HOST_SAMPLES:
        if not gre.match(sample):
            continue                      # 与该通配无关的规则
        ex = expand_host_regex(hre)
        if ex is None:
            return None                   # 有相关规则不可枚举 -> 通配兜底
        for cand in ex:
            c = cand.rstrip('.')
            if HOST_OK.match(c) and not is_public_suffix(c) and gre.match(c) \
                    and c not in found:
                found.append(c)
    return found or None


def norm_host(h):
    """QuanX hostname -> Loon hostname 列表；无法安全收敛时返回空列表"""
    h = h.strip().strip('.')
    if not h:
        return []
    # 先修正 hostname 拼写错误（如 *.souhu.com -> *.sohu.com）
    fixed_typo = repair_hostname_typo(h)
    if fixed_typo:
        h = fixed_typo.strip('.')
    if h.endswith('.*'):
        h = h[:-2]
    if '*' not in h and '?' not in h:
        # 具体域名；单标签内部名（如 pangolin-sdk-toutiao）按源样保留
        if not re.match(r'^[A-Za-z0-9\-\.]+$', h):
            return []                  # 含 ? 以外的非法字符，丢弃
        if '.' not in h:
            return [h]
        if is_public_suffix(h):
            return []
        if not HOST_OK.match(h):
            # 末段不是合法 TLD（如 img.yun.01zhuanche 缺 .com）：尝试从规则补全
            fixed = repair_missing_tld(h)
            return [fixed] if fixed else []
        return [h]
    if h.startswith('*.') and '*' not in h[2:] and '?' not in h[2:]:
        return [] if is_public_suffix(h[2:]) else [h]
    # 中间/后缀通配（含 ? 单字符通配）：1) 先试从规则正则展开具体域名
    got = concrete_from_rules(h)
    if got:
        return got
    # 2) 退化为 *.最长字面后缀（公共后缀感知，绝不产出公共后缀）
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
    out = '*.' + '.'.join(lit)
    return [out] if re.match(r'^\*\.[A-Za-z0-9\-\.]+$', out) else []


seen, hosts, dropped_hosts, derived_hosts = set(), [], [], {}
for h in mitm_hosts:
    if h.startswith('-'):
        ent = ['-' + b for b in norm_host(h[1:])]
    else:
        ent = norm_host(h)
    if not ent:
        dropped_hosts.append(h)
        continue
    if '*' in h.strip('-') and len(ent) == 1 and '*' not in ent[0]:
        derived_hosts[h] = ent           # 记录通配 -> 具体的收敛，便于核对
    elif '*' in h.strip('-'):
        derived_hosts[h] = ent
    for n in ent:
        if n not in seen:
            seen.add(n)
            hosts.append(n)


def _host_is_covered(h):
    """具体主机 h 是否被已有 hostname（精确或 *.后缀 通配）覆盖"""
    for x in seen:
        if x == h:
            return True
        if x.startswith('*.') and (h == x[2:] or h.endswith('.' + x[2:])):
            return True
    return False


# ================= 补全“规则里有、但 hostname 整条缺失”的主机 =================
# 按【整条规则正则】判断：展开该正则的所有具体主机，
#   - 只要有一个已被覆盖，说明上游作者有意选择了部分变体（防御性写法），整条不碰；
#   - 全部未覆盖且不在警告名单 -> 上游漏写 hostname，补全，使规则真正生效。
auto_added = {}
for hre in HOST_RE_LIST:
    ex = expand_host_regex(hre)
    if not ex:
        continue
    concrete = []
    for c in ex:
        c = c.rstrip('.')
        if HOST_OK.match(c) and not is_public_suffix(c):
            concrete.append(c)
    if not concrete or any(_host_is_covered(c) for c in concrete):
        continue
    for c in concrete:
        if c in WARNING_HOSTS or c in seen:
            continue
        seen.add(c)
        hosts.append(c)
        auto_added[c] = hre


# ================= 输出 =================
# 沿用上游的 #!date，便于在 Loon 插件列表里直观看到上游版本
upstream_date = ''
upstream_count = ''
for l in lines[:20]:
    if l.startswith('#!date='):
        upstream_date = l.split('=', 1)[1].strip()
    if l.startswith('#!count='):
        upstream_count = l.split('=', 1)[1].strip()
if not upstream_date:
    upstream_date = datetime.date.today().isoformat()

HEAD = """#!name = 全部-广告拦截合集(Loon)
#!desc = R-Store 去广告规则，按 Loon 原生语法转换；部分规则需清除缓存或重装 App 才生效
#!author = zirawell(规则源)
#!homepage = https://github.com/zirawell/R-Store
#!icon = https://raw.githubusercontent.com/zirawell/R-Store/main/Res/Icon/Filter/AdBlock.png
#!system = iOS,iPadOS,macOS
#!loon_version = 3.5.1(978)
#!date = %s
#!tag = 去广告
#!type = normal
#%s
# 上游：https://github.com/zirawell/R-Store  （Quantumult X 版，每日更新）
#
# ============================ 转换说明 ============================
# 1. 原子组 (?>...) 在 Loon(ICU 正则) 中不被支持，已全部降级为 (?:...)
# 2. QuanX 的 rewrite 脚本已改写到 [Script] 段（http-response / http-request）
# 3. 动作映射：
#      reject/reject-200/reject-img/reject-dict/reject-array -> 同名动作(移至正则之后)
#      script-response-body      -> [Script] http-response  ... requires-body=true
#      script-request-body       -> [Script] http-request   ... requires-body=true
#        protobuf 类脚本（youtube/bilibiliProtoA/tiebaProto/spotify/baiduMap）
#        额外加 binary-body-mode=true，否则拿到字符串、解析失败会放空响应导致转圈
#      script-response-header    -> [Script] http-response
#      script-request-header     -> [Script] http-request
#      response-body A response-body B   -> response-body-replace-regex A B
#      request-body  A request-body  B   -> request-body-replace-regex  A B
#      request-header 整块替换           -> header-replace-regex <头名> ^.*$ <值>
# 4. 以下 3 类改用 Loon 新版 Rewrite 语法（官方允许新旧语法在同一 [Rewrite] 段混用）：
#      jsonjq-response-body 'jq'  -> response if ${url} ~= /re/ then response.json.jq(`jq`)
#        （legacy 按空格切分参数，而 jq 表达式含空格，用 \\x20 不可靠，故走新语法）
#      echo-response 类型 URL     -> ... then response.body.mock_file("json", "URL", 200)
#      url 302 URL(含 $1 引用)    -> ... as m then redirect(302, "...${m.1}...")
# 5. 注意：QuanX 的 reject 返回 404，Loon 的 reject 直接断开连接。
#    若某 App 出现网络错误提示，把对应条目改成 reject-200 即可。
# 6. 必须开启 MitM 并信任 CA 证书，否则所有规则不生效。
# =================================================================
""" % (upstream_date, ('  ' + upstream_count) if upstream_count else '')

out = [HEAD.rstrip('\n'), '', '[Rewrite]']
out = [HEAD.rstrip('\n'), '', '[Rewrite]']
out += rewrite
if skipped:
    out += ['', '# ---------- 以下规则无法 1:1 映射，已保留原文供手动处理 ----------']
    for s, why in skipped:
        out.append('# [%s] %s' % (why, s))
out += ['', '[Script]']
out += scripts
out += ['', '[MITM]', 'hostname = ' + ', '.join(hosts), '']

dst = args.output
d = os.path.dirname(os.path.abspath(dst))
if d:
    os.makedirs(d, exist_ok=True)
open(dst, 'w', encoding='utf-8').write('\n'.join(out))
print('\n输出:', dst)

print('=== 转换统计 ===')
for k, v in stats.most_common():
    print('%6d  %s' % (v, k))
print('\nRewrite 条目: %d' % len([x for x in rewrite if x.strip() and not x.strip().startswith('#')]))
print('Script  条目: %d' % len(scripts))
print('MitM  域名数: %d (原始 %d, 丢弃 %d)' % (len(hosts), len(mitm_hosts), len(dropped_hosts)))
for h in dropped_hosts:
    print('   [MitM 丢弃] %s  <- 无法安全收敛（避免误伤全域）' % h)
for h, fixed in sorted(repaired_hosts.items()):
    print('   [MitM 修复] %s  ->  %s  （上游缺 TLD，已从规则补全）' % (h, fixed))
for h, fixed in sorted(typo_hosts.items()):
    print('   [MitM 纠错] %s  ->  %s  （上游 hostname 拼写错误，已按规则修正）' % (h, fixed))
for c in sorted(auto_added):
    print('   [MitM 补全] %s  （规则存在但 hostname 漏写，已补全）' % c)
for h, ent in derived_hosts.items():
    print('   [MitM 收敛] %s  ->  %s' % (h, ', '.join(ent)))
print('跳过/异常  : %d' % len(skipped))
for s, why in skipped:
    print('   [跳过] %s  <- %s' % (why, s[:100]))
