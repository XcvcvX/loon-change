#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate vendored Amap assets and attach immutable upstream provenance."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PLUGIN_UPSTREAM_PATH = "Modules/Loon/sooyaaabo/Amap.lpx"
ASSET_UPSTREAM_PATHS = {
    "rucu6_amap.js": "Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js",
    "loon_Amap.recommend.jq": "Modules/JavaScript/sooyaaabo/Amap/loon_Amap.recommend.jq",
    "updatable.jq": "Modules/JavaScript/Kelee/Amap_remove_ads/kelee_updatable.jq",
    "search_poi_detail.jq": "Modules/JavaScript/Kelee/Amap_remove_ads/kelee_search_poi_detail.jq",
}

ASSETS = {
    "rucu6_amap.js": {
        "min_bytes": 1000,
        "markers": ("$request", "$response"),
    },
    "loon_Amap.recommend.jq": {
        "min_bytes": 1000,
        "markers": (".data.toolsRecommend",),
    },
    "updatable.jq": {
        "min_bytes": 500,
        "markers": ("def ", "sportsGroupConfig"),
    },
    "search_poi_detail.jq": {
        "min_bytes": 500,
        "markers": ("def ", "baseInfo"),
    },
}


def git_blob_sha1(content):
    header = b"blob " + str(len(content)).encode("ascii") + bytes([0])
    return hashlib.sha1(header + content).hexdigest()


def _expected_blob(romeo_repo, commit, upstream_path):
    result = subprocess.run(
        ["git", "-C", str(romeo_repo), "rev-parse", "%s:%s" % (commit, upstream_path)],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _assert_upstream_blob(name, content, expected, upstream_path):
    actual = git_blob_sha1(content)
    if actual != expected:
        raise ValueError(
            "%s: upstream drift detected at %s (expected %s, got %s)" %
            (name, upstream_path, expected, actual)
        )
    return actual


def validate_asset(name, content):
    if name not in ASSETS:
        raise ValueError("未登记的高德依赖文件: " + name)
    if not isinstance(content, bytes):
        raise TypeError("依赖内容必须为 bytes")
    spec = ASSETS[name]
    if len(content) < spec["min_bytes"]:
        raise ValueError("%s: 文件过小（%d bytes，至少 %d）" %
                         (name, len(content), spec["min_bytes"]))
    sample = content[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if (sample.startswith(b"<!doctype html") or sample.startswith(b"<html")
            or b"cloudflare ray id" in sample
            or b"attention required! | cloudflare" in sample
            or content.startswith(b"version https://git-lfs.github.com/spec/v1")):
        raise ValueError(name + ": 命中 HTML/Cloudflare/Git LFS 错误内容")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(name + ": 不是有效 UTF-8 文本") from exc
    if "\x00" in text:
        raise ValueError(name + ": 包含 NUL 字节")
    missing = [marker for marker in spec["markers"] if marker not in text]
    if missing:
        raise ValueError("%s: 缺少预期内容标记: %s" %
                         (name, ", ".join(missing)))
    if re.search(r"(?im)^\s*(?:404: not found|repository not found)\s*$", text):
        raise ValueError(name + ": 命中上游 404 错误文本")
    return {
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "git_blob_sha1": git_blob_sha1(content),
    }


def build_provenance(asset_dir, plugin_path, commit, romeo_repo=None):
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise ValueError("Romeo 上游 commit 必须是完整 40 位 SHA")
    root = Path(asset_dir)
    plugin_path = Path(plugin_path)
    plugin_bytes = plugin_path.read_bytes()
    plugin = plugin_bytes.decode("utf-8-sig")
    assets_report = {}
    if romeo_repo is not None:
        expected_plugin = _expected_blob(romeo_repo, commit, PLUGIN_UPSTREAM_PATH)
        _assert_upstream_blob("Amap.lpx", plugin_bytes, expected_plugin, PLUGIN_UPSTREAM_PATH)
    for name in ASSETS:
        if name not in plugin:
            raise ValueError("Amap.lpx 未引用依赖: " + name)
        path = root / name
        if not path.is_file():
            raise ValueError("缺少高德依赖文件: " + str(path))
        content = path.read_bytes()
        stats = validate_asset(name, content)
        if romeo_repo is not None:
            upstream_path = ASSET_UPSTREAM_PATHS[name]
            expected = _expected_blob(romeo_repo, commit, upstream_path)
            stats["upstream_path"] = upstream_path
            _assert_upstream_blob(name, content, expected, upstream_path)
        assets_report[name] = stats
    plugin_report = {
        "bytes": len(plugin_bytes),
        "sha256": hashlib.sha256(plugin_bytes).hexdigest(),
        "git_blob_sha1": git_blob_sha1(plugin_bytes),
    }
    return {
        "upstream_repository": "https://github.com/ifflagged/Romeo",
        "upstream_commit": commit,
        "plugin": plugin_report,
        "assets": assets_report,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True)
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--romeo-repo", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report_path = Path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if "Amap" not in report:
        raise SystemExit("source-report.json 缺少 Amap 来源记录")
    report["Amap"].update(build_provenance(args.assets, args.plugin, args.commit, args.romeo_repo))
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("[amap-dependency-guard] PASS: " +
          json.dumps(report["Amap"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
