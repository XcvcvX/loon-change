import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from optimize_baidumap import MARKER, REBUILD_MARKER, optimize_segment_rebuild_without_chunks, optimize_source


class BaiduMapOffsetOptimizerTests(unittest.TestCase):
    def test_checked_in_runtime_is_idempotent(self):
        source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")
        self.assertEqual(optimize_source(source), source)

    def test_legacy_header_scan_is_rewritten_once(self):
        source = """// loon-change: Baidu protobuf target-only byte views v1
  const name = messageHead.name;
  const targetDataLength = messageHead.length;
  if (name === "Ads") {
    if (!Number.isInteger(messageHead.offset) ||
        messageHead.offset < 0 ||
        messageHead.offset > binaryBody.byteLength - dataBeginOffset ||
        targetDataLength > binaryBody.byteLength - dataBeginOffset - messageHead.offset) {
      invalidSegmentLayout = true;
    }
    const currentOffset = dataBeginOffset + messageHead.offset;
  }
}

if(invalidSegmentLayout || !adsFound) {}
"""
        result = optimize_source(source)
        self.assertEqual(result.count(MARKER), 1)
        self.assertEqual(result.count("const targetDataOffset = messageHead.offset;"), 1)
        self.assertNotIn("messageHead.offset", result.replace("const targetDataOffset = messageHead.offset;", ""))
        self.assertEqual(optimize_source(result), result)

    def test_segment_rebuild_optimizer_is_idempotent_and_fails_closed(self):
        source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")
        self.assertIn(REBUILD_MARKER, source)
        self.assertEqual(optimize_segment_rebuild_without_chunks(source), source)
        damaged = source.replace("const payload = new Uint8Array(outputLength);", "const payload = new Uint8Array(0);", 1)
        with self.assertRaisesRegex(ValueError, "structure drift"):
            optimize_segment_rebuild_without_chunks(damaged)

    def test_drifted_cache_fails_closed(self):
        source = (ROOT / "scripts/baidumap/baidu-map-protobuf.js").read_text(encoding="utf-8")
        damaged = source.replace(
            "const targetDataOffset = messageHead.offset;",
            "const targetDataOffset = messageHead.other_offset;",
            1,
        )
        with self.assertRaisesRegex(ValueError, "marker/structure drift"):
            optimize_source(damaged)


if __name__ == "__main__":
    unittest.main()
