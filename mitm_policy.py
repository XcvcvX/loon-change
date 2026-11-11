#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared MITM exclusions for certificate-pinned or known MITM-incompatible hosts.

This policy is consumed by both the merge pipeline and the read-only deep audit.
Keep reasons explicit so intentionally skipped HTTPS coverage is not misreported
as an accidental missing-MITM configuration.
"""

MITM_SKIP_REASONS = {
    "amemv.com": "抖音核心 API 与 Frontier 长连接存在 SSL Pinning，强制 MITM 会导致握手失败",
    "ios.chat.openai.com": "ChatGPT App 证书校验；R-Store 上游明确警告强制 MITM 会导致新版本无法使用",
    "mobilepaas.abchina.com.cn": "农业银行上游标注已无法 MITM；强制解密可能导致大部分功能不可用",
    "images.cib.com.cn": "兴业银行上游标注已无法 MITM；相关图片拦截存在首页图片误杀风险",
    "elife.icbc.com.cn": "工商银行开屏广告守卫可能影响 App 功能，按证书绑定风险跳过",
    "openapi.boc.cn": "中国银行广告列表守卫可能导致银行 App 异常，按证书绑定风险跳过",
    "res.cc.cmbimg.com": "招商银行响应体替换守卫可能导致功能不可用，按证书绑定风险跳过",
    "wcmp.189.cn": "中国电信广告项响应体替换可能导致功能不可用，按证书绑定风险跳过",
    "m.ctrip.com": "携程上游提示该域可能无法 MITM，启用时可能造成图片或功能异常",
}


def mitm_skip_match(host):
    """Return (matched policy domain, reason), or None when host is not excluded."""
    candidate = host.strip().lstrip("-").strip(".").lower()
    if candidate.startswith("*."):
        candidate = candidate[2:]
    candidate = candidate.replace("*", "").replace("?", "").strip(".")
    matches = [
        domain for domain in MITM_SKIP_REASONS
        if candidate == domain or candidate.endswith("." + domain)
    ]
    if not matches:
        return None
    domain = max(matches, key=len)
    return domain, MITM_SKIP_REASONS[domain]


def mitm_skip_host(host):
    """Whether a hostname (including wildcard/negative forms) is in the skip policy."""
    return mitm_skip_match(host) is not None
