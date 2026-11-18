import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stage_romeo_plugins import (
    EXPECTED_PLUGIN_FILES,
    LEGACY_SNAPSHOTS,
    MANIFEST,
    ROMEO_PLUGIN_MAP,
    RUNTIME_ASSETS,
    ZMJDE_APP_MAP,
    ZMJDE_GENERAL_MAP,
    ZMJDE_PLUGIN_MAP,
    stage,
)


ROOT = Path(__file__).resolve().parent


class RomeoPluginMigrationTests(unittest.TestCase):
    def test_manifest_is_the_single_complete_mapping(self):
        self.assertEqual(len(ROMEO_PLUGIN_MAP), 24)
        self.assertEqual(len(set(ROMEO_PLUGIN_MAP)), len(ROMEO_PLUGIN_MAP))
        self.assertEqual(len(set(ROMEO_PLUGIN_MAP.values())), len(ROMEO_PLUGIN_MAP))
        self.assertEqual(EXPECTED_PLUGIN_FILES, 31)
        self.assertEqual(len(ZMJDE_APP_MAP), 5)
        self.assertEqual(len(ZMJDE_GENERAL_MAP), 3)
        self.assertEqual(len(ZMJDE_PLUGIN_MAP), 8)
        self.assertTrue(all(path.startswith("Modules/Loon/Kelee/Official/")
                            for path in ZMJDE_PLUGIN_MAP.values()))


    def test_wechat_and_weidian_plugins_and_all_runtime_scripts_are_mapped(self):
        expected = {
            "Weixin_Official_Accounts_remove_ads.lpx":
                "Modules/Loon/Kelee/Weixin_Official_Accounts_remove_ads.lpx",
            "WexinMiniPrograms_Remove_ads.lpx":
                "Modules/Loon/Kelee/WexinMiniPrograms_Remove_ads.lpx",
            "Weidian_remove_ads.lpx":
                "Modules/Loon/Kelee/Weidian_remove_ads.lpx",
        }
        for filename, source_path in expected.items():
            self.assertEqual(ROMEO_PLUGIN_MAP[filename], source_path)
        assets = {(item["plugin"], item["source_path"]) for item in RUNTIME_ASSETS}
        self.assertEqual(sum(plugin == "WexinMiniPrograms_Remove_ads.lpx" for plugin, _ in assets), 12)
        self.assertEqual(sum(plugin == "Weidian_remove_ads.lpx" for plugin, _ in assets), 2)
        self.assertEqual(sum(plugin == "Weixin_Official_Accounts_remove_ads.lpx" for plugin, _ in assets), 0)

    def test_legacy_snapshots_are_present(self):
        self.assertEqual(len(LEGACY_SNAPSHOTS), 7)
        for name in LEGACY_SNAPSHOTS:
            with self.subTest(name=name):
                path = ROOT / "sources" / "romeo_legacy" / name
                self.assertTrue(path.is_file(), str(path))
                self.assertTrue(path.read_text(encoding="utf-8-sig").lstrip().startswith("#!"))

    def test_legacy_script_urls_no_longer_depend_on_aoomee_raw(self):
        for name in ("chelaile2.plugin", "qunar-legacy.plugin"):
            with self.subTest(name=name):
                content = (ROOT / "sources" / "romeo_legacy" / name).read_text(encoding="utf-8-sig")
                self.assertNotIn("raw.githubusercontent.com/aoomee/", content)
                self.assertIn("raw.githubusercontent.com/XcvcvX/loon-change/main/scripts/romeo_legacy/", content)

    def test_pdd_uses_split_nonempty_romeo_sources(self):
        self.assertEqual(
            ROMEO_PLUGIN_MAP["pdd-filter.lpx"],
            "Modules/Loon/ishowshu/pdd-filter.lpx",
        )
        self.assertEqual(
            ROMEO_PLUGIN_MAP["pdd-rewrite.lpx"],
            "Modules/Loon/ishowshu/pdd-rewrite.lpx",
        )
        self.assertNotIn("Modules/Loon/ishowshu/pdd.lpx", ROMEO_PLUGIN_MAP.values())

    def test_former_zmjde_assets_are_mapped_to_romeo_files(self):
        self.assertEqual(len(RUNTIME_ASSETS), 19)
        by_plugin = {item["plugin"]: item for item in RUNTIME_ASSETS}
        self.assertEqual(
            by_plugin["PinDuoDuo_remove_ads.lpx"]["source_path"],
            "Modules/JavaScript/Kelee/PinDuoDuo_remove_ads/kelee.one_PinDuoDuo_remove_ads.js",
        )
        self.assertEqual(
            by_plugin["Taobao_remove_ads.lpx"]["source_path"],
            "Modules/JavaScript/Kelee/Taobao_remove_ads/kelee.one_Taobao_remove_ads.js",
        )
        self.assertEqual(
            by_plugin["smzdm_remove_ads.lpx"]["source_path"],
            "Modules/JavaScript/Kelee/smzdm_remove_ads/kelee.one_home_smzdm_remove_ads.jq",
        )
        self.assertEqual(
            by_plugin["goofish.lpx"]["source_path"],
            "Modules/JavaScript/ishowshu/goofish/ishowshu_goofish.js",
        )
        self.assertEqual(
            by_plugin["12306.lpx"]["source_path"],
            "Modules/JavaScript/fmz200/12306/kokoryh_12306.js",
        )
        self.assertTrue(MANIFEST["external_runtime_dependencies"])

    def test_pins_romeo_urls_without_consuming_rule_delimiters(self):
        from stage_romeo_plugins import _pin_romeo_references
        commit = "c" * 40
        source = (
            'response if ${url} ~= /example/ then script("'
            'https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/fmz200/12306/kokoryh_12306.js",'
            ' tag="12306")'
        )
        with patch("stage_romeo_plugins._read_romeo_file", return_value=b"// asset"):
            result = _pin_romeo_references(source, Path("."), commit)
        expected = (
            "https://raw.githubusercontent.com/ifflagged/Romeo/" + commit
            + "/Modules/JavaScript/fmz200/12306/kokoryh_12306.js"
        )
        self.assertIn(expected + '",', result)
        self.assertNotIn("Romeo/raw/main", result)


    def test_pins_all_romeo_reference_forms_in_a_merged_plugin(self):
        from stage_romeo_plugins import _pin_romeo_references
        commit = "d" * 40
        source = (
            'script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/a.js")\n'
            'script("https://raw.githubusercontent.com/ifflagged/Romeo/main/Modules/JavaScript/b.js")\n'
        )
        with patch("stage_romeo_plugins._read_romeo_file", return_value=b"// pinned asset"):
            result = _pin_romeo_references(source, Path("."), commit)
        prefix = "https://raw.githubusercontent.com/ifflagged/Romeo/" + commit + "/"
        self.assertIn(prefix + "Modules/JavaScript/a.js", result)
        self.assertIn(prefix + "Modules/JavaScript/b.js", result)
        self.assertNotIn("Romeo/raw/main/", result)
        self.assertNotIn("Romeo/main/", result)

    def test_romeo_reference_pinning_fails_closed_when_asset_is_missing(self):
        from stage_romeo_plugins import _pin_romeo_references
        source = 'script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/missing.js")'
        with patch("stage_romeo_plugins._read_romeo_file", side_effect=RuntimeError("missing asset")):
            with self.assertRaisesRegex(RuntimeError, "missing asset"):
                _pin_romeo_references(source, Path("."), "e" * 40)

    def test_stage_builds_both_compatibility_slots_from_one_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "romeo"
            (repo / ".git").mkdir(parents=True)
            primary = root / "plugins"
            former_zmjde = root / "zmjde" / "Plugin"
            commit = "a" * 40

            asset_by_plugin = {}
            for asset in RUNTIME_ASSETS:
                asset_by_plugin.setdefault(asset["plugin"], []).append(asset)

            def fake_read(_repo, _commit, source_path):
                if source_path.endswith((".lpx", ".plugin")):
                    plugin_name = Path(source_path).name
                    assets = asset_by_plugin.get(plugin_name, [])
                    urls = "\\n".join(item["upstream_url"] for item in assets)
                    return ("#!name=fixture\\n[Rewrite]\\n" + urls + "\\n").encode()
                for dependency in MANIFEST["external_runtime_dependencies"]:
                    if source_path == dependency["referenced_by"]:
                        return ("// Romeo asset fixture\\n" + dependency["url"] + "\\n").encode()
                return b"// Romeo asset fixture\\n"

            with patch("stage_romeo_plugins._read_romeo_file", side_effect=fake_read):
                result = stage(repo, commit, primary, ROOT, former_zmjde)

            self.assertEqual(result["romeo_plugin_files"], 21)
            self.assertEqual(result["former_zmjde_plugin_files"], 8)
            self.assertEqual(len(result["staged_plugin_files"]), EXPECTED_PLUGIN_FILES)
            self.assertEqual(len(list(former_zmjde.glob("*.lpx"))), 8)
            meta = json.loads((former_zmjde / ".romeo-source.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["upstream_commit"], commit)
            self.assertEqual(meta["upstream_repository"], MANIFEST["upstream_repository"])
            for asset in RUNTIME_ASSETS:
                slot_dir = primary if asset["slot"] == "aoomee_compat" else former_zmjde
                staged = (slot_dir / asset["plugin"]).read_text(encoding="utf-8")
                self.assertIn(
                    f"https://raw.githubusercontent.com/ifflagged/Romeo/{commit}/{asset['source_path']}",
                    staged,
                )
                self.assertNotIn(asset["upstream_url"], staged)


if __name__ == "__main__":
    unittest.main()
