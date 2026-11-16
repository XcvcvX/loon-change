#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply narrowly scoped, fail-closed overrides to the vendored Amap plugin."""
import argparse
from pathlib import Path

# This standalone rule is already covered by the grouped rule below.
DUPLICATE_HOTWORD_RULE = (
    r'request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/shield\/search\/new_hotword\?/i '
    r'then reject_dict(200)'
)
CANONICAL_GROUPED_RULE = (
    r'request if ${url} ~= /^https:\/\/m5\.amap\.com\/ws\/(?:mapapi\/hint_text\/offline_data|message\/notice\/list|shield\/search\/new_hotword)/i '
    r'then reject_dict(200)'
)
HOTWORD_MARKER = "search/new_hotword"


def _normalize(line):
    # Loon plugin serialization may vary the number of backslashes around regex escapes.
    return line.strip().replace("\\", "")


def apply(text):
    """Remove only the exact duplicate hotword request rule; reject upstream drift."""
    lines = text.splitlines()
    output = []
    section = ""
    duplicate_count = 0
    grouped_count = 0
    unexpected = []
    duplicate_normalized = _normalize(DUPLICATE_HOTWORD_RULE)
    grouped_normalized = _normalize(CANONICAL_GROUPED_RULE)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(line)
            continue
        normalized = _normalize(stripped)
        if section != "Rewrite" or HOTWORD_MARKER not in normalized:
            output.append(line)
            continue
        if normalized == duplicate_normalized:
            duplicate_count += 1
            continue
        if normalized == grouped_normalized:
            grouped_count += 1
            output.append(line)
            continue
        unexpected.append(stripped)
        output.append(line)

    if unexpected:
        raise ValueError("Amap hotword rule changed; refusing an unreviewed override")
    if grouped_count != 1:
        raise ValueError("Amap grouped hotword rule inventory changed; expected exactly one")
    if duplicate_count > 1:
        raise ValueError("duplicate standalone Amap hotword rules; refusing ambiguous cleanup")
    return "\n".join(output) + ("\n" if text.endswith("\n") else ""), duplicate_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    args = parser.parse_args()
    path = Path(args.plugin)
    original = path.read_text(encoding="utf-8-sig")
    updated, removed = apply(original)
    path.write_text(updated, encoding="utf-8")
    print("[amap-local-overrides] PASS: removed %d duplicate hotword request rule(s)" % removed)


if __name__ == "__main__":
    main()
