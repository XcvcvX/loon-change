#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed syntax guard for Script v2 dynamic enable arguments in Loon plugins."""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
ENABLE_RE = re.compile(r"\b(?:with\s+)?enable\s*=\s*([^,\s]+)", re.I)
ATOMIC_GROUP_RE = re.compile(r"\(?>")
DYNAMIC_VALUE_RE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

def inspect_text(text: str, label: str = "<text>") -> list[str]:
    section = None
    errors: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        header = SECTION_RE.match(raw.strip())
        if header:
            section = header.group(1).strip().lower()
            continue
        if section not in {"script", "rewrite"}:
            continue
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if section == "script":
            for match in ENABLE_RE.finditer(line):
                value = match.group(1).strip().strip("\"'")
                if value.lower() in {"true", "false"} or DYNAMIC_VALUE_RE.fullmatch(value):
                    continue
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    errors.append(
                        f"{label}:{number}: bare Script enable variable {value!r}; "
                        f"use enable=${{{value}}}"
                    )
        if ATOMIC_GROUP_RE.search(line):
            errors.append(f"{label}:{number}: unsupported atomic regex group '(?>...)' in a Loon Script/Rewrite configuration line")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", help="Loon plugin or generated subscription file")
    args = parser.parse_args()
    path = Path(args.plugin)
    errors = inspect_text(path.read_text(encoding="utf-8-sig"), str(path))
    if errors:
        for error in errors:
            print("[Script v2 syntax error] " + error)
        return 1
    print(f"Script v2 syntax guard passed: {path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
