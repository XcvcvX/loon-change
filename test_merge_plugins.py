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
    def run_merge(self, base_text, extra_text, myblockads_text=None, return_stdout=False, amap_text=None):
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
        if amap_text is not None:
            amap = root / "Amap.lpx"
            amap.write_text(amap_text, encoding="utf-8")
            command += ["--amap", str(amap)]
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        output = out.read_text(encoding="utf-8")
        return (output, result.stdout) if return_stdout else output


    def test_amap_app_has_highest_priority_and_keeps_distinct_actions(self):
        base = r"""[Rule]
DOMAIN,amap.com,DIRECT
[Rewrite]
request if ${url} ~= /^https:\/\/m5\.amap\.com\/same\?/i then reject_dict(200)
response if ${url} ~= /^https:\/\/m5\.amap\.com\/edit\?/i then response.json.delete("legacy")
[MITM]
hostname = m5.amap.com
"""
        amap = r"""[Rule]
DOMAIN,amap.com,REJECT
[Rewrite]
request if ${url} ~= /^https:\/\/m5\.amap\.com\/same\?/ then reject_dict(200)
response if ${url} ~= /^https:\/\/m5\.amap\.com\/edit\?/ then response.json.delete("promotion")
[Script]
response if ${url} ~= /^https:\/\/m5\.amap\.com\/script\?/ then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js")
response if ${url} ~= /^https:\/\/m5\.amap\.com\/recommend\?/ then response.json.jq_file("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/loon_Amap.recommend.jq")
response if ${url} ~= /^https:\/\/m5\.amap\.com\/updatable\?/ then response.json.jq_file("https://kelee.one/Resource/JQLang/Amap/updatable.jq")
response if ${url} ~= /^https:\/\/m5\.amap\.com\/poi\?/ then response.json.jq_file("https://kelee.one/Resource/JQLang/Amap/search_poi_detail.jq")
[MitM]
hostname = *.amap.com
"""
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n", amap_text=amap)
        rewrite = output.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        script = output.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        same = [line for line in rewrite.splitlines() if "/same" in line]
        self.assertEqual(len(same), 1)
        self.assertNotIn("/i then", same[0])
        edit = [line for line in rewrite.splitlines() if "/edit" in line]
        self.assertEqual(len(edit), 2)
        self.assertTrue(any('delete("legacy")' in line for line in edit))
        self.assertTrue(any('delete("promotion")' in line for line in edit))
        self.assertIn("DOMAIN,amap.com,REJECT", output)
        self.assertIn("https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/amap/rucu6_amap.js", script)
        for asset in ("rucu6_amap.js", "loon_Amap.recommend.jq", "updatable.jq", "search_poi_detail.jq"):
            self.assertIn("https://raw.githubusercontent.com/XcvcvX/loon-change/main/sources/amap/" + asset, output)
        self.assertNotIn("github.com/ifflagged/Romeo/raw/main", output)
        self.assertNotIn("kelee.one/Resource/JQLang/Amap", output)
        mitm = output.split("[MITM]", 1)[1]
        # The broad upstream wildcard is narrowed to the concrete HTTPS hosts actually guarded.
        self.assertIn("m5.amap.com", mitm)
        self.assertNotIn("*.amap.com", mitm)
        self.assertNotIn("hostname = 103.", mitm)

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

    def test_rewrite_actions_misplaced_in_block_script_are_moved_to_rewrite(self):
        output = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = beehiveapi.58.com\n",
            "[Script]\n"
            "request if ${url} ~= /^https?:\\/\\/beehiveapi\\.58\\.com\\/adplace\\/zcm/ then reject_dict(200)\n"
            "^https?:\\/\\/legacy\\.example\\.com\\/ad reject-dict\n"
            "response if ${url} ~= /^https:\\/\\/api\\.example\\.com/ then script(\"https://cdn.example/script.js\")\n")
        rewrite_pos = output.index("[Rewrite]")
        script_pos = output.index("[Script]")
        self.assertLess(rewrite_pos, script_pos)
        self.assertEqual(output[:script_pos].count("then reject_dict(200)"), 2)
        self.assertIn("legacy\\.example\\.com", output[:script_pos])
        self.assertIn('script("https://cdn.example/script.js")', output[script_pos:])
        self.assertNotIn("then reject_dict(200)", output[script_pos:])



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
