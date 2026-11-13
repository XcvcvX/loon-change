#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for QX -> Loon conversion safety semantics."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CONVERTER = Path(__file__).with_name("convert_qx2loon.py")


class RewriteConverterTests(unittest.TestCase):
    @staticmethod
    def valid_source(hostnames, extra_lines=()):
        lines = ["#!date=2026-11-13", "hostname = " + hostnames]
        for index in range(20):
            lines.append(
                r"^https?:\\/\\/fixture%02d\\.example\\.com\\/ads\\/ url reject-dict"
                % index
            )
        lines.extend(extra_lines)
        return "\\n".join(lines) + "\\n"

    def test_wildcards_are_preserved_and_public_suffix_wildcards_are_dropped(self):
        source = self.valid_source(
            "wanciwangdata.oss-cn-*.aliyuncs.com,m*.amap.com,api*.futunn.com,*.com.cn,*.com"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source.conf"
            out = root / "out.plugin"
            src.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CONVERTER), "-i", str(src), "-o", str(out)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plugin = out.read_text(encoding="utf-8")
            mitm = plugin.split("[MITM]", 1)[1]
            self.assertIn("wanciwangdata.oss-cn-*.aliyuncs.com", mitm)
            self.assertIn("m*.amap.com", mitm)
            self.assertIn("api*.futunn.com", mitm)
            self.assertNotIn("*.com.cn", mitm)
            self.assertNotIn("*.com,", mitm)
            self.assertNotIn("*.aliyuncs.com", mitm)

    def test_header_scripts_do_not_wait_for_body_and_body_scripts_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header_js = root / "header.js"
            body_js = root / "body.js"
            binary_js = root / "bilibiliProtoA.js"
            for path in (header_js, body_js, binary_js):
                path.write_text("// fixture\n", encoding="utf-8")
            source = self.valid_source(
                "header.example.com,body.example.com,binary.example.com",
                [
                    r"^https?:\\/\\/header\\.example\\.com\\/ url script-response-header " + header_js.as_uri(),
                    r"^https?:\\/\\/body\\.example\\.com\\/ url script-response-body " + body_js.as_uri(),
                    r"^https?:\\/\\/binary\\.example\\.com\\/ url script-response-body " + binary_js.as_uri(),
                ],
            )
            src = root / "source.conf"
            out = root / "out.plugin"
            src.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CONVERTER), "-i", str(src), "-o", str(out)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plugin = out.read_text(encoding="utf-8")
            header_line = next(line for line in plugin.splitlines()
                               if "header.js" in line)
            body_line = next(line for line in plugin.splitlines()
                             if "body.js" in line)
            binary_line = next(line for line in plugin.splitlines()
                               if "bilibiliProtoA.js" in line)
            self.assertNotIn("requires-body=true", header_line)
            self.assertIn("requires-body=true", body_line)
            self.assertIn("requires-body=true", binary_line)
            self.assertIn("binary-body-mode=true", binary_line)

    def test_plain_reject_is_explicit_http_404_but_special_shapes_are_preserved(self):
        source = self.valid_source(
            "api.example.com",
            [
                r"^https?:\\/\\/api\\.example\\.com\\/ad url reject",
                r"^https?:\\/\\/api\\.example\\.com\\/empty url reject-200",
                r"^https?:\\/\\/api\\.example\\.com\\/json url reject-dict",
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source.conf"
            out = root / "out.plugin"
            src.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CONVERTER), "-i", str(src), "-o", str(out)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plugin = out.read_text(encoding="utf-8")
            self.assertIn("then reject(404)", plugin)
            self.assertIn("reject-200", plugin)
            self.assertIn("reject-dict", plugin)


if __name__ == "__main__":
    unittest.main()
