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

lines = raw.split('\n')

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
        scripts.append('%s %s script-path=%s,tag=%s,requires-body=true'
                       % (phase, urlre, js, tag))
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
def norm_host(h):
    """Loon 只支持 *. 前缀通配与 - 排除；中间/后缀通配需收敛为 *.主域，无法收敛则丢弃"""
    if h.startswith('-'):
        return h
    if h.endswith('.*'):
        h = h[:-2]
    if '*' in h:
        parts = [p for p in h.replace('*', '').split('.') if p]
        h = ('*.' + '.'.join(parts[-2:])) if len(parts) >= 2 else '.'.join(parts)
    if not re.match(r'^\*?\.?[A-Za-z0-9][A-Za-z0-9\-\.]*$', h):
        return None                   # 收敛后仍非法（如 *.*.com），丢弃避免误伤全域
    return h


seen, hosts = set(), []
for h in mitm_hosts:
    n = norm_host(h)
    if n and n not in seen:
        seen.add(n)
        hosts.append(n)


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
print('MitM  域名数: %d (原始 %d)' % (len(hosts), len(mitm_hosts)))
print('跳过/异常  : %d' % len(skipped))
for s, why in skipped:
    print('   [跳过] %s  <- %s' % (why, s[:100]))
