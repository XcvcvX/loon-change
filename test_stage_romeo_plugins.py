import unittest
from pathlib import Path

from stage_romeo_plugins import (
    EXPECTED_PLUGIN_FILES,
    LEGACY_SNAPSHOTS,
    ROMEO_PLUGIN_MAP,
)


ROOT = Path(__file__).resolve().parent


class RomeoPluginMigrationTests(unittest.TestCase):
    def test_mapping_is_complete_and_unambiguous(self):
        self.assertEqual(len(ROMEO_PLUGIN_MAP), 21)
        self.assertEqual(len(set(ROMEO_PLUGIN_MAP)), len(ROMEO_PLUGIN_MAP))
        self.assertEqual(len(set(ROMEO_PLUGIN_MAP.values())), len(ROMEO_PLUGIN_MAP))
        self.assertEqual(EXPECTED_PLUGIN_FILES, 28)

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


if __name__ == "__main__":
    unittest.main()
