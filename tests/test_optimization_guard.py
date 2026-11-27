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
            "scripts/jingdong/jd.js": [
                "function compactJdInPlace(items, mode, welcomeExtraEnabled)",
                "function compactJdServiceList(items)",
                'compactJdInPlace(obj.floorList, "welcome", welcomeExtraEnabled);',
                'compactJdInPlace(obj.floors, "order");',
                "$done(modified ? { body: JSON.stringify(obj) } : {});",
            ],
            "scripts/taobao/taobao.js": [
                "function clearArray(target, key)",
                "const poplayerEnabled = obj?.enable;",
                "if (poplayerEnabled) {",
                "obj.enable = false;",
                "// loon-change: Taobao splash array length single-read cache v1",
                "const sectionCount = Array.isArray(sections) ? sections.length : 0;",
                "const itemCount = Array.isArray(splashItems) ? splashItems.length : 0;",
                "if (itemCount === 0) continue;",
                "$done(modified ? {body: JSON.stringify(obj)} : {});",
            ],
            "scripts/xianyu/goofish.js": [
                "// loon-change: Goofish per-response allocation hot-path optimization v1",
                "const isSupportedPath =",
                "let hasKeys = false",
                "for (const key in node)",
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


    def test_final_plugin_manifest_protects_native_pdd_jq_migration(self):
        manifest_path = Path(__file__).with_name("optimization_output_invariants.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = {item["path"]: item for item in manifest["artifacts"]}
        self.assertIn("allAdRewrite.plugin", artifacts)
        required = artifacts["allAdRewrite.plugin"]["required"]
        forbidden = artifacts["allAdRewrite.plugin"]["forbidden"]
        for token in (
            "api.pinduoduo.com",
            "response.json.jq(",
            "result.dy_module.irregular_banner_dy",
            "result.bottom_tabs?",
            "result.buffer_bottom_tabs?",
            "result.all_top_opts?",
        ):
            self.assertIn(token, required)
        self.assertIn("pdd-homepage.js", forbidden)
        self.assertIn("ishowshu_pdd.js", forbidden)
        self.assertEqual(
            validate(Path(__file__).resolve().parent, manifest_path),
            ["allAdRewrite.plugin"],
        )

if __name__ == "__main__":
    unittest.main()
