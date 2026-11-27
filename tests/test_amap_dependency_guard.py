#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import tempfile
import unittest
from pathlib import Path

from amap_dependency_guard import (ASSETS, ASSET_UPSTREAM_PATHS, PLUGIN_UPSTREAM_PATH, build_provenance, validate_asset)


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


    def test_detects_asset_drift_against_pinned_romeo_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "romeo"
            assets_dir = root / "assets"
            repo.mkdir()
            assets_dir.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)

            plugin_bytes = ("\n".join(ASSETS) + "\n").encode()
            plugin_repo_path = repo / PLUGIN_UPSTREAM_PATH
            plugin_repo_path.parent.mkdir(parents=True, exist_ok=True)
            plugin_repo_path.write_bytes(plugin_bytes)
            plugin_path = assets_dir / "Amap.lpx"
            plugin_path.write_bytes(plugin_bytes)

            for name, upstream_path in ASSET_UPSTREAM_PATHS.items():
                content = self.fixture(name)
                repo_path = repo / upstream_path
                repo_path.parent.mkdir(parents=True, exist_ok=True)
                repo_path.write_bytes(content)
                (assets_dir / name).write_bytes(content)

            subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, capture_output=True)
            commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            report = build_provenance(assets_dir, plugin_path, commit, repo)
            self.assertEqual(report["upstream_commit"], commit)
            self.assertEqual(report["assets"]["rucu6_amap.js"]["upstream_path"],
                             ASSET_UPSTREAM_PATHS["rucu6_amap.js"])
            self.assertEqual(len(report["assets"]["rucu6_amap.js"]["git_blob_sha1"]), 40)

            (assets_dir / "rucu6_amap.js").write_bytes(self.fixture("rucu6_amap.js") + b"tampered")
            with self.assertRaisesRegex(ValueError, "upstream drift detected"):
                build_provenance(assets_dir, plugin_path, commit, repo)

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
