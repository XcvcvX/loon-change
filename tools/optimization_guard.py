#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail closed when generated runtime artifacts lose reviewed local optimizations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(root: Path, manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported optimization invariant manifest schema")

    failures: list[str] = []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("optimization invariant manifest has no artifacts")

    seen: set[str] = set()
    for artifact in artifacts:
        relative = artifact.get("path")
        if not isinstance(relative, str) or not relative or relative in seen:
            raise ValueError("invalid or duplicate artifact path in optimization manifest")
        seen.add(relative)
        path = root / relative
        if not path.is_file():
            failures.append(f"{relative}: generated artifact is missing")
            continue
        content = path.read_text(encoding="utf-8-sig")
        for token in artifact.get("required", []):
            if token not in content:
                failures.append(f"{relative}: required optimization invariant missing: {token}")
        for token in artifact.get("forbidden", []):
            if token in content:
                failures.append(f"{relative}: forbidden regression pattern found: {token}")

    if failures:
        raise ValueError("optimization preservation check failed:\n- " + "\n- ".join(failures))
    return [item["path"] for item in artifacts]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--manifest", type=Path,
        default=Path(__file__).resolve().parents[1] / "optimization_invariants.json",
    )
    args = parser.parse_args()
    checked = validate(args.root.resolve(), args.manifest.resolve())
    print("Optimization preservation check PASS: %d artifacts verified" % len(checked))
    for path in checked:
        print("  - " + path)


if __name__ == "__main__":
    main()
