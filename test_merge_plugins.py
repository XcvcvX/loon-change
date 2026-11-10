#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for merge_plugins.py; all inputs are local fixtures."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MERGER = Path(__file__).with_name("merge_plugins.py")


class MergeIntegrationTests(unittest.TestCase):
    def run_merge(self, base_text, extra_text, myblockads_text=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        base = root / "base.plugin"
        extra = root / "extra.plugin"
        out = root / "merged.plugin"
        base.write_text(base_text, encoding="utf-8")
        extra.write_text(extra_text, encoding="utf-8")
        command = [sys.executable, str(MERGER), "--base", str(base),
                   "--extra", str(extra), "--filter", "none",
                   "--myblockads", "none", "--out", str(out)]
        if myblockads_text is not None:
            myblockads = root / "myblockads.lpx"
            myblockads.write_text(myblockads_text, encoding="utf-8")
            command[command.index("--myblockads") + 1] = str(myblockads)
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        return out.read_text(encoding="utf-8")

    def test_repeated_sections_are_accumulated(self):
        output = self.run_merge(
            "[Rewrite]\n^https://one.example.com/a reject\n"
            "[Rewrite]\n^https://two.example.com/b reject\n[MITM]\nhostname = one.example.com,two.example.com\n",
            "[Rewrite]\n^https://three.example.com/c reject\n")
        self.assertIn("one.example.com/a", output)
        self.assertIn("two.example.com/b", output)
        self.assertIn("three.example.com/c", output)

    def test_reject_variants_are_not_collapsed(self):
        output = self.run_merge(
            "[Rewrite]\n^https://same.example.com/ad reject\n[MITM]\nhostname = same.example.com\n",
            "[Rewrite]\n^https://same.example.com/ad reject-img\n")
        self.assertIn("^https://same.example.com/ad reject", output)
        self.assertIn("reject_img(200)", output)



    def test_legacy_and_v2_alias_of_same_reject_action_deduplicate(self):
        output = self.run_merge(
            "[Rewrite]\n^https://same.example.com/image reject-img\n[MITM]\nhostname = same.example.com\n",
            "[Rewrite]\n^https://same.example.com/image reject-img\n")
        self.assertEqual(output.count("same.example.com/image"), 1)

    def test_mitm_host_declared_by_one_source_is_kept_for_another_sources_rule(self):
        output = self.run_merge(
            "[Rewrite]\n^https://shared.example.com/ad reject\n[MITM]\nhostname = \n",
            "[Rewrite]\n[MITM]\nhostname = \n",
            "[Rewrite]\n[MITM]\nhostname = shared.example.com\n")
        self.assertIn("shared.example.com", output)


    def test_unparseable_host_regex_disables_aggressive_mitm_pruning(self):
        output = self.run_merge(
            "[Rewrite]\n^https://(?<host>[^.]+)\\.example\\.com/ad reject\n"
            "[MITM]\nhostname = ads.example.com\n",
            "[Rewrite]\n[MITM]\nhostname = \n")
        self.assertIn("ads.example.com", output)

    def test_valid_unlisted_tld_is_not_dropped_from_mitm(self):
        output = self.run_merge(
            "[Rewrite]\n[MITM]\nhostname = \n",
            "[Rewrite]\n^https://ads.example.photography/ad reject\n"
            "[MITM]\nhostname = ads.example.photography\n")
        self.assertIn("ads.example.photography", output)


if __name__ == "__main__":
    unittest.main()
