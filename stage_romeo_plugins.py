#!/usr/bin/env python3
"""Stage the former AOOMEE App-plugin feed from a pinned Romeo commit.

The historical merge slot is retained for provenance compatibility, but no
AOOMEE repository clone or runtime fetch is needed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROMEO_PLUGIN_MAP = {
    "12306.lpx": "Modules/Loon/fmz200/12306.lpx",
    "amap.lpx": "Modules/Loon/ishowshu/amap.lpx",
    "boc.plugin": "Modules/Loon/zirawell/boc.lpx",
    "chelaile.plugin": "Modules/Loon/sooyaaabo/CheLaiLe.lpx",
    "cmbchina.lpx": "Modules/Loon/ishowshu/cmbchina.lpx",
    "didi.lpx": "Modules/Loon/ishowshu/didi.lpx",
    "github.lpx": "Modules/Loon/ishowshu/github.lpx",
    "goofish.lpx": "Modules/Loon/ishowshu/goofish.lpx",
    "hupu.lpx": "Modules/Loon/ishowshu/hupu.lpx",
    "jd.lpx": "Modules/Loon/ishowshu/jd.lpx",
    "keep.lpx": "Modules/Loon/ishowshu/keep.lpx",
    "leisu.lpx": "Modules/Loon/ishowshu/leisu.lpx",
    "meituan.lpx": "Modules/Loon/ZenmoFeiShi/MT.lpx",
    "pdd-filter.lpx": "Modules/Loon/ishowshu/pdd-filter.lpx",
    "pdd-rewrite.lpx": "Modules/Loon/ishowshu/pdd-rewrite.lpx",
    "pupu.lpx": "Modules/Loon/ishowshu/pupu.lpx",
    "qunar.plugin": "Modules/Loon/ccyykk666/qunar_ad.lpx",
    "soul-new.lpx": "Modules/Loon/ishowshu/soul.lpx",
    "taobao.lpx": "Modules/Loon/ishowshu/taobao.lpx",
    "umetrip.plugin": "Modules/Loon/ddgksf2013/UmetripAds.lpx",
    "youtube.lpx": "Modules/Loon/Maasea/YouTube.Enhance.lpx",
}

LEGACY_SNAPSHOTS = (
    "51cg.plugin",
    "91porn.plugin",
    "cmcc.plugin",
    "huazhu.plugin",
    "chelaile2.plugin",
    "qunar-legacy.plugin",
    "youtube-zh.lpx",
)

EXPECTED_PLUGIN_FILES = len(ROMEO_PLUGIN_MAP) + len(LEGACY_SNAPSHOTS)


def _read_romeo_file(repo: Path, commit: str, source_path: str) -> bytes:
    try:
        data = subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{commit}:{source_path}"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Romeo source missing at {commit}:{source_path}: {detail}") from exc
    text = data.decode("utf-8-sig", "strict")
    if not text.strip() or "<!doctype html" in text[:512].lower():
        raise RuntimeError(f"Romeo source is empty or HTML: {source_path}")
    if not text.lstrip().startswith("#!"):
        raise RuntimeError(f"Romeo source has no Loon metadata header: {source_path}")
    return data


def stage(romeo_repo: Path, commit: str, output: Path, repo_root: Path) -> dict:
    if not (romeo_repo / ".git").exists():
        raise RuntimeError(f"Not a Romeo git checkout: {romeo_repo}")
    output.mkdir(parents=True, exist_ok=True)
    for old in output.iterdir():
        if old.is_file() and old.suffix.lower() in {".lpx", ".plugin"}:
            old.unlink()

    for filename, source_path in ROMEO_PLUGIN_MAP.items():
        data = _read_romeo_file(romeo_repo, commit, source_path)
        (output / filename).write_bytes(data)

    legacy_dir = repo_root / "sources" / "romeo_legacy"
    for filename in LEGACY_SNAPSHOTS:
        source = legacy_dir / filename
        if not source.is_file():
            raise RuntimeError(f"Missing pinned legacy snapshot: {source}")
        data = source.read_bytes()
        text = data.decode("utf-8-sig", "strict")
        if not text.strip() or not text.lstrip().startswith("#!"):
            raise RuntimeError(f"Legacy snapshot is empty or lacks Loon metadata: {source}")
        (output / filename).write_bytes(data)

    staged = sorted(
        p.name for p in output.iterdir()
        if p.is_file() and p.suffix.lower() in {".lpx", ".plugin"}
    )
    if len(staged) != EXPECTED_PLUGIN_FILES:
        raise RuntimeError(
            f"Expected {EXPECTED_PLUGIN_FILES} staged plugins, found {len(staged)}"
        )
    return {
        "romeo_commit": commit,
        "romeo_plugin_files": len(ROMEO_PLUGIN_MAP),
        "legacy_snapshot_files": list(LEGACY_SNAPSHOTS),
        "staged_plugin_files": staged,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--romeo-repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    result = stage(
        Path(args.romeo_repo),
        args.commit,
        Path(args.output),
        Path(args.repo_root),
    )
    print("[romeo-stage] " + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
