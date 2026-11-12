#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse
import re

ROOT = Path(__file__).resolve().parent
SPOTIFY_SOURCE = ROOT / "sources" / "spotify" / "Spotify.lpx"
SPOTIFY_SCRIPT_BASE = "https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/spotify/"

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
    "api.hellobike.com", "taxiapi.hellobike.com",
    "marketingapi.hellobike.com", "entertainment.hellobike.com",
    "resource.51downapp.cn",
}

SPOTIFY_SCRIPT_TAGS = ("Spotify search ads", "Spotify home ads", "Spotify scroll ads")
SPOTIFY_RULES = {"DOMAIN,aet.spotify.com,REJECT"}
SPOTIFY_MITM_HOSTS = {"spclient.wg.spotify.com", "*spclient.spotify.com"}


def _section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip().lower() == f"[{name.lower()}]"), None)
    if start is None:
        raise ValueError(f"plugin missing [{name}] section")
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^\s*\[[^]]+\]\s*$", lines[i])), len(lines))
    return lines[start + 1:end]


def _append_section(text: str, name: str, additions: list[str]) -> str:
    if not additions:
        return text
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.strip().lower() == f"[{name.lower()}]"), None)
    if start is None:
        raise ValueError(f"plugin missing [{name}] section")
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^\s*\[[^]]+\]\s*$", lines[i])), len(lines))
    present = set(lines)
    fresh = [line for line in additions if line not in present]
    if fresh:
        lines[end:end] = fresh
    return "\n".join(lines)


def _spotify_additions(source_text: str) -> tuple[list[str], list[str], list[str], set[str]]:
    rules = [line.strip() for line in _section(source_text, "Rule")
             if line.strip() in SPOTIFY_RULES]
    if rules != sorted(SPOTIFY_RULES):
        raise ValueError("Spotify upstream ad-tracking domain rule missing or ambiguous")
    rewrite = [line.strip() for line in _section(source_text, "Rewrite")
               if line.strip().startswith("^https") and "ad-logic" in line
               and "premium-marketing" in line]
    if len(rewrite) != 1:
        raise ValueError("Spotify upstream ad-delivery rewrite rule missing or ambiguous")

    scripts = [line.strip() for line in _section(source_text, "Script")
               if any(f"tag={tag}" in line for tag in SPOTIFY_SCRIPT_TAGS)]
    if len(scripts) != 3:
        raise ValueError("Spotify upstream must provide exactly three ad response scripts")
    expected = {"spot-NoSearchAd.js", "spot-NoHomeAd.js", "spot-NoScrollAd.js"}
    rewritten = []
    for line in scripts:
        match = re.search(r"/Scripts/Spotify/([^,\s]+)", line)
        if not match or match.group(1) not in expected:
            raise ValueError("Unexpected Spotify ad script reference")
        name = match.group(1)
        line = re.sub(r"script-path=https://raw\.githubusercontent\.com/[^,\s]+",
                      SPOTIFY_SCRIPT_BASE + name, line)
        rewritten.append(line)

    mitm = next((line for line in _section(source_text, "Mitm")
                 if re.match(r"^\s*hostname\s*=", line, re.I)), None)
    if not mitm:
        raise ValueError("Spotify upstream MITM hostname missing")
    hosts = {host.strip() for host in mitm.split("=", 1)[1].split(",") if host.strip()}
    if not SPOTIFY_MITM_HOSTS.issubset(hosts):
        raise ValueError("Spotify upstream MITM host list changed unexpectedly")
    return rules, rewrite, rewritten, hosts


def apply(text: str, spotify_source: str | None = None) -> str:
    if any(section not in text for section in ("[Rule]", "[Rewrite]", "[Script]", "[MITM]")):
        raise ValueError("plugin missing [Rule], [Rewrite], [Script] or [MITM] section")
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

    source_text = spotify_source
    if source_text is None:
        if not SPOTIFY_SOURCE.exists():
            raise ValueError("Spotify upstream snapshot missing")
        source_text = SPOTIFY_SOURCE.read_text(encoding="utf-8")
    spotify_rules, spotify_rewrite, spotify_scripts, spotify_hosts = _spotify_additions(source_text)
    for host in sorted(spotify_hosts):
        if host not in hosts:
            hosts.append(host)
    lines[hostname_index] = lines[hostname_index].split("=", 1)[0] + "= " + ", ".join(hosts)
    result = "\n".join(lines)

    additions = [rule for rule in (RULE,) + HELLOBIKE_RULES if rule not in result]
    if additions:
        pos = result.index("[MITM]")
        result = result[:pos].rstrip() + "\n" + "\n".join(additions) + "\n\n" + result[pos:]
    result = _append_section(result, "Rule", spotify_rules)
    result = _append_section(result, "Rewrite", spotify_rewrite)
    result = _append_section(result, "Script", spotify_scripts)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--spotify-source", default=str(SPOTIFY_SOURCE))
    args = ap.parse_args()
    path = Path(args.plugin)
    source = Path(args.spotify_source).read_text(encoding="utf-8")
    path.write_text(apply(path.read_text(encoding="utf-8"), source), encoding="utf-8")
    print("已应用买单吧、哈啰与 Spotify 上游去广告规则")


if __name__ == "__main__":
    main()
