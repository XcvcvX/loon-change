#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed validation for downloaded rule sources and cloned repositories."""
import argparse
import json
import re
import subprocess
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
    supported_types = {"host", "host-suffix", "host-keyword", "host-wildcard",
                       "ip-cidr", "ip6-cidr"}
    supported_policies = {"reject", "reject-200", "reject-img", "reject-dict",
                          "reject-array", "reject-drop"}
    count = 0
    for line in real_lines(text):
        parts = [part.strip().lower() for part in line.split(",")]
        if len(parts) >= 3 and parts[0] in supported_types and parts[2] in supported_policies:
            count += 1
    if count < 20:
        raise ValueError("R-Store filter: 可转换规则仅 %d 条（要求至少 20）" % count)
    stats["rules"] = count
    return stats


def fetch_validated(urls, fetcher, validator, source):
    """按顺序尝试来源；只有下载且通过完整性校验的候选内容才会被返回。"""
    errors = []
    for url in urls:
        try:
            candidate = fetcher(url)
            stats = validator(candidate)
            return candidate, url, stats
        except Exception as exc:
            errors.append("%s: %s" % (url, exc))
            print("[fetch] %s 失败: %s" % (source, errors[-1]))
    detail = "; ".join(errors) if errors else "没有可用来源"
    raise ValueError("%s 获取失败: %s" % (source, detail))


def validate_plugin_file(path, source):
    """逐文件检查克隆插件，避免单个 HTML/空文件被来源总量掩盖。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    validate_source(text, source, min_bytes=20, min_entries=1)
    blocks = re.findall(r"(?ms)^\[([^\]]+)\]\s*\n(.*?)(?=^\[|\Z)", text)
    action_entries = sum(
        len(real_lines(body)) for name, body in blocks
        if name.strip().lower() in {"rewrite", "url rewrite", "script", "rule"})
    if action_entries < 1:
        raise ValueError("%s: 未发现有效 Rewrite/URL Rewrite/Script/Rule 内容" % source)
    return action_entries


def validate_amap(text):
    """Fail closed on incomplete/changed Amap plugin structure and its external assets."""
    stats = validate_source(
        text, "Amap", min_bytes=5000, min_entries=30,
        required_sections=("Rule", "Rewrite", "Script", "MitM"),
        require_hostname=True)
    blocks = {name.strip().lower(): body for name, body in re.findall(
        r"(?ms)^\[([^\]]+)\]\s*\n(.*?)(?=^\[|\Z)", text)}
    counts = {name: len(real_lines(blocks.get(name.lower(), "")))
              for name in ("Rule", "Rewrite", "Script")}
    limits = {"Rule": 3, "Rewrite": 20, "Script": 10}
    for name, minimum in limits.items():
        if counts[name] < minimum:
            raise ValueError("Amap [%s] 有效条目仅 %d 条（要求至少 %d）" %
                             (name, counts[name], minimum))
    mitm = re.search(r"(?mi)^\s*hostname\s*=\s*(.+)$", blocks.get("mitm", ""))
    hosts = [x.strip() for x in mitm.group(1).split(",")] if mitm else []
    if "*.amap.com" not in hosts:
        raise ValueError("Amap: 缺少预期的 *.amap.com MITM 声明")
    if any(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}|\[[0-9a-fA-F:]+\]", h)
           for h in hosts):
        raise ValueError("Amap: MITM 中出现裸 IP，拒绝自动合并")
    required_assets = (
        "rucu6_amap.js", "loon_Amap.recommend.jq",
        "updatable.jq", "search_poi_detail.jq")
    missing = [asset for asset in required_assets if asset not in text]
    if missing:
        raise ValueError("Amap: 缺少预期的远程依赖引用: " + ", ".join(missing))
    stats.update({"sections": counts, "mitm_hosts": hosts,
                  "required_assets": list(required_assets)})
    return stats

def validate_blockv2(text):
    stats = validate_source(text, "blockAdsV2", min_bytes=300, min_entries=5,
                            required_sections=("Rewrite", "MITM"))
    count = sum(len(real_lines(x)) for x in re.findall(
        r"(?ms)^\[(?:Rewrite|URL Rewrite|Script|Rule)\]\s*\n(.*?)(?=^\[|\Z)", text))
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


def check_clones(thelong, aoomee, zmjde, qxapp, previous_report=None, amap=None):
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
    def revision(path):
        try:
            return subprocess.check_output(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return "unknown"

    def rule_lines(paths):
        total = 0
        for path in paths:
            try:
                total += validate_plugin_file(path, "%s/%s" % (path.parent, path.name))
            except Exception as exc:
                raise ValueError("来源插件逐文件校验失败 %s: %s" % (path, exc))
        return total

    zm_files = [zm_dir / name for name in REQUIRED_ZMJDE]
    counts = {
        "thelongdarkorg": rule_lines(tl),
        "aoomee": rule_lines(ao),
        "zmjde": rule_lines(zm_files),
    }
    for source, count in counts.items():
        if count < 10:
            raise ValueError("%s 可识别规则量仅 %d 行（要求至少 10），拒绝把异常空源写入基线"
                             % (source, count))
    if amap:
        amap_text = Path(amap).read_text(encoding="utf-8-sig")
        report["Amap"] = validate_amap(amap_text)
    report.update({
        "thelongdarkorg": {"commit": revision(thelong), "plugin_files": len(tl),
                           "rule_lines": counts["thelongdarkorg"]},
        "aoomee": {"commit": revision(aoomee), "plugin_files": len(ao),
                   "rule_lines": counts["aoomee"]},
        "zmjde": {"commit": revision(zmjde), "required_plugins": len(REQUIRED_ZMJDE),
                  "rule_lines": counts["zmjde"]},
        "GuaZiVideoAds": qx_stats,
    })
    if previous_report and Path(previous_report).is_file():
        previous = json.loads(Path(previous_report).read_text(encoding="utf-8"))
        for source in ("thelongdarkorg", "aoomee", "zmjde"):
            old_count = previous.get(source, {}).get("rule_lines", 0)
            new_count = report[source]["rule_lines"]
            if old_count >= 20 and new_count < old_count * 0.40:
                raise ValueError(
                    "%s 规则量异常下降：%d -> %d（下降超过 60%%）；拒绝自动发布，请人工核实上游变化"
                    % (source, old_count, new_count))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thelong")
    parser.add_argument("--aoomee")
    parser.add_argument("--zmjde")
    parser.add_argument("--qxapp")
    parser.add_argument("--amap", help="RuCu6 高德地图独立 Loon 插件路径")
    parser.add_argument("--report")
    parser.add_argument("--previous-report")
    args = parser.parse_args()
    try:
        report = check_clones(args.thelong, args.aoomee, args.zmjde, args.qxapp, args.previous_report, args.amap)
        if args.report:
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
        print("[source-guard] 上游仓库结构检查通过：" +
              json.dumps(report, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        raise SystemExit("[source-guard] FAIL-CLOSED: %s" % exc)


if __name__ == "__main__":
    main()
