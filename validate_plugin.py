#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon 插件确定性校验器（生成后自检，与转换路径相互独立）。

校验内容：
  - [MITM] 每个 hostname 为合法域名 / *.后缀 通配 / - 前缀排除，且不是裸公共后缀；
  - [Rewrite] 旧版动作名均在 Loon 合法动作集内；新版语法行包含必选 URL 守卫与 then。

用法：
  python3 validate_plugin.py <file.plugin>

硬错误 -> 退出码 1（GitHub Actions 会因此失败，阻止错误产物被提交）；
警告   -> 仅打印，不影响退出码。
"""
import re
import sys

# 合法域名：末段 TLD 只含字母、长度 >=2（真实 TLD 不含数字）
HOST_RE = re.compile(
    r'^(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$')
IP_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')

# Loon 旧版 Rewrite 合法动作（见官方文档 Rewrite 旧语法）
LEGACY_ACTIONS = {
    'reject', 'reject-200', 'reject-img', 'reject-dict', 'reject-array',
    'response-body-replace-regex', 'request-body-replace-regex',
    'header-replace-regex', '302',
}

# 常见两级公共后缀（其 registrable domain 需取三级）
PUBLIC_SUFFIX_2L = {
    'com.cn', 'net.cn', 'org.cn', 'gov.cn', 'edu.cn', 'ac.cn', 'mil.cn',
    'com.hk', 'com.tw', 'com.au', 'com.sg', 'com.my', 'com.vn', 'com.ph',
    'com.br', 'com.mx', 'com.tr', 'co.jp', 'or.jp', 'ne.jp', 'ac.jp',
    'co.uk', 'org.uk', 'ac.uk', 'co.kr', 'or.kr', 'co.in', 'co.nz',
    'co.th', 'co.id',
}


def is_public_suffix(d):
    labels = d.split('.')
    if len(labels) == 1:
        return True
    return len(labels) == 2 and d.lower() in PUBLIC_SUFFIX_2L


def sections(text):
    """返回 {段名: [行...]}（仅识别顶层 [X] 段）"""
    out, cur = {}, None
    for line in text.split('\n'):
        m = re.match(r'^\[([A-Za-z]+)\]\s*$', line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def check_hostname(errors, warnings, host):
    raw = host
    if host.startswith('-'):          # 排除前缀
        host = host[1:]
    if not host:
        errors.append('空的排除项: %r' % raw)
        return
    if IP_RE.match(host):
        warnings.append('裸 IP（Loon hostname 按域名处理，通常无效）: %s' % host)
        return
    if '*' in host or '?' in host:
        # 仅接受 *.后缀 形式（其余通配应由转换器收敛）
        if not re.match(r'^\*\.[A-Za-z0-9\-\.]+$', host):
            errors.append('hostname 含未收敛的通配（仅支持 *.后缀）: %s' % raw)
            return
        suffix = host[2:]
        if is_public_suffix(suffix):
            errors.append('hostname 为裸公共后缀（会全域解密、弹证书错误）: %s' % raw)
        return
    if not HOST_RE.match(host):
        errors.append('hostname 不是合法域名（疑似缺 TLD）: %s' % raw)


def main(path):
    text = open(path, encoding='utf-8').read()
    sec = sections(text)
    errors, warnings = [], []

    # ---- [MITM] ----
    for line in sec.get('MITM', []):
        if '=' not in line:
            continue
        val = line.split('=', 1)[1]
        for h in val.split(','):
            h = h.strip()
            if h:
                check_hostname(errors, warnings, h)

    # ---- [Rewrite] ----
    for line in sec.get('Rewrite', []):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if ' if ${url} ' in s:
            # 新版语法：必须有 URL 守卫与 then
            if ' then ' not in s:
                errors.append('新语法行缺少 then: %s' % s)
            if not re.search(r'(request|response) if \$\{url\} ~= /', s):
                errors.append('新语法行缺少必选 URL 守卫: %s' % s)
            continue
        toks = s.split()
        if len(toks) >= 2 and toks[1] not in LEGACY_ACTIONS:
            errors.append('未知 Rewrite 动作 %r: %s' % (toks[1], s))

    # ---- 报告 ----
    for w in warnings:
        print('[警告] ' + w)
    for e in errors:
        print('[错误] ' + e)
    print('\n校验 %s：错误 %d，警告 %d' % (path, len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('用法: python3 validate_plugin.py <file.plugin>')
    sys.exit(main(sys.argv[1]))
#（注：内容由AI生成）
