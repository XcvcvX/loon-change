#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair known invalid legacy Script argument encodings in the merged Loon plugin."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

MAASEA_RESPONSE = "Maasea_youtube.response.js"
MAASEA_REQUEST = "Maasea_youtube.request.js"
ARGUMENT_RENAMES = {
    "屏蔽上传按钮": ("blockUpload", "switch,true,false"),
    "屏蔽选段按钮": ("blockImmersive", "switch,true,false"),
    "屏蔽Shorts按钮": ("blockShorts", "switch,false,true"),
    "字幕翻译语言": ("captionLang", "input,off"),
    "启用调试模式": ("debug", "switch,false,true"),
}

def _rename_argument_declarations(lines):
    section, out = None, []
    for line in lines:
        match = re.match(r'^\[([^]]+)\]\s*$', line.strip())
        if match:
            section = match.group(1).lower()
            out.append(line)
            continue
        if section == "argument":
            for old, (new, typed_prefix) in ARGUMENT_RENAMES.items():
                m = re.match(rf'^(\s*){re.escape(old)}\s*=\s*(.*)$', line)
                if m:
                    rest = m.group(2)
                    suffix_match = re.search(r',\s*tag=', rest)
                    suffix = rest[suffix_match.start():] if suffix_match else ""
                    line = f"{m.group(1)}{new}={typed_prefix}{suffix}"
                    break
        out.append(line)
    return out

def repair_plugin_text(text):
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = _rename_argument_declarations(text.splitlines())
    counts = {"legacy_argument_lists": 0, "maasea_response": 0,
              "maasea_request": 0, "requires_body_boolean": 0,
              "bare_enable_variables": 0}
    in_script = False
    for index, line in enumerate(lines):
        section = re.match(r'^\[([^]]+)\]\s*$', line.strip())
        if section:
            in_script = section.group(1).lower() == "script"
            continue
        if not in_script or not line.strip() or line.lstrip().startswith("#"):
            continue
        line, n = re.subn(r'argument=\[\{([^]\r\n]+)\}\]', lambda m: 'argument={' + m.group(1).replace('},{', ',') + '}', line)
        counts["legacy_argument_lists"] += n
        if MAASEA_RESPONSE in line and "argument=" in line:
            counts["maasea_response"] += 1
            line = re.sub(r',\s*argument=.*$', '', line)
            line += ', argument={captionLang,blockUpload,blockImmersive,blockShorts,debug}'
        elif MAASEA_REQUEST in line and "argument=" in line:
            counts["maasea_request"] += 1
            line = re.sub(r',\s*argument=.*$', '', line)
            line += ', argument={captionLang}'
        line, n = re.subn(
            r'(\benable\s*=\s*)([A-Za-z_][A-Za-z0-9_]*)(?=\s*(?:,|$))',
            lambda match: (
                match.group(0) if match.group(2).lower() in {"true", "false"}
                else match.group(1) + "${" + match.group(2) + "}"
            ),
            line,
        )
        counts["bare_enable_variables"] += n
        line, n = re.subn(r'\brequires-body=1\b', 'requires-body=true', line)
        counts["requires_body_boolean"] += n
        lines[index] = line
    if any(re.search(r"argument=\[\{", line) for line in lines):
        raise ValueError("Unrepaired legacy argument list syntax remains in [Script]")
    if any(re.search(r"requires-body=1\b", line) for line in lines):
        raise ValueError("Non-Boolean requires-body value remains in [Script]")
    if any(MAASEA_RESPONSE in line or MAASEA_REQUEST in line for line in lines):
        missing = [name for name in ("blockUpload", "blockImmersive", "blockShorts", "captionLang", "debug")
                   if not any(re.match(rf'^\s*{name}\s*=', line) for line in lines)]
        if missing:
            raise ValueError("Maasea YouTube script parameter declarations missing: " + ", ".join(missing))
        if counts["maasea_response"] != 1 or counts["maasea_request"] != 1:
            raise ValueError("Expected exactly one Maasea response and request script entry; "
                             f"found {counts['maasea_response']} and {counts['maasea_request']}")
    return newline.join(lines) + (newline if text.endswith(("\n", "\r")) else ""), counts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", required=True, help="Merged Loon plugin path")
    path = Path(parser.parse_args().plugin)
    repaired, counts = repair_plugin_text(path.read_text(encoding="utf-8"))
    path.write_text(repaired, encoding="utf-8")
    print("Script configuration repair: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

if __name__ == "__main__":
    main()
