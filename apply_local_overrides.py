#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse

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

    result = "\n".join(lines)
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
