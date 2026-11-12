#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the standalone R-Store -> Loon rule converter."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CONVERTER = Path(__file__).with_name("convert_filter_qx2loon.py")


class FilterConverterTests(unittest.TestCase):
    def test_httpdns_reject_endpoints_are_excluded_without_widening(self):
        source = """#!date=2026-11-12
#!count=5
ip-cidr,119.29.29.98/32,reject
ip-cidr,119.29.29.99/32,reject-200
ip-cidr,119.29.29.90/32,reject
ip-cidr,119.29.29.98/32,direct
ip-cidr,119.29.29.0/24,reject
host-suffix,ads.example.com,reject
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "source.list"
            list_file = root / "converted.list"
            plugin_file = root / "converted.plugin"
            input_file.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CONVERTER), "--input", str(input_file),
                 "--list", str(list_file), "--plugin", str(plugin_file)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("HTTPDNS 安全排除规则: 2", result.stdout)

            for output in (list_file.read_text(encoding="utf-8"),
                           plugin_file.read_text(encoding="utf-8")):
                rule_lines = [line.strip() for line in output.splitlines()
                              if line.strip().startswith("IP-CIDR,")]
                self.assertNotIn("IP-CIDR,119.29.29.98/32,REJECT,no-resolve",
                                 rule_lines)
                self.assertNotIn("IP-CIDR,119.29.29.99/32,REJECT,no-resolve",
                                 rule_lines)
                self.assertIn("IP-CIDR,119.29.29.90/32,REJECT,no-resolve",
                              rule_lines)
                self.assertIn("IP-CIDR,119.29.29.98/32,DIRECT,no-resolve",
                              rule_lines)
                self.assertIn("IP-CIDR,119.29.29.0/24,REJECT,no-resolve",
                              rule_lines)
                self.assertIn("DOMAIN-SUFFIX,ads.example.com,REJECT", output)
                self.assertIn("119.29.29.98/32", output)
                self.assertIn("119.29.29.99/32", output)


if __name__ == "__main__":
    unittest.main()
