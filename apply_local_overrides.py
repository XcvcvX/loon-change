#!/usr/bin/env python3
"""Apply durable local Loon plugin overrides after upstream merge."""
from pathlib import Path
import argparse

RULE = ('response if ${url} ~= /^https?:\\/\\/creditcard\\.bankcomm\\.(?:cn|com)\\/tofimg\\/bucket-pj-btss-tfcn-dmz\\/OSS-F\\/.+/i '
        'then script("https://raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/maidanba.js") '
        'with tag="买单吧开屏广告", requires_body=true, binary_body_mode=true')

def apply(text: str) -> str:
    if "[Script]" not in text or "[MITM]" not in text:
        raise ValueError("plugin missing [Script] or [MITM] section")
    hosts = set()
    mitm = text.split("[MITM]", 1)[1].splitlines()
    for line in mitm:
        if line.strip().lower().startswith("hostname") and "=" in line:
            hosts.update(x.strip() for x in line.split("=", 1)[1].split(","))
            break
    required = {"creditcard.bankcomm.cn", "creditcard.bankcomm.com", "creditcardapp.bankcomm.cn", "creditcardapp.bankcomm.com"}
    if not required.issubset(hosts):
        raise ValueError("required Bankcomm image hosts missing from MITM")
    if RULE in text:
        return text
    pos = text.index("[MITM]")
    return text[:pos].rstrip() + "\n" + RULE + "\n\n" + text[pos:]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True)
    args = ap.parse_args()
    path = Path(args.plugin)
    path.write_text(apply(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("已应用买单吧开屏本地覆盖规则")

if __name__ == "__main__":
    main()
