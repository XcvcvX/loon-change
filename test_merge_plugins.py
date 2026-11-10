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
    def run_merge(self, base_text, extra_text, myblockads_text=None, return_stdout=False):
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
        output = out.read_text(encoding="utf-8")
        return (output, result.stdout) if return_stdout else output

    def test_repeated_sections_are_accumulated(self):
        output = self.run_merge(
            "[Rewrite]\n^https://one.example.com/a reject\n"
            "[Rewrite]\n^https://two.example.com/b reject\n[MITM]\nhostname = one.example.com,two.example.com\n",
            "[Rewrite]\n^https://three.example.com/c reject\n")
        self.assertIn("one.example.com/a", output)
        self.assertIn("two.example.com/b", output)
        self.assertIn("three.example.com", output)

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

    def test_ip_literals_are_never_added_to_mitm_but_rewrite_rules_remain(self):
        output, stdout = self.run_merge(
            "[Rewrite]\n^https://103.37.155.60/ad reject\n"
            "^https://[2001:db8::1]/track reject\n"
            "[MITM]\nhostname = 103.37.155.60,[2001:db8::1],ads.example.com\n",
            "[Rewrite]\n^https://118.178.214.118/config reject\n"
            "[MITM]\nhostname = 118.178.214.118\n",
            return_stdout=True)
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        self.assertNotIn("103.37.155.60", mitm_line)
        self.assertNotIn("118.178.214.118", mitm_line)
        self.assertNotIn("2001:db8::1", mitm_line)
        self.assertIn("MITM 自愈补全 0 个", stdout)
        # 只过滤 MITM hostname，不删除原有 IP 目标 Rewrite 拦截规则。
        self.assertIn("103.37.155.60/ad", output)
        self.assertIn("118.178.214.118", output)
        self.assertIn("/config", output)
        self.assertIn("2001:db8::1", output)

    def test_lowercase_domain_suffix_rule_is_normalized(self):
        output = self.run_merge(
            "[Rewrite]\n[MITM]\nhostname = \n",
            "[Rule]\nDOMAIN-suffix,anythinktech.com,reject\n")
        self.assertIn("DOMAIN-SUFFIX,anythinktech.com,REJECT", output)
        self.assertNotIn("DOMAIN-suffix", output)

    def test_standard_wildcard_domain_is_still_preserved(self):
        output = self.run_merge(
            "[Rewrite]\n^https://ads.example.com/ad reject\n"
            "[MITM]\nhostname = *.example.com\n",
            "[Rewrite]\n[MITM]\nhostname = \n")
        self.assertIn("*.example.com", output)

    def test_wildcard_mitm_does_not_cover_apex_domain(self):
        output = self.run_merge(
            "[Rewrite]\n^https://example.com/ad reject\n"
            "[MITM]\nhostname = *.example.com\n",
            "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        self.assertIn("example.com", mitm_line)

    def test_valid_unlisted_tld_is_not_dropped_from_mitm(self):
        output = self.run_merge(
            "[Rewrite]\n[MITM]\nhostname = \n",
            "[Rewrite]\n^https://ads.example.photography/ad reject\n"
            "[MITM]\nhostname = ads.example.photography\n")
        self.assertIn("ads.example.photography", output)


if __name__ == "__main__":
    unittest.main()
