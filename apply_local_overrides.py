#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse

RULE = ('response if ${url} ~= /^https?:\\/\\/creditcard\\.bankcomm\\.(?:cn|com)\\/tofimg\\/bucket-pj-btss-tfcn-dmz\\/OSS-F\\/.+/i '
        'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/maidanba.js") '
        'with tag="买单吧开屏广告", requires_body=true, binary_body_mode=true')

# Script-Hub's QX rewrite -> Loon plugin conversion with jsc2=.
# jsc2= enables Script-Hub's QX compatibility wrapper (wrap_response=true);
# do not replace these with a hand-written Loon response script.
HELLOBIKE_JS = (
    "http://script.hub/convert/_start_/"
    "https://raw.githubusercontent.com/ZenmoFeiShi/Qx/refs/heads/main/easybike-ad.js"
    "/_end_/easybike-ad.js?type=qx-script&target=loon-script&wrap_response=true&headers="
)

HELLOBIKE_REWRITE_RULES = (
    r"^https?:\/\/api-htp\.beizi\.biz\/mb\/sdk0\/json(?:\?|$) reject-200",
    r"^https?:\/\/adservice\.sigmob\.cn\/(?:hb\/v2\/ad|ad\/v4)(?:\?|$) reject-200",
    r"^https?:\/\/tm\.sigmob\.cn\/(?:waterfall\/v1|strategy\/v6)(?:\?|$) reject-200",
    r"^https?:\/\/(?:mi|v2mi)\.gdt\.qq\.com\/(?:gdt_mview\.fcg|server_bidding2)(?:\?|$) reject-200",
)

HELLOBIKE_SCRIPT_RULES = (
    f"http-request ^https:\\/\\/resource\\.51downapp\\.cn\\/f414fbc17c411b4e986ba8891c738a49\\.json\\?(?:[^#]*&)?md5=e5230c919f7e3f3af3256161fbfaa0e2&(?:[^#]*&)?hbe_qx_ui=1\\.3$ script-path={HELLOBIKE_JS}, timeout=60, tag=easybike-ad",
    f"http-response ^https:\\/\\/api\\.hellobike\\.com(?::443)?\\/secretkey(?:\\?|$) script-path={HELLOBIKE_JS}, requires-body=true, timeout=60, tag=easybike-ad",
    f"response if ${{url}} ~= /^https:\\/\\/taxiapi\\.hellobike\\.com(?::443)?\\/api(?:\\?|$)/i && ${{request.method}} == \"POST\" && ${{request.header['action']}} == \"hitch.driver.journeyList\" then script(\"{HELLOBIKE_JS}\") with requires_body=true, timeout=60, tag=\"easybike-ad\"",
)

HELLOBIKE_MITM_HOSTS = {
    "api.hellobike.com",
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

LEGACY_HELLOBIKE_MARKER = "scripts/hellobike-clean.js"
BAIDU_BROKEN_STATIC_MARKERS = ("www.baidu.com", "action=static&ms=1&version=css_page_2@0")
HELLOBIKE_HIGH_FREQUENCY_MARKERS = ("api.hellobike.com", "marketingapi.hellobike.com", "entertainment.hellobike.com", "taxiapi.hellobike.com")
HELLOBIKE_SOURCE = "ZenmoFeiShi-Qx-HelloBike(ScriptHub-Loon)"


def append_to_section(lines, section, entries):
    try:
        start = lines.index("[" + section + "]")
    except ValueError as exc:
        raise ValueError("plugin missing [" + section + "] section") from exc
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("[") and lines[i].endswith("]")), len(lines))
    existing = set(lines[start + 1:end])
    additions = [entry for entry in entries if entry not in existing]
    if additions:
        lines[end:end] = additions


def apply(text: str) -> str:
    if "[Script]" not in text or "[MITM]" not in text or "[Rewrite]" not in text:
        raise ValueError("plugin missing [Rewrite], [Script] or [MITM] section")

    # Remove the PR #121 hand-written HelloBike integration, which is not
    # equivalent to the upstream QX script and was reported ineffective.
    lines = []
    for line in text.splitlines():
        if LEGACY_HELLOBIKE_MARKER in line:
            continue
        if all(marker in line for marker in BAIDU_BROKEN_STATIC_MARKERS) and line.rstrip().endswith("reject"):
            continue
        if "tag=easybike-ad" in line and any(host in line for host in HELLOBIKE_HIGH_FREQUENCY_MARKERS):
            if "/secretkey" not in line and "resource" not in line:
                continue
        lines.append(line)

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

    append_to_section(lines, "Rewrite", HELLOBIKE_REWRITE_RULES)
    append_to_section(lines, "Script", HELLOBIKE_SCRIPT_RULES)

    # Make the converted upstream source visible in plugin metadata.
    for index, line in enumerate(lines):
        if line.startswith("#!sources=") and HELLOBIKE_SOURCE not in line:
            lines[index] = line + "+" + HELLOBIKE_SOURCE
            break

    # Keep the unrelated Bankcomm override in [Script], idempotently.
    result = "\n".join(lines)
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
    print("已应用买单吧覆盖规则及 Script-Hub 转换的哈啰 QX 规则")


if __name__ == "__main__":
    main()
