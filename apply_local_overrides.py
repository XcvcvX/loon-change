#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse
import re

RULE = (r'response if ${url} ~= /^https?:\/\/creditcard\.bankcomm\.(?:cn|com)\/tofimg\/bucket-pj-btss-tfcn-dmz\/OSS-F\/.+/i '
        'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/maidanba.js") '
        'with tag="买单吧开屏广告", requires_body=true, binary_body_mode=true')

LEGACY_HELLOBIKE_MARKER = "scripts/hellobike-clean.js"
HELLOBIKE_SOURCE = "ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)"
HELLOBIKE_ADDED_MITM_HOSTS = {
    "taxiapi.hellobike.com",
    "marketingapi.hellobike.com",
    "entertainment.hellobike.com",
    "resource.51downapp.cn",
    "api-htp.beizi.biz",
    "adservice.sigmob.cn",
    "tm.sigmob.cn",
    "mi.gdt.qq.com",
    "v2mi.gdt.qq.com",
}
# 拼多多 HTTPDNS IPv4 规则必须以查询路径边界结束：/d、/d4? 可命中，/download 不应命中。
PDD_HTTPDNS_MARKER = "com.xunmeng.pinduoduo"
PDD_HTTPDNS_OLD_SUFFIX = r"\/d(\d)?"
PDD_HTTPDNS_NEW_SUFFIX = r"\/d(\d)?(?:\?|$)"
PDD_HTTPDNS_IPV4_MARKER = r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
PDD_HTTPDNS_IPV6_MARKER = r"\[[0-9a-fA-F:]+\]"
PDD_HTTPDNS_IPV6_SUFFIX = r"\/d(\d)?\?"
PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX = PDD_HTTPDNS_NEW_SUFFIX + r"\?"

REQUIRED_BANKCOMM_MITM_HOSTS = {
    "creditcard.bankcomm.cn", "creditcard.bankcomm.com",
    "creditcardapp.bankcomm.cn", "creditcardapp.bankcomm.com",
}
HELLOBIKE_REWRITE_MARKERS = (
    "api-htp.beizi.biz",
    "adservice.sigmob.cn",
    "tm.sigmob.cn",
    "mi.gdt.qq.com",
    "v2mi.gdt.qq.com",
)
HELLOBIKE_SCRIPT_MARKERS = (
    "script.hub/convert/_start_/",
    "tag=easybike-ad",
)

# Soul 青少年配置：较早的 http(s) 规则已覆盖后续仅 HTTPS 的同路径规则。
SOUL_TEENAGER_CONFIG_BROAD_RULE = r"^https?:\/\/api-account\.soulapp\.cn\/teenager\/config reject-dict"
SOUL_TEENAGER_CONFIG_HTTPS_RULE = r"^https:\/\/api-account\.soulapp\.cn\/teenager\/config reject-dict"

PEOPLEAPP_HOME_AD_BROAD_RULE = r"^https?:\/\/app\.peopleapp\.com\/Api\/\d+/HomeApi\/(?:adv|getAdvertImage) reject"
PEOPLEAPP_HOME_AD_SHADOW_RULE = r"request if \${url} ~= /^https?:\/\/app\.peopleapp\.com\/Api\/\d+\/HomeApi\/(adv|getAdvertImage)/ then reject(404)"
PEOPLEAPP_IMAGE_AD_BROAD_RULE = r"^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*\.(?:jpg|png) reject-200"
PEOPLEAPP_IMAGE_AD_SHADOW_RULE = r"request if \${url} ~= /^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*\.(jpg|png)/ then reject(200)"

def remove_shadowed_peopleapp_rules(lines):
    output, home_broad_seen, image_broad_seen, removed = [], False, False, 0
    for line in lines:
        value = line.strip()
        if value == PEOPLEAPP_HOME_AD_BROAD_RULE:
            home_broad_seen = True
        if value == PEOPLEAPP_IMAGE_AD_BROAD_RULE:
            image_broad_seen = True
        if value == PEOPLEAPP_HOME_AD_SHADOW_RULE and home_broad_seen:
            removed += 1
            continue
        if value == PEOPLEAPP_IMAGE_AD_SHADOW_RULE and image_broad_seen:
            removed += 1
            continue
        output.append(line)
    return output, removed

def remove_subsumed_soul_teenager_rule(lines):
    output, broad_seen, removed = [], False, 0
    for line in lines:
        value = line.strip()
        if value == SOUL_TEENAGER_CONFIG_BROAD_RULE:
            broad_seen = True
        if value == SOUL_TEENAGER_CONFIG_HTTPS_RULE and broad_seen:
            removed += 1
            continue
        output.append(line)
    return output, removed


def split_response_json_rewrite(line: str):
    match = re.match(r'^(response if .+?) then (.+)', line)
    if not match: return None
    prefix, action_text = match.groups()
    actions = re.split(r'\s+\|\s+', action_text)
    if not actions or any(not action.startswith("response.json.") for action in actions): return None
    return prefix, actions

