#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from amap_dependency_guard import ASSETS, build_provenance, validate_asset


class AmapDependencyGuardTests(unittest.TestCase):
    def fixture(self, name):
        markers = ASSETS[name]["markers"]
        return ("// fixture " + ("x" * ASSETS[name]["min_bytes"]) + "\n"
                + "\n".join(markers)).encode()

    def test_validates_all_expected_asset_types(self):
        for name in ASSETS:
            with self.subTest(name=name):
                stats = validate_asset(name, self.fixture(name))
                self.assertGreater(stats["bytes"], 0)
                self.assertEqual(len(stats["sha256"]), 64)

    def test_rejects_empty_and_truncated_files(self):
        for name in ASSETS:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "过小"):
                    validate_asset(name, b"short")

    def test_rejects_html_cloudflare_and_git_lfs(self):
        bad_payloads = (
            b"<!doctype html><html>" + b"x" * 2000,
            b"Attention Required! | Cloudflare " + b"x" * 2000,
            b"version https://git-lfs.github.com/spec/v1\n" + b"x" * 2000,
        )
        for payload in bad_payloads:
            with self.subTest(payload=payload[:30]):
                with self.assertRaises(ValueError):
                    validate_asset("rucu6_amap.js", payload)

    def test_rejects_missing_semantic_markers(self):
        payload = b"// " + b"x" * 3000
        with self.assertRaisesRegex(ValueError, "缺少预期内容标记"):
            validate_asset("rucu6_amap.js", payload)

    def test_builds_commit_and_sha256_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "Amap.lpx"
            plugin.write_text("\n".join(ASSETS), encoding="utf-8")
            for name in ASSETS:
                (root / name).write_bytes(self.fixture(name))
            result = build_provenance(root, plugin, "a" * 40)
            self.assertEqual(result["upstream_commit"], "a" * 40)
            self.assertEqual(set(result["assets"]), set(ASSETS))

    def test_rejects_short_commit_and_missing_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "Amap.lpx"
            plugin.write_text("\n".join(ASSETS), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "40 位 SHA"):
                build_provenance(root, plugin, "abc")
            with self.assertRaisesRegex(ValueError, "缺少高德依赖"):
                build_provenance(root, plugin, "a" * 40)


if __name__ == "__main__":
    unittest.main()
