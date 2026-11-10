#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed validation for downloaded rule sources and cloned repositories."""
import argparse
import json
import re
from pathlib import Path

REQUIRED_ZMJDE = (
    "DiDi_remove_ads.lpx", "PinDuoDuo_remove_ads.lpx",
    "FleaMarket_remove_ads.lpx", "Taobao_remove_ads.lpx", "smzdm_remove_ads.lpx",
    "Block_HTTPDNS.lpx", "BlockAdvertisers.lpx", "Remove_ads_by_keli.lpx",
)


def real_lines(text):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "//", ";"))]


def validate_source(text, source, min_bytes=200, min_entries=1,
                    required_sections=(), require_hostname=False):
    if not isinstance(text, str):
        raise ValueError("%s: 响应不是文本" % source)
    data = text.lstrip("\ufeff \t\r\n")
    if len(text.encode("utf-8")) < min_bytes:
        raise ValueError("%s: 响应过小（%d bytes，要求至少 %d）" %
                         (source, len(text.encode("utf-8")), min_bytes))
    if re.search(r"(?is)^\s*(?:<!doctype\s+html|<html\b)", data[:1000]):
        raise ValueError("%s: 返回 HTML 页面而不是规则文本" % source)
    if any(marker in data[:5000].lower() for marker in
           ("cloudflare ray id", "attention required! | cloudflare",
            "temporarily unavailable", "repository not found")):
        raise ValueError("%s: 命中上游错误页特征" % source)
    for section in required_sections:
        if not re.search(r"(?mi)^\s*\[" + re.escape(section) + r"\]\s*$", text):
            raise ValueError("%s: 缺少必要区块 [%s]" % (source, section))
    if require_hostname and not re.search(r"(?mi)^\s*hostname\s*=", text):
        raise ValueError("%s: 缺少 hostname 声明" % source)
    entries = real_lines(text)
    if len(entries) < min_entries:
        raise ValueError("%s: 有效内容仅 %d 行（要求至少 %d）" %
                         (source, len(entries), min_entries))
    return {"bytes": len(text.encode("utf-8")), "entries": len(entries)}


def validate_rstore_rewrite(text):
    stats = validate_source(text, "R-Store rewrite", min_bytes=500,
                            min_entries=20, require_hostname=True)
    count = sum(1 for line in real_lines(text)
                if re.match(r"^\S+\s+url\s+", line))
    if count < 20:
        raise ValueError("R-Store rewrite: 可识别 URL 规则仅 %d 条（要求至少 20）" % count)
    stats["url_rules"] = count
    return stats


def validate_filter(text):
    stats = validate_source(text, "R-Store filter", min_bytes=500, min_entries=20)
    count = sum(1 for line in real_lines(text)
                if len([p for p in line.split(",")]) >= 3
                and not line.lower().startswith("hostname"))
    if count < 20:
        raise ValueError("R-Store filter: 可识别规则仅 %d 条（要求至少 20）" % count)
    stats["rules"] = count
    return stats


def validate_blockv2(text):
    stats = validate_source(text, "blockAdsV2", min_bytes=300, min_entries=5,
                            required_sections=("Rewrite", "MITM"))
    count = sum(len(real_lines(x)) for x in re.findall(
        r"(?ms)^\[(?:Rewrite|Script|Rule)\]\s*\n(.*?)(?=^\[|\Z)", text))
    if count < 5:
        raise ValueError("blockAdsV2: Rewrite/Script/Rule 有效条目仅 %d 条" % count)
    stats["rule_entries"] = count
    return stats


def validate_myblockads(text):
    stats = validate_source(text, "MyBlockAds", min_bytes=300, min_entries=5,
                            required_sections=("Rewrite",))
    count = sum(len(real_lines(x)) for x in re.findall(
        r"(?ms)^\[(?:Rewrite|Script|Rule)\]\s*\n(.*?)(?=^\[|\Z)", text))
    if count < 5:
        raise ValueError("MyBlockAds: Rewrite/Script/Rule 有效条目仅 %d 条" % count)
    stats["rule_entries"] = count
    return stats


def check_clones(thelong, aoomee, zmjde, qxapp):
    report = {}
    tl = list(Path(thelong).glob("*_ad_block.plugin")) + list(
        Path(thelong).glob("*_splash_ad_block.plugin"))
    tl = [p for p in tl if not p.name.startswith("ai_auto_node")]
    if not tl:
        raise ValueError("Thelongdarkorg: 未找到任何 *_ad_block.plugin / *_splash_ad_block.plugin")
    ao_dir = Path(aoomee) / "plugins"
    if not ao_dir.is_dir():
        ao_dir = Path(aoomee)
    ao = list(ao_dir.glob("*.plugin")) + list(ao_dir.glob("*.lpx"))
    if not ao:
        raise ValueError("aoomee: plugins 目录没有 .plugin/.lpx 文件")
    zm_dir = Path(zmjde) / "Plugin"
    if not zm_dir.is_dir():
        zm_dir = Path(zmjde)
    missing = [name for name in REQUIRED_ZMJDE if not (zm_dir / name).is_file()]
    if missing:
        raise ValueError("zmjde 缺少指定插件: " + ", ".join(missing))
    qx = Path(qxapp).read_text(encoding="utf-8-sig")
    qx_stats = validate_source(qx, "GuaZiVideoAds", min_bytes=100,
                               min_entries=1, require_hostname=True)
    if not re.search(r"(?m)^\s*\^https?\S*\s+url\s+", qx):
        raise ValueError("GuaZiVideoAds: 未发现可识别的 QuanX URL 规则")
    report.update({
        "thelongdarkorg": {"plugin_files": len(tl)},
        "aoomee": {"plugin_files": len(ao)},
        "zmjde": {"required_plugins": len(REQUIRED_ZMJDE)},
        "GuaZiVideoAds": qx_stats,
    })
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thelong")
    parser.add_argument("--aoomee")
    parser.add_argument("--zmjde")
    parser.add_argument("--qxapp")
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        report = check_clones(args.thelong, args.aoomee, args.zmjde, args.qxapp)
        if args.report:
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
        print("[source-guard] 上游仓库结构检查通过：" +
              json.dumps(report, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        raise SystemExit("[source-guard] FAIL-CLOSED: %s" % exc)


if __name__ == "__main__":
    main()
