#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cache BaiduMap RepHead segment offsets in the initial binary header scan."""
import argparse
from pathlib import Path

MARKER = "// loon-change: Baidu protobuf target segment offset cache v1"
OLD = "  const name = messageHead.name;\n  const targetDataLength = messageHead.length;"
NEW = OLD + "\n  " + MARKER + "\n  const targetDataOffset = messageHead.offset;"


REBUILD_MARKER = "// loon-change: Baidu protobuf segment rebuild without chunks v1"
REBUILD_OLD_START = "  const chunks = [];\n  let sourceCursor = 0;\n  let outputLength = 0;"
REBUILD_OLD_END = "  const beginOffset = 4;"
REBUILD_NEW = """  // loon-change: Baidu protobuf segment rebuild without chunks v1
  let sourceCursor = 0;
  let outputLength = 0;
  const segmentsLength = segments.length;
  // First pass computes final offsets and validates replacements without allocating chunk views.
  for (let i = 0; i < segmentsLength; i++) {
    const segment = segments[i];
    if (segment.offset < sourceCursor) {
      throw new Error("BaiduMap segments overlap");
    }
    outputLength += segment.offset - sourceCursor;
    const replacement = replacements[segment.index];
    if (replacement !== undefined && replacement !== null && !(replacement instanceof Uint8Array)) {
      throw new Error("BaiduMap replacement segment must be Uint8Array");
    }
    const replacementLength = replacement === undefined || replacement === null
      ? segment.length
      : replacement.byteLength;
    segment.header.offset = outputLength;
    segment.header.length = replacementLength;
    outputLength += replacementLength;
    sourceCursor = segment.offset + segment.length;
  }
  if (sourceCursor < payloadLength) outputLength += payloadLength - sourceCursor;

  // One payload allocation; copy source ranges and replacements directly into their final positions.
  const payload = new Uint8Array(outputLength);
  sourceCursor = 0;
  let payloadWrite = 0;
  for (let i = 0; i < segmentsLength; i++) {
    const segment = segments[i];
    if (segment.offset > sourceCursor) {
      const gapLength = segment.offset - sourceCursor;
      payload.set(binaryBody.subarray(
        dataBeginOffset + sourceCursor,
        dataBeginOffset + segment.offset
      ), payloadWrite);
      payloadWrite += gapLength;
    }
    const replacement = replacements[segment.index];
    const part = replacement === undefined || replacement === null
      ? binaryBody.subarray(
          dataBeginOffset + segment.offset,
          dataBeginOffset + segment.offset + segment.length
        )
      : replacement;
    payload.set(part, payloadWrite);
    payloadWrite += part.byteLength;
    sourceCursor = segment.offset + segment.length;
  }
  if (sourceCursor < payloadLength) {
    payload.set(binaryBody.subarray(dataBeginOffset + sourceCursor), payloadWrite);
  }

"""
def optimize_segment_rebuild_without_chunks(source: str) -> str:
    start = source.find("function assembleBaiduResponseSegments(")
    if start < 0:
        return source
    end = source.index("\n}\n", start) + 2
    helper = source[start:end]
    if REBUILD_MARKER in helper:
        if helper.count(REBUILD_MARKER) != 1 or "const chunks = [];" in helper or "chunks.push(" in helper:
            raise ValueError("BaiduMap chunk-free rebuild marker/structure drift")
        for required in ("const payload = new Uint8Array(outputLength);", "payload.set(part, payloadWrite);", "const segmentsLength = segments.length;"):
            if required not in helper:
                raise ValueError("BaiduMap chunk-free rebuild structure drift")
        return source
    if helper.count(REBUILD_OLD_START) != 1 or helper.count(REBUILD_OLD_END) != 1:
        raise ValueError("BaiduMap segment rebuild anchor drift; refusing optimization")
    left = helper.index(REBUILD_OLD_START)
    right = helper.index(REBUILD_OLD_END, left)
    helper = helper[:left] + REBUILD_NEW + helper[right:]
    if "const chunks = [];" in helper or "chunks.push(" in helper:
        raise ValueError("BaiduMap chunk-free rebuild postcondition failed")
    return source[:start] + helper + source[end:]



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
        return optimize_segment_rebuild_without_chunks(source)
    if source.count(OLD) != 1:
        raise ValueError("BaiduMap header scan anchor drift; refusing optimization")
    source = source.replace(OLD, NEW, 1)
    start = source.index("// loon-change: Baidu protobuf target-only byte views v1")
    end = source.index("\n}\n\nif(invalidSegmentLayout || !adsFound", start)
    loop = source[start:end].replace("messageHead.offset", "targetDataOffset")
    loop = loop.replace("const targetDataOffset = targetDataOffset;", "const targetDataOffset = messageHead.offset;", 1)
    source = source[:start] + loop + source[end:]
    return optimize_source(source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    path = Path(args.source)
    path.write_text(optimize_source(path.read_text(encoding="utf-8")), encoding="utf-8")
    print("BaiduMap target segment offset reads cached")


if __name__ == "__main__":
    main()
