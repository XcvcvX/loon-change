#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

from optimization_guard import validate


class OptimizationGuardTests(unittest.TestCase):
    def test_accepts_all_declared_invariants(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "runtime.js").write_text("// marker\\nfunction compactInPlace() {}\\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 1,
                "artifacts": [{
                    "path": "runtime.js",
                    "required": ["// marker", "function compactInPlace("],
                    "forbidden": ["Array.filter("],
                }],
            }), encoding="utf-8")
            self.assertEqual(validate(root, manifest), ["runtime.js"])

    def test_manifest_covers_recent_high_cost_response_hot_paths(self):
        manifest_path = Path(__file__).with_name("optimization_invariants.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = {item["path"]: item for item in manifest["artifacts"]}
        expected = {
            "scripts/pinduoduo/pdd-homepage.js": [
                "const allowedLinks = new Set([\"index.html\", \"chat_list.html\", \"personal.html\"]);",
                "function compactInPlace(items, keep)",
                "return $done(modified ? { body: JSON.stringify(obj) } : {});",
            ],
            "scripts/jingdong/jd.js": [
                "function compactInPlace(items, keep)",
                "const WELCOME_HOME_EXTRA_EXCLUDE = new Set(",
                "$done(modified ? { body: JSON.stringify(obj) } : {});",
            ],
            "scripts/taobao/taobao.js": [
                "function setIfDifferent(target, key, value)",
                "function clearArray(target, key)",
                "$done(modified ? {body: JSON.stringify(obj)} : {});",
            ],
        }
        for path, tokens in expected.items():
            self.assertIn(path, artifacts)
            for token in tokens:
                self.assertIn(token, artifacts[path]["required"])
        self.assertEqual(validate(Path(__file__).resolve().parent, manifest_path),
                         list(artifacts))

    def test_fails_closed_when_upstream_overwrites_optimization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "runtime.js").write_text("function upstreamOnly() {}\\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 1,
                "artifacts": [{
                    "path": "runtime.js",
                    "required": ["// local optimization marker"],
                    "forbidden": [],
                }],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "required optimization invariant missing"):
                validate(root, manifest)

    def test_fails_closed_when_artifact_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 1,
                "artifacts": [{"path": "missing.js", "required": ["marker"]}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "generated artifact is missing"):
                validate(root, manifest)

    def test_rejects_duplicate_manifest_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "runtime.js").write_text("marker", encoding="utf-8")
            manifest = root / "manifest.json"
            row = {"path": "runtime.js", "required": ["marker"]}
            manifest.write_text(json.dumps({
                "schema_version": 1, "artifacts": [row, row],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate artifact path"):
                validate(root, manifest)


if __name__ == "__main__":
    unittest.main()
