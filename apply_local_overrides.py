#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse

RULE = ('response if ${url} ~= /^https?:\\/\\/creditcard\\.bankcomm\\.(?:cn|com)\\/tofimg\\/bucket-pj-btss-tfcn-dmz\\/OSS-F\\/.+/i '
        'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/maidanba.js") '
        'with tag="买单吧开屏广告", requires_body=true, binary_body_mode=true')

HELLOBIKE_RULES = (
    r'response if ${url} ~= /^https?:\\/\\/(?:api|marketingapi|entertainment)\\.hellobike\\.com(?::\\d+)?\\/api(?:\\?|$)/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-接口", requires_body=true, timeout=10',
    r'response if ${url} ~= /^https?:\\/\\/api\\.hellobike\\.com(?::443)?\\/secretkey(?:\\?|$)/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-动态密钥", requires_body=true, timeout=10',
    r'response if ${url} ~= /^https?:\\/\\/taxiapi\\.hellobike\\.com(?::443)?\\/api(?:\\?|$)/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-车主列表", requires_body=true, timeout=10',
    r'response if ${url} ~= /^https:\\/\\/resource\\.51downapp\\.cn\\/f414fbc17c411b4e986ba8891c738a49\\.json\\?(?:[^#]*&)?md5=e5230c919f7e3f3af3256161fbfaa0e2&(?:[^#]*&)?hbe_qx_ui=1\\.3$/i then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/hellobike-clean.js") with tag="哈啰净化-车抵贷模板", requires_body=true, timeout=10',
)

HELLOBIKE_MITM_HOSTS = {
    "taxiapi.hellobike.com",
    "marketingapi.hellobike.com",
    "entertainment.hellobike.com",
    "resource.51downapp.cn",
}

def apply(text: str) -> str:
    if "[Script]" not in text or "[MITM]" not in text:
        raise ValueError("plugin missing [Script] or [MITM] section")
    lines = text.splitlines()
    mitm_index = lines.index("[MITM]")
    hostname_index = next((i for i in range(mitm_index + 1, len(lines))
                           if lines[i].strip().lower().startswith("hostname") and "=" in lines[i]), None)
    if hostname_index is None:
        raise ValueError("plugin MITM hostname line missing")
    hosts = [x.strip() for x in lines[hostname_index].split("=", 1)[1].split(",") if x.strip()]
    required_bankcomm = {"creditcard.bankcomm.cn", "creditcard.bankcomm.com",
                         "creditcardapp.bankcomm.cn", "creditcardapp.bankcomm.com"}
    if not required_bankcomm.issubset(set(hosts)):
        raise ValueError("required Bankcomm image hosts missing from MITM")
    for host in sorted(HELLOBIKE_MITM_HOSTS):
        if host not in hosts:
            hosts.append(host)
    lines[hostname_index] = lines[hostname_index].split("=", 1)[0] + "= " + ", ".join(hosts)
    result = "\n".join(lines)
    additions = [rule for rule in (RULE,) + HELLOBIKE_RULES if rule not in result]
    if additions:
        pos = result.index("[MITM]")
        result = result[:pos].rstrip() + "\n" + "\n".join(additions) + "\n\n" + result[pos:]
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    args = ap.parse_args()
    path = Path(args.plugin)
    path.write_text(apply(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("已应用买单吧开屏本地覆盖规则")

if __name__ == "__main__":
    main()