def merge_adjacent_response_json_rewrites(lines):
    output, index, merged = [], 0, 0
    while index < len(lines):
        parsed = split_response_json_rewrite(lines[index].strip())
        if not parsed:
            output.append(lines[index]); index += 1; continue
        prefix, actions = parsed
        look = index + 1
        while look < len(lines) and not lines[look].strip(): look += 1
        count = 1
        while look < len(lines):
            candidate = split_response_json_rewrite(lines[look].strip())
            if not candidate or candidate[0] != prefix: break
            actions.extend(candidate[1]); count += 1; look += 1
            while look < len(lines) and not lines[look].strip(): look += 1
        if count > 1:
            output.append(prefix + " then " + " | ".join(actions)); merged += 1; index = look
        else:
            output.append(lines[index]); index += 1
    return output, merged

def apply(text: str) -> str:
    if "[Script]" not in text or "[MITM]" not in text or "[Rewrite]" not in text:
        raise ValueError("plugin missing [Rewrite], [Script] or [MITM] section")

    lines = []
    section = ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            lines.append(line)
            continue

        if LEGACY_HELLOBIKE_MARKER in line:
            continue
        if section == "Rewrite" and any(marker in line for marker in HELLOBIKE_REWRITE_MARKERS):
            continue
        if section == "Script" and any(marker in line for marker in HELLOBIKE_SCRIPT_MARKERS):
            continue
        if line.startswith("#!sources="):
            sources = [item for item in line[len("#!sources="):].split("+")
                       if item != HELLOBIKE_SOURCE]
            line = "#!sources=" + "+".join(sources)
        if section == "Rule" and PDD_HTTPDNS_MARKER in line and "URL-REGEX" in line:
            if PDD_HTTPDNS_IPV6_MARKER in line:
                # IPv6 HTTPDNS already had its own query boundary. Repair the
                # accidental suffix introduced by the prior broad IPv4 match.
                if PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX in line:
                    line = line.replace(PDD_HTTPDNS_IPV6_PREVIOUS_BAD_SUFFIX, PDD_HTTPDNS_IPV6_SUFFIX)
                elif PDD_HTTPDNS_IPV6_SUFFIX not in line:
                    raise ValueError("拼多多 IPv6 HTTPDNS matcher changed; refusing an unreviewed rewrite")
            elif PDD_HTTPDNS_IPV4_MARKER in line:
                if PDD_HTTPDNS_NEW_SUFFIX in line:
                    pass
                elif PDD_HTTPDNS_OLD_SUFFIX in line:
                    line = line.replace(PDD_HTTPDNS_OLD_SUFFIX, PDD_HTTPDNS_NEW_SUFFIX)
                else:
                    raise ValueError("拼多多 IPv4 HTTPDNS matcher changed; refusing an unreviewed rewrite")
            else:
                raise ValueError("拼多多 HTTPDNS address-family matcher changed; refusing an unreviewed rewrite")
        if section == "MITM" and line.strip().lower().startswith("hostname") and "=" in line:
            key, value = line.split("=", 1)
            hosts = [host.strip() for host in value.split(",") if host.strip()]
            if not REQUIRED_BANKCOMM_MITM_HOSTS.issubset(set(hosts)):
                raise ValueError("required Bankcomm image hosts missing from MITM")
            hosts = [host for host in hosts if host not in HELLOBIKE_ADDED_MITM_HOSTS]
            line = key + "= " + ", ".join(hosts)
        lines.append(line)

    result_lines, rewrite_lines = [], []
    section = ""
    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            if section == "Rewrite":
                rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
                rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
                rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
                result_lines.extend(rewrite_lines); rewrite_lines = []
            section = line[1:-1]; result_lines.append(line)
        elif section == "Rewrite": rewrite_lines.append(line)
        else: result_lines.append(line)
    if section == "Rewrite":
        rewrite_lines, _ = merge_adjacent_response_json_rewrites(rewrite_lines)
        rewrite_lines, _ = remove_subsumed_soul_teenager_rule(rewrite_lines)
        rewrite_lines, _ = remove_shadowed_peopleapp_rules(rewrite_lines)
        result_lines.extend(rewrite_lines)
    result = "\n".join(result_lines)
    # Keep the unrelated Bankcomm override in [Script], idempotently.
    if RULE not in result:
        pos = result.index("[MITM]")
        result = result[:pos].rstrip() + "\n" + RULE + "\n\n" + result[pos:]
    return result + ("\n" if text.endswith("\n") and not result.endswith("\n") else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    args = ap.parse_args()
    path = Path(args.plugin)
    path.write_text(apply(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("已应用买单吧覆盖规则；已移除 PR #129 引入的哈啰整合规则")


if __name__ == "__main__":
    main()
