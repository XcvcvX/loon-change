#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "scripts" / "amap" / "amap.js").read_text(encoding="utf-8")


class AmapCanonicalScriptTests(unittest.TestCase):
    def test_canonical_script_covers_rucu6_nearby_route(self):
        self.assertIn('url.includes("/c3frontend/af-nearby/nearby")', SCRIPT)
        self.assertIn('setIfDifferent(obj.data.modules, "banner", {})', SCRIPT)
        self.assertIn('setIfDifferent(obj.data.modules, "contentPoster", {})', SCRIPT)

    def test_canonical_script_preserves_ishowshu_hotword_cleanup(self):
        self.assertIn('url.includes("/shield/search_bff/hotword")', SCRIPT)
        self.assertIn('setIfDifferent(obj.data, "headerHotWord", [])', SCRIPT)
        self.assertIn('setIfDifferent(obj.data, "hotWordWithIcon", [])', SCRIPT)

    def test_profile_cleanup_merges_native_json_allowlists(self):
        for key in ("MyOrderCard", "MineNewFootprintCard", "MineNewBEntranceCardV4"):
            self.assertIn(key, SCRIPT)
        self.assertIn('mode === "myOrderEntrance1"', SCRIPT)
        self.assertIn('mode === "myOrderEntrance2"', SCRIPT)
        self.assertIn('deleteIfPresent(obj.data, "wallet")', SCRIPT)
        for allowed_id in ("id === 7", "id === 8", "id === 10", "id === 17",
                            "id === 1", "id === 32", "id === 9", "id === 14"):
            self.assertIn(allowed_id, SCRIPT)


if __name__ == "__main__":
    unittest.main()
