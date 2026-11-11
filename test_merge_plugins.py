#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for merge_plugins.py; all inputs are local fixtures."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MERGER = Path(__file__).with_name("merge_plugins.py")


class MergeIntegrationTests(unittest.TestCase):
    def run_merge(self, base_text, extra_text, myblockads_text=None, return_stdout=False, amap_text=None, return_provenance=False, apps_files=None, expect_failure=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        base = root / "base.plugin"
        extra = root / "extra.plugin"
        out = root / "merged.plugin"
        provenance = root / "rule-provenance.json"
        base.write_text(base_text, encoding="utf-8")
        extra.write_text(extra_text, encoding="utf-8")
        command = [sys.executable, str(MERGER), "--base", str(base),
                   "--extra", str(extra), "--filter", "none",
                   "--myblockads", "none", "--out", str(out),
                   "--provenance-out", str(provenance)]
        if myblockads_text is not None:
            myblockads = root / "myblockads.lpx"
            myblockads.write_text(myblockads_text, encoding="utf-8")
            command[command.index("--myblockads") + 1] = str(myblockads)
        if amap_text is not None:
            amap = root / "Amap.lpx"
            amap.write_text(amap_text, encoding="utf-8")
            command += ["--amap", str(amap)]
        if apps_files is not None:
            apps = root / "apps"
            apps.mkdir()
            for filename, content in apps_files.items():
                (apps / filename).write_text(content, encoding="utf-8")
            command += ["--apps", str(apps)]
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=30)
        if expect_failure:
            self.assertNotEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            return result.stdout + "\n" + result.stderr
        self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
        output = out.read_text(encoding="utf-8")
        if return_provenance:
            return output, json.loads(provenance.read_text(encoding="utf-8"))
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
response if ${url} ~= /^https:\/\/m5\.amap\.com\/recommend\?/ then response.json.jq_file("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/loon_Amap.recommend.jq")
response if ${url} ~= /^https:\/\/m5\.amap\.com\/updatable\?/ then response.json.jq_file("https://kelee.one/Resource/JQLang/Amap/updatable.jq")
response if ${url} ~= /^https:\/\/m5\.amap\.com\/poi\?/ then response.json.jq_file("https://kelee.one/Resource/JQLang/Amap/search_poi_detail.jq")
[Script]
response if ${url} ~= /^https:\/\/m5\.amap\.com\/script\?/ then script("https://github.com/ifflagged/Romeo/raw/main/Modules/JavaScript/sooyaaabo/Amap/rucu6_amap.js")
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

    def test_active_tencent_httpdns_endpoints_are_not_blocked_by_broad_ip_rule(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n"
            r"request if " + "${url}" + r" ~= /^https?:\/\/119\.29\.29\.\d+\/d/ then reject(200)" + "\n"
            r"request if " + "${url}" + r" ~= /^https?:\/\/119\.29\.29\.98\/health/ then reject(200)" + "\n"
            "[MITM]\nhostname = \n"
        )
        output, report = self.run_merge(
            base, extra, return_provenance=True
        )
        self.assertNotIn(r"119\.29\.29\.\d+\/d", output)
        self.assertIn(r"119\.29\.29\.98\/health", output)
        exclusions = report.get("rewrite_exclusions", [])
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["source"], "block")
        self.assertEqual(exclusions[0]["status"], "excluded_safety_guard")
        self.assertEqual(exclusions[0]["action"], "reject(200)")
        self.assertIn("119.29.29.98", exclusions[0]["reason"])
        self.assertIn("119.29.29.99", exclusions[0]["reason"])

    def test_unused_zhangle_app_httpdns_mitm_wildcard_is_removed(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n"
            r"request if " + "${url}" + r" ~= /^https?:\\/\\/119\\.29\\.29\\.\\d+\\/d/ then reject(200)" + "\n"
            "[MITM]\nhostname = 119.29.29.*\n"
        )
        output, report = self.run_merge(base, extra, return_provenance=True)
        mitm_line = next(line for line in output.splitlines() if line.strip().startswith("hostname ="))
        self.assertNotIn("119.29.29.*", mitm_line)
        exclusions = report.get("mitm_exclusions", [])
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["hostname"], "119.29.29.*")
        self.assertEqual(exclusions[0]["status"], "excluded_unused_app")

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


    def test_555_rewrite_and_script_host_scope_is_narrowed(self):
        broad = r'[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+){1,3}(:\d+)?'
        extra = (
            "[Rewrite]\n"
            "# > 555影视\n"
            "# hostname = vip7.fzwdyy.cn, *.qyfxgd.cn, *.weilai555.com, *.ecoliving168.com\n"
            r"request if ${url} ~= /^https?:\/\/vip7\.fzwdyy\.cn:8083\/api\/(getAdvertInfo|getGOOGAdvert)/ then reject(200)" + "\n"
            r"request if ${url} ~= /^https?:\/\//" + broad + r"\/api\/v\d\/advert/ then reject(404)" + "\n"
            "[Script]\n"
            r'response if ${url} ~= /^https?:\/\//' + broad + r'\/api\/v\d\/movie\/index_recommend/i then script("https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/555Ad.js") with enable=555_enable, tag="555影视广告", timeout=60, requires_body=true' + "\n"
            "[MITM]\n"
            "hostname = vip7.fzwdyy.cn, *.qyfxgd.cn, *.weilai555.com, *.ecoliving168.com\n"
        )
        output, report = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            return_provenance=True,
        )
        rewrite = output.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        script = output.split("[Script]", 1)[1].split("[MITM]", 1)[0]
        vip_rule = next(line for line in rewrite.splitlines()
                        if "getAdvertInfo" in line)
        advert_rule = next(line for line in rewrite.splitlines()
                           if "/api\\/v\\d\\/advert" in line)
        script_rule = next(line for line in script.splitlines()
                           if "555Ad.js" in line)
        self.assertIn("vip7\\.fzwdyy\\.cn:8083", vip_rule)
        self.assertNotIn(broad, advert_rule)
        self.assertNotIn(broad, script_rule)
        self.assertIn("555_enable", script_rule)
        self.assertIn("555Ad.js", script_rule)
        self.assertIn("vip7\\.fzwdyy\\.cn", advert_rule)
        self.assertIn("qyfxgd\\.cn", advert_rule)
        self.assertIn("weilai555\\.com", script_rule)
        self.assertIn("ecoliving168\\.com", script_rule)

        host_pattern = (
            r'(?:vip7\.fzwdyy\.cn|(?:[A-Za-z0-9-]+\.)+qyfxgd\.cn|'
            r'(?:[A-Za-z0-9-]+\.)+weilai555\.com|'
            r'(?:[A-Za-z0-9-]+\.)+ecoliving168\.com)(?::\d+)?'
        )
        host_re = __import__("re").compile(r"^(?:" + host_pattern + r")$", __import__("re").I)
        for host in (
            "vip7.fzwdyy.cn", "api.qyfxgd.cn", "a.b.weilai555.com",
            "app.ecoliving168.com:8080",
        ):
            self.assertRegex(host, host_re)
        for host in ("other.example.com", "api.qyfxgd.cn.evil.test",
                     "qyfxgd.cn", "weilai555.com"):
            self.assertNotRegex(host, host_re)

        self.assertEqual(len(report["scope_adjustments"]), 2)
        self.assertEqual(
            {x["section"] for x in report["scope_adjustments"]},
            {"Rewrite", "Script"},
        )


    def test_lanrentingshu_broad_rewrite_is_limited_to_declared_hosts(self):
        extra = (
            "[Rewrite]\n"
            "# > 懒人听书\n"
            "# hostname = 118.178.214.118, dapis.mting.info, display.wting.info\n"
            r"request if ${url} ~= /^https?:\/\/118\.178\.214\.118\/yyting\/advertclient\/ClientAdvertList\.action/ then reject_img(200)" + "\n"
            r"request if ${url} ~= /^https?:\/\/dapis\.mting\.info\/yyting\/advertclient\/ClientAdvertList\.action/ then reject_img(200)" + "\n"
            r"request if ${url} ~= /^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action/ then reject(404)" + "\n"
            r"request if ${url} ~= /^https?:\/\/display\.wting\.info\/.*.jpeg/ then reject(200)" + "\n"
            "[Script]\n[MITM]\nhostname = 118.178.214.118, dapis.mting.info, display.wting.info\n"
        )
        output, report = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            return_provenance=True,
        )
        rewrite = output.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        broad = next(line for line in rewrite.splitlines()
                     if "ClientAdvertList" in line and "reject(404)" in line)
        self.assertIn(r"(?:118\.178\.214\.118|dapis\.mting\.info)", broad)
        self.assertNotIn(r"https?:\/\/.*\/yyting", broad)
        self.assertIn("reject(404)", broad)

        # 两条原有精确图片广告拦截与 display.wting.info 图片规则均保持原样。
        self.assertEqual(rewrite.count("reject_img(200)"), 2)
        self.assertIn("display\\.wting\\.info", rewrite)
        self.assertEqual(len(report["scope_adjustments"]), 1)
        adjustment = report["scope_adjustments"][0]
        self.assertEqual(adjustment["section"], "Rewrite")
        self.assertIn("118\\.178\\.214\\.118|dapis\\.mting\\.info",
                      adjustment["output_line"])

        host_re = __import__("re").compile(
            r"^(?:118\.178\.214\.118|dapis\.mting\.info)$",
            __import__("re").I,
        )
        for host in ("118.178.214.118", "dapis.mting.info"):
            self.assertRegex(host, host_re)
        for host in ("other.example.com", "display.wting.info",
                     "dapis.mting.info.evil.test"):
            self.assertNotRegex(host, host_re)

    def test_lanrentingshu_legacy_rstore_matcher_is_also_limited(self):
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action reject" + "\n"
            "[Script]\n[MITM]\nhostname = \n"
        )
        extra = (
            "[Rewrite]\n"
            "# > 懒人听书\n"
            "# hostname = 118.178.214.118, dapis.mting.info, display.wting.info\n"
            r"request if ${url} ~= /^https?:\/\/118\.178\.214\.118\/yyting\/advertclient\/ClientAdvertList\.action/ then reject_img(200)" + "\n"
            r"request if ${url} ~= /^https?:\/\/dapis\.mting\.info\/yyting\/advertclient\/ClientAdvertList\.action/ then reject_img(200)" + "\n"
            r"request if ${url} ~= /^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action/ then reject(404)" + "\n"
            "[Script]\n[MITM]\nhostname = 118.178.214.118, dapis.mting.info, display.wting.info\n"
        )
        output, report = self.run_merge(
            base, extra, return_provenance=True,
        )
        rewrite = output.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        legacy = next(line for line in rewrite.splitlines()
                      if "ClientAdvertList" in line and line.endswith(" reject"))
        self.assertIn(r"(?:118\.178\.214\.118|dapis\.mting\.info)", legacy)
        self.assertNotIn(r"https?:\/\/.*\/yyting", legacy)
        self.assertTrue(legacy.endswith(" reject"))

        # 原有两条精确图片广告规则保持不变；base 的 reject 动作也保持不变。
        self.assertEqual(rewrite.count("reject_img(200)"), 2)
        self.assertIn("display\.wting\.info", rewrite)

        legacy_record = next(
            item for item in report["rewrite"]
            if "ClientAdvertList" in item["output_line"]
            and item["output_line"].endswith(" reject")
        )
        self.assertEqual(legacy_record["sources"][0]["source"], "base")
        adjustment = next(
            item for item in report["scope_adjustments"]
            if item["source"] == "base" and "ClientAdvertList" in item["output_line"]
        )
        self.assertIn("118\.178\.214\.118|dapis\.mting\.info",
                      adjustment["output_line"])

        import re
        host_re = re.compile(r"^(?:118\.178\.214\.118|dapis\.mting\.info)$", re.I)
        for host in ("118.178.214.118", "dapis.mting.info"):
            self.assertRegex(host, host_re)
        for host in ("other.example.com", "display.wting.info",
                     "dapis.mting.info.evil.test"):
            self.assertNotRegex(host, host_re)


    def test_qqmusic_fallback_cdn_matcher_is_limited_to_declared_mitm_hosts(self):
        extra = (
            "[Rewrite]\n"
            "# > QQ音乐\n"
            "# hostname = us.l.qq.com, y.gtimg.cn, music.y.qq.com\n"
            r"request if ${url} ~= /^https?:\/\/y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\// then reject(404)" + "\n"
            r"request if ${url} ~= /^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\// then reject(404)" + "\n"
            r"request if ${url} ~= /^https?:\/\/((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\/music\/common\/upload\/t_splash_info\// then reject(404)" + "\n"
            "[MITM]\nhostname = y.gtimg.cn, music.y.qq.com\n"
        )
        thelong = (
            "#!name=QQ音乐\n[Rewrite]\n"
            "# 开屏广告图\n"
            r"^https?:\/\/y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            "# 同上，覆盖其他 CDN / IP 直连返回同一路径的情况（该主机需在 MITM 列表内才会生效，故本行实际对上面两个域名同样命中）\n"
            r"^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            "[MITM]\nhostname = y.gtimg.cn, music.y.qq.com\n"
        )
        output, report = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            return_provenance=True,
            apps_files={"qqmusic_splash_ad_block.plugin": thelong},
        )
        rewrite = output.split("[Rewrite]", 1)[1].split("[Script]", 1)[0]
        scoped = [line for line in rewrite.splitlines()
                  if "t_splash_info" in line and "(?:y" in line]
        self.assertEqual(len(scoped), 1)
        self.assertIn("t_splash_info", scoped[0])
        self.assertIn("reject", scoped[0])
        # blockAdsV2 的独立 IPv4 规则不受本次域名收敛影响。
        self.assertIn("25[0-5]", rewrite)
        self.assertIn("reject(404)", rewrite)
        self.assertNotIn(r"https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/", "\n".join(scoped))
        scoped_records = [x for x in report["rewrite"]
                          if "t_splash_info" in x["output_line"]
                          and "(?:y" in x["output_line"]]
        self.assertEqual(len(scoped_records), 1)
        mapped_sources = {
            source["source"]
            for record in scoped_records
            for source in record["sources"]
        }
        self.assertEqual(mapped_sources, {"block", "thelong"})
        adjustments = [x for x in report["scope_adjustments"]
                       if "t_splash_info" in x["output_line"]]
        self.assertEqual({x["source"] for x in adjustments},
                         {"block", "thelong"})
        self.assertEqual(len(adjustments), 2)

        import re
        host_re = re.compile(r"^(?:y\.gtimg\.cn|music\.y\.qq\.com)$", re.I)
        for host in ("y.gtimg.cn", "music.y.qq.com"):
            self.assertRegex(host, host_re)
        for host in ("other.example.com", "cdn.evil.test", "us.l.qq.com",
                     "y.gtimg.cn.evil.test"):
            self.assertNotRegex(host, host_re)


    def test_qqmusic_block_host_declaration_drift_fails_closed(self):
        extra = (
            "[Rewrite]\n# > QQ音乐\n"
            "# hostname = us.l.qq.com, y.gtimg.cn, changed.example.com\n"
            r"^https?:\/\/y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            r"^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            "[MITM]\nhostname = \n"
        )
        result = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            expect_failure=True,
        )
        self.assertIn("QQ音乐 blockAdsV2 hostname/matcher/action 已变化", result)


    def test_qqmusic_thelong_mitm_declaration_drift_fails_closed(self):
        extra = (
            "[Rewrite]\n# > QQ音乐\n"
            "# hostname = us.l.qq.com, y.gtimg.cn, music.y.qq.com\n"
            r"request if ${url} ~= /^https?:\/\/y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\// then reject(404)" + "\n"
            r"request if ${url} ~= /^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\// then reject(404)" + "\n"
            "[MITM]\nhostname = \n"
        )
        thelong = (
            "#!name=QQ音乐\n[Rewrite]\n"
            r"^https?:\/\/y\.gtimg\.cn\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            "# 同上，覆盖其他 CDN / IP 直连返回同一路径的情况（该主机需在 MITM 列表内才会生效）\n"
            r"^https?:\/\/.+?\/music\/common\/upload\/t_splash_info\/ reject" + "\n"
            "[MITM]\nhostname = y.gtimg.cn, changed.example.com\n"
        )
        result = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            apps_files={"qqmusic_splash_ad_block.plugin": thelong},
            expect_failure=True,
        )
        self.assertIn("Thelong QQ音乐 MITM/备用 CDN 规则声明已变化", result)


    def test_lanrentingshu_host_declaration_drift_fails_closed(self):
        extra = (
            "[Rewrite]\n"
            "# > 懒人听书\n"
            "# hostname = 118.178.214.118, dapis.mting.info, new.example.com\n"
            r"request if ${url} ~= /^https?:\/\/.*\/yyting\/advertclient\/ClientAdvertList.action/ then reject(404)" + "\n"
            "[Script]\n[MITM]\nhostname = \n"
        )
        result = self.run_merge(
            "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            extra,
            expect_failure=True,
        )
        self.assertIn("懒人听书上游 hostname 声明已变化", result)


    def test_rule_provenance_records_winner_duplicates_and_rule_events(self):
        base = (
            "[Rewrite]\n"
            "^https://same.example.com/ad reject\n"
            "[Script]\n"
            'http-response ^https://script.example.com/config script-path=https://cdn.example/script.js\n'
            "[MITM]\nhostname = same.example.com,script.example.com\n"
        )
        extra = (
            "[Rewrite]\n"
            "^https://same.example.com/ad reject\n"
            "[Script]\n"
            'http-response ^https://script.example.com/config script-path=https://cdn.example/script.js\n'
            "[Rule]\nDOMAIN,ads.example.com,REJECT\n"
        )
        myblockads = "[Rule]\nDOMAIN,ads.example.com,REJECT\n"
        output, report = self.run_merge(
            base, extra, myblockads_text=myblockads, return_provenance=True
        )

        rewrite = next(item for item in report["rewrite"]
                       if "same.example.com/ad" in item["output_line"])
        self.assertEqual(len(rewrite["sources"]), 2)
        self.assertEqual(rewrite["sources"][0]["source"], "base")
        self.assertEqual(rewrite["sources"][0]["disposition"], "selected")
        self.assertEqual(rewrite["sources"][1]["source"], "block")
        self.assertEqual(
            rewrite["sources"][1]["disposition"], "duplicate_same_semantics"
        )

        script = next(item for item in report["script"]
                      if "script.example.com/config" in item["output_line"])
        self.assertEqual(len(script["sources"]), 2)
        self.assertEqual(script["sources"][0]["source"], "base")
        self.assertEqual(script["sources"][0]["disposition"], "selected")
        self.assertEqual(script["sources"][1]["source"], "block")

        included = [event for event in report["rule_events"]
                    if event["normalized_line"] == "DOMAIN,ads.example.com,REJECT"]
        self.assertEqual(len(included), 2)
        self.assertEqual(included[0]["status"], "included")
        self.assertEqual(included[1]["status"], "duplicate_exact")
        self.assertEqual(included[1]["duplicate_of_source"], "block")
        self.assertEqual(report["summary"]["rule_output_entries"], 1)
        self.assertIn("source_entry_index", included[0])
        self.assertTrue(report["limitations"])



    def test_multi_file_sources_include_exact_filename_and_original_line(self):
        base = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        apps = {
            "sample_ad_block.plugin": (
                "# sample source\n[Rule]\nDOMAIN,ads.example.com,REJECT\n"
                "[Rewrite]\n^https://ads.example.com/ad reject\n"
                "[Script]\nhttp-response ^https://ads.example.com/config script-path=https://cdn.example/a.js\n"
            )
        }
        _, report = self.run_merge(base, extra, return_provenance=True, apps_files=apps)
        rewrite = next(x for x in report["rewrite"] if "ads.example.com/ad" in x["output_line"])
        source = next(x for x in rewrite["sources"] if x["source"] == "thelong")
        self.assertEqual(source["source_file"], "sample_ad_block.plugin")
        self.assertEqual(source["source_line_number"], 5)
        self.assertEqual(source["source_raw_line"], "^https://ads.example.com/ad reject")
        rule = next(x for x in report["rule_events"] if x["source"] == "thelong")
        self.assertEqual(rule["source_file"], "sample_ad_block.plugin")
        self.assertEqual(rule["source_line_number"], 3)

    def test_rule_provenance_identifies_semantic_coverage_source(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\nDOMAIN-SUFFIX,example.com,REJECT\n"
        myblockads = "[Rule]\nDOMAIN,ads.example.com,REJECT\n"
        _, report = self.run_merge(
            base, extra, myblockads_text=myblockads, return_provenance=True
        )
        event = next(item for item in report["rule_events"]
                     if item["normalized_line"] == "DOMAIN,ads.example.com,REJECT")
        self.assertEqual(event["status"], "covered_by_existing_rule")
        self.assertEqual(event["covered_by"], "DOMAIN-SUFFIX,example.com,REJECT")
        self.assertEqual(event["covered_by_source"], "block")


if __name__ == "__main__":
    unittest.main()
