#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cache BaiduMap RepHead segment offsets in the initial binary header scan."""
import argparse
from pathlib import Path

MARKER = "// loon-change: Baidu protobuf target segment offset cache v1"
OLD = "  const name = messageHead.name;\n  const targetDataLength = messageHead.length;"
NEW = OLD + "\n  " + MARKER + "\n  const targetDataOffset = messageHead.offset;"


def optimize_source(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or source.count("const targetDataOffset = messageHead.offset;") != 1:
            raise ValueError("BaiduMap target segment offset cache marker/structure drift")
        start = source.index("// loon-change: Baidu protobuf target-only byte views v1")
        end = source.index("\n}\n\nif(invalidSegmentLayout || !adsFound", start)
        loop = source[start:end]
        if "messageHead.offset" in loop.replace("const targetDataOffset = messageHead.offset;", ""):
            raise ValueError("BaiduMap repeated target segment offset reads remain")
        if "targetDataOffset > binaryBody.byteLength - dataBeginOffset" not in loop:
            raise ValueError("BaiduMap cached target segment offset is not used for bounds checks")
        return source
    if source.count(OLD) != 1:
        raise ValueError("BaiduMap header scan anchor drift; refusing optimization")
    source = source.replace(OLD, NEW, 1)
    start = source.index("// loon-change: Baidu protobuf target-only byte views v1")
    end = source.index("\n}\n\nif(invalidSegmentLayout || !adsFound", start)
    loop = source[start:end].replace("messageHead.offset", "targetDataOffset")
    loop = loop.replace("const targetDataOffset = targetDataOffset;", "const targetDataOffset = messageHead.offset;", 1)
    source = source[:start] + loop + source[end:]
    if source.count(MARKER) != 1 or "targetDataOffset > binaryBody.byteLength - dataBeginOffset" not in loop:
        raise ValueError("BaiduMap target segment offset cache postcondition failed")
    if "messageHead.offset" in loop.replace("const targetDataOffset = messageHead.offset;", ""):
        raise ValueError("BaiduMap repeated target segment offset reads remain")
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    path = Path(args.source)
    path.write_text(optimize_source(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("BaiduMap target segment offset reads cached")


if __name__ == "__main__":
    main()
