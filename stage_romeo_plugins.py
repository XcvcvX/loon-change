#!/usr/bin/env python3
"""Stage all formerly separate App-plugin feeds from one pinned Romeo commit.

romeo_resource_map.json is the single source of truth for plugin and runtime
asset mappings. Historical merge-slot names are retained only for compatibility.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

MANIFEST_PATH = Path(__file__).with_name("romeo_resource_map.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

ROMEO_PLUGIN_MAP = MANIFEST["slots"]["aoomee_compat"]["plugins"]
LEGACY_SNAPSHOTS = tuple(MANIFEST["slots"]["aoomee_compat"]["legacy_snapshots"])
ZMJDE_APP_MAP = MANIFEST["slots"]["zmjde_app_compat"]["plugins"]
ZMJDE_GENERAL_MAP = MANIFEST["slots"]["zmjde_general_compat"]["plugins"]
ZMJDE_PLUGIN_MAP = {**ZMJDE_APP_MAP, **ZMJDE_GENERAL_MAP}
ZMJDE_APP_PLUGINS = tuple(ZMJDE_APP_MAP)
ZMJDE_GENERAL_PLUGINS = tuple(ZMJDE_GENERAL_MAP)
RUNTIME_ASSETS = tuple(MANIFEST["runtime_assets"])
EXPECTED_PLUGIN_FILES = len(ROMEO_PLUGIN_MAP) + len(LEGACY_SNAPSHOTS)
EXPECTED_ZMJDE_PLUGIN_FILES = len(ZMJDE_PLUGIN_MAP)


def _read_romeo_file(repo: Path, commit: str, source_path: str) -> bytes:
    try:
        data = subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{commit}:{source_path}"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Romeo source missing at {commit}:{source_path}: {detail}") from exc
    decoded = data.decode("utf-8-sig", "strict")
    if not decoded.strip() or "<!doctype html" in decoded[:512].lower():
        raise RuntimeError(f"Romeo source is empty or HTML: {source_path}")
    return data


def _pinned_asset_url(commit: str, source_path: str) -> str:
    return f"https://raw.githubusercontent.com/ifflagged/Romeo/{commit}/{source_path}"


def _stage_plugin_map(
    romeo_repo: Path, commit: str, output: Path, mapping: dict[str, str],
    assets_by_plugin: dict[str, list[dict]],
) -> list[str]:
    output.mkdir(parents=True, exist_ok=True)
    for old in output.iterdir():
        if old.is_file() and old.suffix.lower() in {".lpx", ".plugin"}:
            old.unlink()

    staged = []
    for filename, source_path in mapping.items():
        data = _read_romeo_file(romeo_repo, commit, source_path)
        text = data.decode("utf-8-sig", "strict")
        if not text.lstrip().startswith("#!"):
            raise RuntimeError(f"Romeo plugin has no Loon metadata header: {source_path}")
        for asset in assets_by_plugin.get(filename, []):
            old_url = asset["upstream_url"]
            if old_url not in text:
                raise RuntimeError(
                    f"Declared {asset['kind']} dependency not referenced by {filename}: {old_url}"
                )
            asset_data = _read_romeo_file(romeo_repo, commit, asset["source_path"])
            if not asset_data.strip():
                raise RuntimeError(f"Romeo runtime asset is empty: {asset['source_path']}")
            text = text.replace(old_url, _pinned_asset_url(commit, asset["source_path"]))
        if "raw.githubusercontent.com/zmjde/loon-plugins/" in text:
            raise RuntimeError(f"Unmigrated zmjde Raw dependency remains in {filename}")
        (output / filename).write_text(text, encoding="utf-8")
        staged.append(filename)
    return sorted(staged)


def stage(
    romeo_repo: Path, commit: str, output: Path, repo_root: Path,
    zmjde_output: Path | None = None,
) -> dict:
    if not (romeo_repo / ".git").exists():
        raise RuntimeError(f"Not a Romeo git checkout: {romeo_repo}")

    assets_by_plugin: dict[str, list[dict]] = {}
    for asset in RUNTIME_ASSETS:
        assets_by_plugin.setdefault(asset["plugin"], []).append(asset)

    romeo_files = _stage_plugin_map(
        romeo_repo, commit, output, ROMEO_PLUGIN_MAP, assets_by_plugin
    )

    # Keep the one known nested CDN dependency explicit and fail closed if its
    # reference disappears or silently changes upstream.
    for dependency in MANIFEST["external_runtime_dependencies"]:
        asset_text = _read_romeo_file(
            romeo_repo, commit, dependency["referenced_by"]
        ).decode("utf-8-sig", "strict")
        if dependency["url"] not in asset_text:
            raise RuntimeError(
                "Declared external runtime dependency is missing from "
                + dependency["referenced_by"] + ": " + dependency["url"]
            )

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
            f"Expected {EXPECTED_PLUGIN_FILES} Romeo/AOOMEE compatibility plugins, found {len(staged)}"
        )

    zmjde_files: list[str] = []
    if zmjde_output is not None:
        zmjde_files = _stage_plugin_map(
            romeo_repo, commit, zmjde_output, ZMJDE_PLUGIN_MAP, assets_by_plugin
        )
        if len(zmjde_files) != EXPECTED_ZMJDE_PLUGIN_FILES:
            raise RuntimeError(
                f"Expected {EXPECTED_ZMJDE_PLUGIN_FILES} Romeo-mapped former zmjde plugins, "
                f"found {len(zmjde_files)}"
            )
        metadata = {
            "upstream_repository": MANIFEST["upstream_repository"],
            "upstream_commit": commit,
            "source_mode": "Romeo manifest mapping; historical zmjde merge slots",
            "app_plugin_paths": list(ZMJDE_APP_MAP.values()),
            "general_plugin_paths": list(ZMJDE_GENERAL_MAP.values()),
            "runtime_assets": list(RUNTIME_ASSETS),
            "external_runtime_dependencies": MANIFEST["external_runtime_dependencies"],
        }
        (zmjde_output / ".romeo-source.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "romeo_commit": commit,
        "romeo_plugin_files": len(ROMEO_PLUGIN_MAP),
        "legacy_snapshot_files": list(LEGACY_SNAPSHOTS),
        "staged_plugin_files": staged,
        "former_zmjde_plugin_files": len(zmjde_files),
        "former_zmjde_staged_files": zmjde_files,
        "runtime_assets_pinned": [
            {"plugin": a["plugin"], "kind": a["kind"], "source_path": a["source_path"]}
            for a in RUNTIME_ASSETS
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--romeo-repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, help="Former AOOMEE compatibility slot output")
    parser.add_argument("--zmjde-output", help="Former zmjde compatibility slot output; sourced from Romeo")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    result = stage(
        Path(args.romeo_repo),
        args.commit,
        Path(args.output),
        Path(args.repo_root),
        Path(args.zmjde_output) if args.zmjde_output else None,
    )
    print("[romeo-stage] " + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
