#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for merge_plugins.py; all inputs are local fixtures."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MERGER = Path(__file__).with_name("merge_plugins.py")


class MergeIntegrationTests(unittest.TestCase):
    def run_merge(self, base_text, extra_text, myblockads_text=None, return_stdout=False, amap_text=None, return_provenance=False, apps_files=None, aoomee_files=None, expect_failure=False, filter_text=None):
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
        if filter_text is not None:
            filter_file = root / "filter.list"
            filter_file.write_text(filter_text, encoding="utf-8")
            command[command.index("--filter") + 1] = str(filter_file)
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
        if aoomee_files is not None:
            aoomee = root / "aoomee"
            plugins = aoomee / "plugins"
            plugins.mkdir(parents=True)
            for filename, content in aoomee_files.items():
                (plugins / filename).write_text(content, encoding="utf-8")
            command += ["--aoomee", str(aoomee)]
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


    def test_rule_whitespace_only_duplicates_are_removed_without_changing_quoted_literals(self):
        retained = 'AND, ((USER-AGENT, "com.example App"), (DOMAIN-SUFFIX, example.com)), REJECT'
        duplicate = 'AND,((USER-AGENT,"com.example App"),(DOMAIN-SUFFIX,example.com)),REJECT'
        distinct_literal = 'AND,((USER-AGENT,"com.example  App"),(DOMAIN-SUFFIX,example.com)),REJECT'
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n" + retained + "\n[Rewrite]\n[MITM]\nhostname = \n"
        myblockads = (
            "[Rule]\n" + duplicate + "\n" + distinct_literal
            + "\n[Rewrite]\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(
            base, extra, myblockads_text=myblockads, return_provenance=True
        )
        rule_lines = [line for line in output.splitlines() if line.startswith("AND,")]
        self.assertEqual(len(rule_lines), 2)
        self.assertIn(retained, output)
        self.assertIn(distinct_literal, output)
        self.assertNotIn(duplicate, output)
        duplicate_events = [
            item for item in provenance["rule_events"]
            if item.get("original_input_line") == duplicate
        ]
        self.assertEqual(len(duplicate_events), 1)
        self.assertEqual(duplicate_events[0]["source"], "myblockads")
        self.assertEqual(duplicate_events[0]["status"], "duplicate_exact")
        self.assertEqual(duplicate_events[0]["duplicate_reason"],
                         "whitespace_only_outside_quoted_literals")
        self.assertEqual(
            next(item for item in provenance["rule_events"]
                 if item.get("status") == "duplicate_exact"
                 and item.get("original_input_line") == retained)["duplicate_reason"],
            "exact_text_duplicate",
        )
        self.assertEqual(duplicate_events[0]["duplicate_of"], retained)

    def test_unscoped_udp_443_reject_is_excluded_but_scoped_quic_reject_is_kept(self):
        global_reject = "AND,((PROTOCOL,UDP),(DEST-PORT,443)),REJECT"
        scoped_reject = "AND,((DOMAIN-SUFFIX,example.com),(PROTOCOL,UDP),(DEST-PORT,443)),REJECT"
        global_direct = "AND,((PROTOCOL,UDP),(DEST-PORT,443)),DIRECT"
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rule]\n"
            + global_reject + "\n"
            + scoped_reject + "\n"
            + global_direct + "\n"
            + "[Rewrite]\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        self.assertNotIn(global_reject, output)
        self.assertIn(scoped_reject, output)
        self.assertIn(global_direct, output)
        exclusions = [
            item for item in provenance["rule_events"]
            if item.get("original_input_line") == global_reject
        ]
        self.assertEqual(len(exclusions), 1)
        self.assertEqual(exclusions[0]["status"], "excluded_safety_guard")
        self.assertIn("DIRECT connectivity", exclusions[0]["reason"])


    def test_grcbank_splash_image_extension_dot_is_literal(self):
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/mbank\.grcbank\.com\/ydyh\/resources\/startpage\/.*.(?:jpg|png) reject-200"
            + "\n[MITM]\nhostname = \n"
        )
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "mbank" in line)
        matcher = re.compile(line.split()[0])
        for url in (
            "https://mbank.grcbank.com/ydyh/resources/startpage/banner.jpg",
            "http://mbank.grcbank.com/ydyh/resources/startpage/banner.png",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://mbank.grcbank.com/ydyh/resources/startpage/bannerxjpg",
            "https://mbank.grcbank.com/ydyh/resources/startpage/banner.webp",
            "https://mbankXgrcbank.com/ydyh/resources/startpage/banner.jpg",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "广发银行移动端开屏图片"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "base")
        self.assertEqual(changes[0]["original_line"], base.split("[Rewrite]\n", 1)[1].split("\n", 1)[0])
        self.assertEqual(changes[0]["output_line"], line)

    def test_grcbank_splash_image_guard_fails_closed_on_action_drift(self):
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/mbank\.grcbank\.com\/ydyh\/resources\/startpage\/.*.(?:jpg|png) reject"
            + "\n[MITM]\nhostname = \n"
        )
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output = self.run_merge(base, extra, expect_failure=True)
        self.assertIn("广发银行移动端开屏图片 图片规则动作已变化", output)


    def test_omofun_top_notice_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https?:\/\/103\.91\.210\.141\:2515\/xgapp\.php\/v2\/top_notice/ then reject(404)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n# > omofun\n# hostname = 103.91.210.141\n" + source_line + "\n[MITM]\nhostname = \n"
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "xgapp" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://103.91.210.141:2515/xgapp.php/v2/top_notice",
            "https://103.91.210.141:2515/xgapp.php/v2/top_notice?channel=home",
            "http://103.91.210.141:2515/xgapp.php/v2/top_notice/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://103.91.210.141:2515/xgapp.php/v2/top_notice_extra",
            "https://103.91.210.141:2515/xgapp.php/v2/top_notice2",
            "https://103.91.210.141:2515/xgappXphp/v2/top_notice",
            "https://103.91.210.142:2515/xgapp.php/v2/top_notice",
            "https://103.91.210.141:2516/xgapp.php/v2/top_notice",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "Omofun top_notice 接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_omofun_top_notice_guard_fails_closed_on_action_or_path_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/103\.91\.210\.141\:2515\/xgapp\.php\/v2\/top_notice/ then reject(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_action, expect_failure=True)
        self.assertIn("Omofun top_notice 动作已变化", output)

        extra_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/103\.91\.210\.141\:2515\/xgapp\.php\/v2\/top_notice.*/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_path, expect_failure=True)
        self.assertIn("Omofun top_notice matcher 已变化", output)


    def test_csdn_base_legacy_open_screen_ad_requires_endpoint_path_boundary(self):
        source_line = (
            r"^https?:\/\/app-gw\.csdn\.net\/silkroad-api\/api\/v\d\/assemble\/list\/pub\/channel\/app_open_screen_ad reject"
        )
        base = "[Rewrite]\n" + source_line + "\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        csdn_lines = [
            line for line in output.splitlines()
            if "app_open_screen_ad" in line
        ]
        self.assertEqual(len(csdn_lines), 1)
        line = csdn_lines[0]
        self.assertTrue(line.endswith(" reject"))
        matcher = re.compile(line.split()[0])
        for url in (
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad",
            "https://app-gw.csdn.net/silkroad-api/api/v2/assemble/list/pub/channel/app_open_screen_ad?from=home",
            "https://app-gw.csdn.net/silkroad-api/api/v3/assemble/list/pub/channel/app_open_screen_ad/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad_extra",
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad2",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "CSDN app_open_screen_ad 接口路径边界"
            and item.get("source") == "base"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_csdn_open_screen_ad_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https?:\/\/app-gw\.csdn\.net\/silkroad-api\/api\/v\d\/assemble\/list\/pub\/channel\/app_open_screen_ad/ then reject(404)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n# > CSDN\n# hostname = app-gw.csdn.net, gw.csdn.net\n"
            + source_line + "\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "app_open_screen_ad" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad",
            "http://app-gw.csdn.net/silkroad-api/api/v2/assemble/list/pub/channel/app_open_screen_ad?from=home",
            "https://app-gw.csdn.net/silkroad-api/api/v3/assemble/list/pub/channel/app_open_screen_ad/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad_extra",
            "https://app-gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad2",
            "https://app-gwXcsdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad",
            "https://gw.csdn.net/silkroad-api/api/v1/assemble/list/pub/channel/app_open_screen_ad",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "CSDN app_open_screen_ad 接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_csdn_open_screen_ad_guard_fails_closed_on_action_or_path_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/app-gw\.csdn\.net\/silkroad-api\/api\/v\d\/assemble\/list\/pub\/channel\/app_open_screen_ad/ then reject(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_action, expect_failure=True)
        self.assertIn("CSDN app_open_screen_ad 动作已变化", output)

        extra_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/app-gw\.csdn\.net\/silkroad-api\/api\/v\d\/assemble\/list\/pub\/channel\/app_open_screen_ad.*/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_path, expect_failure=True)
        self.assertIn("CSDN app_open_screen_ad matcher 已变化", output)


    def test_clicli_top_notice_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https?:\/\/js-ad\.ayximgs\.com\.ad-universe-cdn\.hzhcbkj\.cn\/xgapp\.php\/v2\/top_notice/ then reject(404)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n# > clicli\n# hostname = js-ad.ayximgs.com\n"
            + source_line + "\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "ayximgs" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice",
            "https://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice?channel=home",
            "http://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice_extra",
            "https://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice2",
            "https://js-adXayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgapp.php/v2/top_notice",
            "https://js-ad.ayximgs.com.ad-universe-cdn.hzhcbkj.cn/xgappXphp/v2/top_notice",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "clicli top_notice 接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_clicli_top_notice_guard_fails_closed_on_action_or_path_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/js-ad\.ayximgs\.com\.ad-universe-cdn\.hzhcbkj\.cn\/xgapp\.php\/v2\/top_notice/ then reject(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_action, expect_failure=True)
        self.assertIn("clicli top_notice 动作已变化", output)

        extra_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/js-ad\.ayximgs\.com\.ad-universe-cdn\.hzhcbkj\.cn\/xgapp\.php\/v2\/top_notice.*/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_path, expect_failure=True)
        self.assertIn("clicli top_notice matcher 已变化", output)


    def test_ticketstar_app_start_page_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https:\/\/appapi\.caiyicloud\.com\/cyy_gatewayapi\/home\/pub\/v3\/banners\/app_start_page/ then reject_dict(200)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n# > 票星球\n# hostname = appapi.caiyicloud.com\n"
            + source_line + "\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "appapi\\.caiyicloud" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://appapi.caiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page",
            "https://appapi.caiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page?channel=home",
            "https://appapi.caiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page/extra",
        ):
            self.assertRegex(url, matcher)
        for url in (
            "https://appapi.caiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page_extra",
            "https://appapi.caiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page2",
            "https://appapiXcaiyicloud.com/cyy_gatewayapi/home/pub/v3/banners/app_start_page",
        ):
            self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "票星球 app_start_page 开屏接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["output_line"], line)

    def test_ticketstar_app_start_guard_fails_closed_on_action_or_matcher_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        bad_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https:\/\/appapi\.caiyicloud\.com\/cyy_gatewayapi\/home\/pub\/v3\/banners\/app_start_page/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, bad_action, expect_failure=True)
        self.assertIn("票星球 app_start_page 动作已变化", output)
        bad_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https:\/\/appapi\.caiyicloud\.com\/cyy_gatewayapi\/home\/pub\/v3\/banners\/app_start_page.*/ then reject_dict(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, bad_path, expect_failure=True)
        self.assertIn("票星球 app_start_page matcher 已变化", output)


    def test_dasixiong_version_endpoints_require_path_boundary_for_base_and_block(self):
        lines = (
            r'request if ${url} ~= /^https?:\/\/sdk\.alibaba\.com\.ailbaba\.me\/xgapp\.php\/v\d\/version/ then reject(200)',
            r'request if ${url} ~= /^https?:\/\/sdk\.alibaba\.com\.ailbaba\.me\/(dsx|xgapp)\.php\/v\d\/(top_notice\?|version|advert\?position=[^2]+)/ then reject(200)',
        )
        base = '[Rewrite]\n' + '\n'.join(lines) + '\n[MITM]\nhostname = \n'
        extra = '[Rewrite]\n# > 大师兄\n# hostname = sdk.alibaba.com.ailbaba.me, adservice.sigmob.cn\n' + '\n'.join(lines) + '\n[MITM]\nhostname = \n'
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        matched = [line for line in output.splitlines() if 'sdk\\.alibaba' in line and 'version' in line]
        self.assertEqual(len(matched), 2)
        patterns = [re.compile(line.split(' ~= ', 1)[1].split(' then ', 1)[0].strip().strip('/')) for line in matched]
        for url in (
            'https://sdk.alibaba.com.ailbaba.me/xgapp.php/v1/version',
            'https://sdk.alibaba.com.ailbaba.me/xgapp.php/v2/version?platform=ios',
            'http://sdk.alibaba.com.ailbaba.me/dsx.php/v3/version/extra',
            'https://sdk.alibaba.com.ailbaba.me/xgapp.php/v1/version/',
        ):
            self.assertTrue(any(pattern.search(url) for pattern in patterns), url)
        for url in (
            'https://sdk.alibaba.com.ailbaba.me/xgapp.php/v1/versionExtra',
            'https://sdk.alibaba.com.ailbaba.me/xgapp.php/v1/version2',
            'https://sdk.alibaba.com.ailbaba.me/dsx.php/v1/versionExtra',
            'https://sdkXalibaba.com.ailbaba.me/xgapp.php/v1/version',
        ):
            self.assertFalse(any(pattern.search(url) for pattern in patterns), url)
        changes = [item for item in provenance['scope_adjustments'] if item.get('target') == '大师兄 version 接口路径边界']
        self.assertEqual(len(changes), 4)
        self.assertEqual({item['source'] for item in changes}, {'base', 'blockAdsV2'})

    def test_dasixiong_version_guard_fails_closed_on_action_or_matcher_drift(self):
        base = '[Rewrite]\n[MITM]\nhostname = \n'
        bad_action = '[Rewrite]\n' + r'request if ${url} ~= /^https?:\/\/sdk\.alibaba\.com\.ailbaba\.me\/xgapp\.php\/v\d\/version/ then reject(404)' + '\n[MITM]\nhostname = \n'
        output = self.run_merge(base, bad_action, expect_failure=True)
        self.assertIn('大师兄 version 动作已变化', output)
        bad_path = '[Rewrite]\n' + r'request if ${url} ~= /^https?:\/\/sdk\.alibaba\.com\.ailbaba\.me\/xgapp\.php\/v\d\/version.*/ then reject(200)' + '\n[MITM]\nhostname = \n'
        output = self.run_merge(base, bad_path, expect_failure=True)
        self.assertIn('大师兄 version matcher 已变化', output)

    def test_pzoap_top_notice_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https?:\/\/pzoap\.moedot\.net\/xgapp\.php\/v2\/top_notice/ then reject(404)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n# > 稀饭动漫\n# hostname = pzoap.moedot.net\n"
            + source_line + "\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "pzoap" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://pzoap.moedot.net/xgapp.php/v2/top_notice",
            "https://pzoap.moedot.net/xgapp.php/v2/top_notice?channel=home",
            "http://pzoap.moedot.net/xgapp.php/v2/top_notice/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://pzoap.moedot.net/xgapp.php/v2/top_notice_extra",
            "https://pzoap.moedot.net/xgapp.php/v2/top_notice2",
            "https://pzoapXmoedot.net/xgapp.php/v2/top_notice",
            "https://pzoap.moedot.net/xgappXphp/v2/top_notice",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "稀饭动漫 top_notice 接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_pzoap_top_notice_guard_fails_closed_on_action_or_path_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/pzoap\.moedot\.net\/xgapp\.php\/v2\/top_notice/ then reject(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_action, expect_failure=True)
        self.assertIn("稀饭动漫 top_notice 动作已变化", output)

        extra_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/pzoap\.moedot\.net\/xgapp\.php\/v2\/top_notice.*/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_path, expect_failure=True)
        self.assertIn("稀饭动漫 top_notice matcher 已变化", output)


    def test_tencentvideo_ad_segment_ip_prefix_is_valid_ipv4_only(self):
        plugin = (
            "[Rewrite]\n"
            + r"^http:\/\/[\d\.:]*\/?(defaultts\.tc|vmind\.qqvideo\.tc|finderpdd\.video)\.qq\.com\/\w+ reject"
            + "\n[MITM]\nhostname = \n"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output, provenance = self.run_merge(
            base, extra, apps_files={"tencentvideo_splash_ad_block.plugin": plugin},
            return_provenance=True,
        )
        line = next(line for line in output.splitlines() if "defaultts" in line)
        matcher = re.compile(line.split()[0])
        valid_urls = (
            "http://1.2.3.4:80/defaultts.tc.qq.com/segment001",
            "http://255.255.255.255:65535/vmind.qqvideo.tc.qq.com/segment002",
            "http://10.0.0.1/finderpdd.video.qq.com/segment003",
            "http://defaultts.tc.qq.com/segment004",
        )
        invalid_urls = (
            "http://999.1.2.3:80/defaultts.tc.qq.com/segment001",
            "http://1.2.3:80/defaultts.tc.qq.com/segment001",
            "http://1.2.3.4.5:80/defaultts.tc.qq.com/segment001",
            "http://1..2.3:80/defaultts.tc.qq.com/segment001",
        )
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("source_file") == "tencentvideo_splash_ad_block.plugin"
            and "Tencent Video plugin documents this HTTP ad-segment form" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "thelong")
        self.assertEqual(changes[0]["source_line_number"], 93)
        self.assertEqual(changes[0]["source_entry_index"], 149)
        self.assertEqual(changes[0]["original_line"], plugin.split("[Rewrite]\n", 1)[1].split("\n", 1)[0])
        self.assertEqual(changes[0]["output_line"], line)

    def test_tencentvideo_segment_ip_guard_fails_closed_on_action_drift(self):
        plugin = (
            "[Rewrite]\n"
            + r"^http:\/\/[\d\.:]*\/?(defaultts\.tc|vmind\.qqvideo\.tc|finderpdd\.video)\.qq\.com\/\w+ reject-dict"
            + "\n[MITM]\nhostname = \n"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output = self.run_merge(
            base, extra, apps_files={"tencentvideo_splash_ad_block.plugin": plugin},
            expect_failure=True,
        )
        self.assertIn("腾讯视频广告分片 IP matcher 范围或动作已变化", output)


    def test_odin_numeric_hosts_are_restricted_to_valid_ipv4_and_keep_ad_paths(self):
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/[\d\.]+\/odin\/c\d\/(channel\/ads|skin\/config)\? reject-dict"
            + "\n[Script]\n[MITM]\nhostname = \n"
        )
        extra = (
            "[Rewrite]\n"
            + 'request if @@URL@@ ~= /^https?:\/\/[\d\.]+\/odin\/c1\/(channel\/ads|skin\/config)\?/ then reject_dict(200)'
            + "\n[Script]\n[MITM]\nhostname = \n"
        ).replace("@@URL@@", chr(36) + "{url}")
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        lines = [line for line in output.splitlines() if "odin" in line]
        self.assertEqual(len(lines), 2)
        for line in lines:
            if line.startswith("request if"):
                pattern = re.search(r"~= /(.*)/ then ", line).group(1)
            else:
                pattern = line.split()[0]
            compiled = re.compile(pattern)
            path = "/odin/c1/channel/ads?x=1" if "request if" in line else "/odin/c9/skin/config?x=1"
            for host in ("1.2.3.4", "0.0.0.0", "255.255.255.255"):
                self.assertIsNotNone(compiled.search("https://" + host + path), line)
            for host in ("999.1.2.3", "1.2.3", "1.2.3.4.5", "1..2.3"):
                self.assertIsNone(compiled.search("https://" + host + path), line)
        changes = [
            item for item in provenance["scope_adjustments"]
            if "Odin ad/config endpoint matcher" in item.get("reason", "")
        ]
        self.assertEqual({item["source"] for item in changes}, {"base", "block"})
        self.assertEqual({item["source_entry_index"] for item in changes}, {621, 626})

    def test_odin_numeric_host_guard_fails_closed_on_scope_or_action_drift(self):
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/[\d\.]+\/odin\/c\d\/(channel\/ads|skin\/config)\? reject"
            + "\n[Script]\n[MITM]\nhostname = \n"
        )
        extra = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        output = self.run_merge(base, extra, expect_failure=True)
        self.assertIn("Odin numeric-host rule count/scope/action drift", output)


    def test_baidunetdisk_cdn_fallbacks_match_valid_mitm_subdomains_only(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT\n"
            "[Rewrite]\n"
            r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            "[MITM]\nhostname = pan.baidu.com, *.vlion.cn, *.advlion.com\n"
        )
        output, report = self.run_merge(
            base, extra,
            return_provenance=True,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
        )
        vlion = next(line for line in output.splitlines() if "vlion" in line and "reject-200" in line)
        advlion = next(line for line in output.splitlines() if "advlion" in line and "reject-200" in line)
        vlion_matcher = re.search(r"^(.*?)\s+reject-200$", vlion).group(1)
        advlion_matcher = re.search(r"^(.*?)\s+reject-200$", advlion).group(1)
        for url in (
            "https://img.vlion.cn/ads/banner.jpg",
            "https://a.b.vlion.cn/ads/banner.jpg",
        ):
            self.assertRegex(url, vlion_matcher)
        for url in (
            "https://vlion.cn/ads/banner.jpg",
            "https://a..vlion.cn/ads/banner.jpg",
            "https://-bad.vlion.cn/ads/banner.jpg",
            "https://img.vlion.cn.evil.test/ads/banner.jpg",
            "http://img.vlion.cn/ads/banner.jpg",
        ):
            self.assertNotRegex(url, vlion_matcher)
        for url in (
            "https://img.advlion.com/ads/banner.jpg",
            "https://a.b.advlion.com/ads/banner.jpg",
        ):
            self.assertRegex(url, advlion_matcher)
        for url in (
            "https://advlion.com/ads/banner.jpg",
            "https://a..advlion.com/ads/banner.jpg",
            "https://img.advlion.com.evil.test/ads/banner.jpg",
            "http://img.advlion.com/ads/banner.jpg",
        ):
            self.assertNotRegex(url, advlion_matcher)
        changes = [
            item for item in report["scope_adjustments"]
            if "Constrain the Baidu Netdisk CDN image fallback" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 2)
        self.assertEqual({item["source_file"] for item in changes}, {"baidunetdisk_splash_ad_block.plugin"})
        self.assertEqual(
            {item["original_line"] for item in changes},
            {
                r"^https://.*\.vlion\.cn/.+ reject-200",
                r"^https://.*\.advlion\.com/.+ reject-200",
            },
        )

    def test_baidunetdisk_advlion_com_mitm_host_gets_matching_quic_reject(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        cn_rule = "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT"
        com_rule = "AND,((DOMAIN-SUFFIX,advlion.com),(PROTOCOL,QUIC)),REJECT"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            + cn_rule + "\n"
            + "[Rewrite]\n"
            + r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            
            + r"^https://pan\.baidu\.com/buy/ad/conf reject-dict" + "\n"
            + r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            + r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            + "[MITM]\nhostname = pan.baidu.com, *.vlion.cn, *.advlion.com\n"
        )
        output, provenance = self.run_merge(
            base, extra,
            return_provenance=True,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
        )
        output_rules = [
            line for line in output.splitlines()
            if line.startswith("AND,((DOMAIN-SUFFIX,advlion.")
        ]
        self.assertIn(cn_rule, output_rules)
        self.assertIn(com_rule, output_rules)
        self.assertEqual(output_rules.count(com_rule), 1)

        adjustments = provenance["rule_scope_adjustments"]
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0]["source"], "thelong")
        self.assertEqual(adjustments[0]["source_file"], "baidunetdisk_splash_ad_block.plugin")
        self.assertEqual(adjustments[0]["section"], "Rule")
        self.assertEqual(adjustments[0]["related_existing_rule"], cn_rule)
        self.assertEqual(adjustments[0]["mitm_host"], "*.advlion.com")
        self.assertEqual(adjustments[0]["output_line"], com_rule)

        generated_event = next(
            event for event in provenance["rule_events"]
            if event.get("source") == "thelong"
            and event.get("original_input_line") == com_rule
        )
        self.assertEqual(generated_event["status"], "included")
        self.assertEqual(generated_event["source_file"], "baidunetdisk_splash_ad_block.plugin")
        self.assertEqual(generated_event["source_original_section"], "MITM-derived Rule")
        self.assertEqual(generated_event["generated_from_mitm_host"], "*.advlion.com")
        self.assertIsNotNone(generated_event["output_entry_index"])

    def test_baidunetdisk_advlion_com_quic_rule_is_not_duplicated_when_upstream_fixes_it(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        cn_rule = "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT"
        com_rule = "AND,((DOMAIN-SUFFIX,advlion.com),(PROTOCOL,QUIC)),REJECT"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n" + cn_rule + "\n" + com_rule + "\n"
            "[Rewrite]\n"
            + r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            
            + r"^https://pan\.baidu\.com/buy/ad/conf reject-dict" + "\n"
            + r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            + r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            + "[MITM]\nhostname = pan.baidu.com, *.advlion.com\n"
        )
        output, provenance = self.run_merge(
            base, extra, return_provenance=True,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
        )
        self.assertEqual(output.splitlines().count(com_rule), 1)
        self.assertEqual(provenance["rule_scope_adjustments"], [])

    def test_baidunetdisk_advlion_quic_guard_fails_closed_when_mitm_host_is_missing(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT\n"
            "[Rewrite]\n"
            + r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            
            + r"^https://pan\.baidu\.com/buy/ad/conf reject-dict" + "\n"
            + r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            + r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            "[MITM]\nhostname = pan.baidu.com, *.vlion.cn\n"
        )
        output = self.run_merge(
            base, extra,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
            expect_failure=True,
        )
        self.assertIn("百度网盘 advlion.com QUIC 补齐守卫缺少对应 MITM 声明", output)

    def test_baidunetdisk_advlion_quic_guard_fails_closed_on_action_drift(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),DIRECT\n"
            "[Rewrite]\n"
            + r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            
            + r"^https://pan\.baidu\.com/buy/ad/conf reject-dict" + "\n"
            + r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            + r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            "[MITM]\nhostname = pan.baidu.com, *.advlion.com\n"
        )
        output = self.run_merge(
            base, extra,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
            expect_failure=True,
        )
        self.assertIn("百度网盘 advlion.cn QUIC 规则范围或动作已变化", output)


    def test_baidunetdisk_cdn_subdomain_guard_fails_closed_on_action_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT\n"
            "[Rewrite]\n"
            r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            r"^https://.*\.vlion\.cn/.+ reject-dict" + "\n"
            r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            "[MITM]\nhostname = pan.baidu.com, *.vlion.cn, *.advlion.com\n"
        )
        output = self.run_merge(
            base, extra,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
            expect_failure=True,
        )
        self.assertIn("百度网盘 CDN 子域名规则范围或动作已变化", output)


    def test_baidunetdisk_ad_image_fallback_is_limited_to_declared_mitm_host(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT\n"
            "[Rewrite]\n"
            r"^https://.*\.baidu\.com.*ad/.* reject-200" + "\n"
            r"^https://.*\.vlion\.cn/.+ reject-200" + "\n"
            r"^https://.*\.advlion\.com/.+ reject-200" + "\n"
            "[MITM]\nhostname = pan.baidu.com, *.vlion.cn, *.advlion.com\n"
        )
        output, report = self.run_merge(
            base, extra,
            return_provenance=True,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
        )
        result = next(
            line for line in output.splitlines()
            if line.startswith(r"^https://pan\.baidu\.com") and "reject-200" in line
        )
        matcher = re.search(r"^(.*?)\s+reject-200$", result).group(1)
        for url in (
            "https://pan.baidu.com/ad/image.jpg",
            "https://pan.baidu.com/api/v1/ad/banner.png",
        ):
            self.assertRegex(url, matcher)
        for url in (
            "https://evil.baidu.com/ad/image.jpg",
            "https://pan.baidu.com.evil.test/ad/image.jpg",
            "https://panXbaidu.com/ad/image.jpg",
            "http://pan.baidu.com/ad/image.jpg",
        ):
            self.assertNotRegex(url, matcher)
        changes = [
            item for item in report["scope_adjustments"]
            if "Baidu Netdisk plugin declares only pan.baidu.com" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "thelong")
        self.assertEqual(changes[0]["source_file"], "baidunetdisk_splash_ad_block.plugin")
        self.assertEqual(changes[0]["original_line"], r"^https://.*\.baidu\.com.*ad/.* reject-200")
        self.assertEqual(changes[0]["output_line"], result)

    def test_baidunetdisk_ad_image_guard_fails_closed_on_action_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        plugin = (
            "#!name=百度网盘\n"
            "[Rule]\n"
            "AND,((DOMAIN-SUFFIX,advlion.cn),(PROTOCOL,QUIC)),REJECT\n"
            "[Rewrite]\n"
            r"^https://.*\.baidu\.com.*ad/.* reject-dict" + "\n"
            "[MITM]\nhostname = pan.baidu.com\n"
        )
        output = self.run_merge(
            base, extra,
            apps_files={"baidunetdisk_splash_ad_block.plugin": plugin},
            expect_failure=True,
        )
        self.assertIn("百度网盘广告图 CDN 规则数量、范围或动作已变化", output)


    def test_aoomee_provenance_keeps_alignment_across_double_slash_rows_and_files(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        aoomee_files = {
            "a.lpx": (
                "[Rewrite]\n"
                "^https://a.example/first reject-dict\n"
                "// upstream note retained by the section parser\n"
                "^https://a.example/second reject-dict\n"
            ),
            "b.lpx": (
                "[Rewrite]\n"
                "^https://b.example/third reject-dict\n"
            ),
        }
        _, provenance = self.run_merge(
            base, extra, aoomee_files=aoomee_files, return_provenance=True)

        by_output = {row["output_line"]: row for row in provenance["rewrite"]}
        expected = {
            "^https://a.example/first reject-dict": ("plugins/a.lpx", 2),
            "^https://a.example/second reject-dict": ("plugins/a.lpx", 4),
            "^https://b.example/third reject-dict": ("plugins/b.lpx", 2),
        }
        for output_line, (source_file, line_number) in expected.items():
            source = next(
                item for item in by_output[output_line]["sources"]
                if item["source"] == "aoomee")
            self.assertEqual(source["source_file"], source_file)
            self.assertEqual(source["source_line_number"], line_number)
            self.assertEqual(source["source_raw_line"], output_line)
            self.assertEqual(source["input_line"], output_line)
            self.assertEqual(source["source_original_section"], "Rewrite")

    def test_aoomee_provenance_matches_feed_order_when_url_rewrite_precedes_rewrite(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        aoomee_files = {
            # parse_loose_sections() stores section buckets, and ao_rw appends
            # Rewrite before URL Rewrite regardless of their physical order.
            # Provenance must use that same flattening order, not raw file order.
            "a_legacy.lpx": (
                "[URL Rewrite]\n"
                "^https://legacy.example/legacy reject\n"
                "[Rewrite]\n"
                "^https://native.example/native reject\n"
            ),
            "pdd.lpx": (
                "[Rewrite]\n"
                "^http://139.196.12.179:8053/httpdns/ reject\n"
            ),
        }
        _, provenance = self.run_merge(
            base, extra, aoomee_files=aoomee_files, return_provenance=True
        )
        by_output = {row["output_line"]: row for row in provenance["rewrite"]}
        expected = {
            "^https://native.example/native reject":
                ("plugins/a_legacy.lpx", 4, "Rewrite"),
            "^https://legacy.example/legacy reject":
                ("plugins/a_legacy.lpx", 2, "URL Rewrite"),
            "^http://139.196.12.179:8053/httpdns/ reject":
                ("plugins/pdd.lpx", 2, "Rewrite"),
        }
        for output_line, (source_file, line_number, section) in expected.items():
            source = next(
                item for item in by_output[output_line]["sources"]
                if item["source"] == "aoomee"
            )
            self.assertEqual(source["source_file"], source_file)
            self.assertEqual(source["source_line_number"], line_number)
            self.assertEqual(source["source_original_section"], section)
            self.assertEqual(source["source_raw_line"], output_line)
            self.assertEqual(source["input_line"], output_line)

    def test_aoomee_provenance_uses_retained_feed_indexes_after_semantic_exclusions(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        aoomee_files = {
            "a_legacy.lpx": (
                "[Rewrite]\n"
                "^https://ssp\\.soulapp\\.cn/api/q reject-dict\n"
                "^https?://hweb-manager\\.huazhu\\.com/notice/getAppPopupNotifyAlert(?:\\?.*)?$ reject-dict\n"
                "^https://native.example/native reject\n"
                "[URL Rewrite]\n"
                "^https://legacy.example/legacy reject\n"
            ),
            "pdd.lpx": (
                "[Rewrite]\n"
                "^http://139.196.12.179:8053/httpdns/ reject\n"
            ),
        }
        _, provenance = self.run_merge(
            base, extra, aoomee_files=aoomee_files, return_provenance=True
        )
        by_output = {row["output_line"]: row for row in provenance["rewrite"]}
        pdd = next(
            item for item in by_output[
                "^http://139.196.12.179:8053/httpdns/ reject"
            ]["sources"] if item["source"] == "aoomee"
        )
        self.assertEqual(pdd["source_file"], "plugins/pdd.lpx")
        self.assertEqual(pdd["source_line_number"], 2)
        self.assertEqual(
            pdd["source_raw_line"],
            "^http://139.196.12.179:8053/httpdns/ reject"
        )
        exclusions = provenance["rewrite_exclusions"]
        aoomee_exclusions = [
            item for item in exclusions if item.get("source") == "aoomee"
        ]
        self.assertEqual(len(aoomee_exclusions), 2)
        self.assertEqual(
            {item["source_section_entry_index"] for item in aoomee_exclusions},
            {0, 1}
        )
        self.assertEqual(
            {item["source_file"] for item in aoomee_exclusions},
            {"a_legacy.lpx"}
        )

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

    def test_audited_semantic_duplicate_rewrites_are_removed_but_covered_base_rules_remain(self):
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/vv\.video\.qq\.com\/(?:diff|get)vmind reject-dict" + "\n"
            r"^https?:\/\/ssp\.soulapp\.cn\/api\/q reject-dict" + "\n"
            r"^https?:\/\/hweb-manager\.huazhu\.com\/notice\/getAppPopupNotifyAlert reject-dict" + "\n"
            "[MITM]\nhostname = \n"
        )
        apps = {
            "video_ad_block.plugin": (
                "[Rewrite]\n"
                r"^https?:\/\/vv\.video\.qq\.com\/(diff|get)vmind reject-dict" + "\n"
                "[MITM]\nhostname = \n"
            )
        }
        aoomee = {
            "soul.plugin": (
                "[Rewrite]\n"
                r"^https:\/\/ssp\.soulapp\.cn\/api\/q reject-dict" + "\n"
                r"^https?:\/\/hweb-manager\.huazhu\.com\/notice\/getAppPopupNotifyAlert(?:\?.*)?$ reject-dict" + "\n"
                "[MITM]\nhostname = \n"
            )
        }
        output, report = self.run_merge(
            base, "[Rewrite]\n[MITM]\nhostname = \n",
            apps_files=apps, aoomee_files=aoomee, return_provenance=True)
        self.assertIn(r"vv\.video\.qq\.com\/(?:diff|get)vmind reject-dict", output)
        self.assertNotIn(r"vv\.video\.qq\.com\/(diff|get)vmind reject-dict", output)
        self.assertIn(r"ssp\.soulapp\.cn\/api\/q reject-dict", output)
        self.assertNotIn(r"^https:\/\/ssp\.soulapp\.cn\/api\/q reject-dict", output)
        self.assertIn(r"hweb-manager\.huazhu\.com\/notice\/getAppPopupNotifyAlert reject-dict", output)
        self.assertNotIn(r"getAppPopupNotifyAlert(?:\?.*)?$", output)
        exclusions = [
            item for item in report.get("rewrite_exclusions", [])
            if item.get("status") == "excluded_semantic_duplicate"
        ]
        self.assertEqual(len(exclusions), 3, exclusions)
        self.assertEqual({item["source"] for item in exclusions}, {"thelong", "aoomee"})
        self.assertEqual({item["action"] for item in exclusions}, {"reject-dict"})
        self.assertTrue(all(item.get("covered_by") for item in exclusions))

        changed_action_apps = {
            "video_ad_block.plugin": (
                "[Rewrite]\n"
                r"^https?:\/\/vv\.video\.qq\.com\/(diff|get)vmind reject" + "\n"
                "[MITM]\nhostname = \n"
            )
        }
        self.run_merge(
            base, "[Rewrite]\n[MITM]\nhostname = \n",
            apps_files=changed_action_apps, expect_failure=True)

    def test_mgtv_unused_indexes_probe_is_excluded_without_removing_ad_endpoints(self):
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/[\d\.]+:\d{5}\/\?cmd=indexes reject" + "\n"
            r"^https?:\/\/[\d\.]+:\d{5}\/\?cmd=indexes reject-200" + "\n"
            r"^https?:\/\/[\d\.]+:\d{5}\/\?cmd=health reject" + "\n"
            r"^https?:\/\/[\d\.]+\/odin\/c\d\/(channel\/ads|skin\/config)\? reject-dict" + "\n"
            "[MITM]\nhostname = \n"
        )
        extra = (
            "[Rewrite]\n"
            r"request if " + "$" + "{url}" + r" ~= /^https?:\/\/[\d\.]+:\d{5}\/\?cmd=indexes/ then reject(404)" + "\n"
            r"request if " + "$" + "{url}" + r" ~= /^https?:\/\/[\d\.]+:\d{5}\/\?cmd=indexes/ then reject" + "\n"
            r"request if " + "$" + "{url}" + r" ~= /^https?:\/\/[\d\.]+:\d{5}\/\?cmd=health/ then reject(404)" + "\n"
            r"request if " + "$" + "{url}" + r" ~= /^https?:\/\/[\d\.]+\/odin\/c1\/(channel\/ads|skin\/config)\?/ then reject_dict(200)" + "\n"
            "[MITM]\nhostname = \n"
        )
        output, report = self.run_merge(base, extra, return_provenance=True)
        self.assertNotIn(r"cmd=indexes", output)
        self.assertIn(r"cmd=health", output)
        self.assertIn(r"odin\/c\d", output)
        exclusions = [
            item for item in report.get("rewrite_exclusions", [])
            if item.get("status") == "excluded_non_ad_probe"
        ]
        self.assertEqual(len(exclusions), 4)
        self.assertEqual({item["source"] for item in exclusions}, {"base", "block"})
        self.assertEqual(
            {item["action"] for item in exclusions},
            {"reject", "reject-200", "reject(404)"},
        )
        self.assertTrue(all(item["matcher"] == r"^https?://[\d\.]+:\d{5}/\?cmd=indexes"
                            for item in exclusions))

    def test_active_tencent_httpdns_endpoints_are_not_blocked_by_broad_ip_rule(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n"
            r"request if " + "${url}" + r" ~= /^https?:\/\/119\.29\.29\.\d+\/d/ then reject(200)" + "\n"
            # An upstream spelling change to the default reject alias must not bypass the guard.
            r"request if " + "${url}" + r" ~= /^https?:\/\/119\.29\.29\.\d+\/d/ then reject" + "\n"
            r"request if " + "${url}" + r" ~= /^https?:\/\/119\.29\.29\.98\/health/ then reject(200)" + "\n"
            "[MITM]\nhostname = \n"
        )
        output, report = self.run_merge(base, extra, return_provenance=True)
        self.assertNotIn(r"119\.29\.29\.\d+\/d", output)
        self.assertIn(r"119\.29\.29\.98\/health", output)
        exclusions = report.get("rewrite_exclusions", [])
        self.assertEqual(len(exclusions), 2)
        self.assertEqual({x["source"] for x in exclusions}, {"block"})
        self.assertEqual({x["status"] for x in exclusions}, {"excluded_safety_guard"})
        self.assertEqual({x["action"] for x in exclusions}, {"reject(200)", "reject"})
        self.assertIn("119.29.29.98", exclusions[0]["reason"])
        self.assertIn("119.29.29.99", exclusions[0]["reason"])

    def test_active_tencent_httpdns_ip_endpoints_are_excluded_from_exact_reject_rules(self):
        base = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rule]\n"
            "IP-CIDR,119.29.29.98/32,DIRECT\n"
            "[Rewrite]\n[MITM]\nhostname = \n"
        )
        filter_text = (
            "IP-CIDR,119.29.29.98/32,REJECT\n"
            "IP-CIDR,119.29.29.99/32,REJECT\n"
            "IP-CIDR,119.29.29.90/32,REJECT\n"
        )
        output, report = self.run_merge(
            base, extra, filter_text=filter_text, return_provenance=True)
        self.assertNotIn("IP-CIDR,119.29.29.98/32,REJECT", output)
        self.assertNotIn("IP-CIDR,119.29.29.99/32,REJECT", output)
        self.assertIn("IP-CIDR,119.29.29.90/32,REJECT", output)
        self.assertIn("IP-CIDR,119.29.29.98/32,DIRECT", output)
        exclusions = [
            item for item in report["rule_events"]
            if item.get("status") == "excluded_safety_guard"
        ]
        self.assertEqual(len(exclusions), 2)
        self.assertEqual({item["source"] for item in exclusions}, {"filter"})
        self.assertEqual(
            {item["matched_ip"] for item in exclusions},
            {"119.29.29.98", "119.29.29.99"},
        )
        self.assertTrue(all("HTTPDNS" in item["reason"] for item in exclusions))

    def test_jd_lite_unreachable_response_rewrites_are_excluded_only_with_terminal_request_guard(self):
        request_guard = r'^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising reject'
        block_response = r'response if ${url} ~= /^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising/ then response.body.replace(/jdLiteAdvertisingVO/, "fmz200")'
        thelong_response = r'^https?:\/\/api\.m\.jd\.com\/client\.action\?functionId=lite_advertising response-body-replace-regex jdLiteAdvertisingVO sooyaaabo'
        base = "[Rewrite]\n" + request_guard + "\n[MITM]\nhostname = api.m.jd.com\n"
        extra = "[Rewrite]\n" + block_response + "\n[MITM]\nhostname = api.m.jd.com\n"
        apps = {"jd_splash_ad_block.plugin": "[Rewrite]\n" + thelong_response + "\n[MITM]\nhostname = api.m.jd.com\n"}
        output, report = self.run_merge(base, extra, apps_files=apps, return_provenance=True)
        self.assertIn("lite_advertising reject", output)
        self.assertNotIn("jdLiteAdvertisingVO", output)
        exclusions = [x for x in report["rewrite_exclusions"] if x.get("status") == "excluded_unreachable_response_rule"]
        self.assertEqual({x["source"] for x in exclusions}, {"block", "thelong"})

        # Without the terminal request-phase guard, response rewrites remain effective and untouched.
        no_guard = self.run_merge("[Rewrite]\n[MITM]\nhostname = api.m.jd.com\n", extra, apps_files=apps)
        self.assertIn("jdLiteAdvertisingVO", no_guard)
        self.assertIn("response-body-replace-regex jdLiteAdvertisingVO sooyaaabo", no_guard)

    def test_unused_zhangle_rules_are_removed_from_base_and_block_with_shared_mitm_safety(self):
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/c\.zhangle\.com\/pic\/mktg\/diversity\/.+\.jpg$ reject-dict" + "\n"
            r"^https?:\/\/live\.inst-service\.htsc\.com\/live reject-dict" + "\n"
            r"^https?:\/\/geetest\.htsc\.com:\d+\/pre_get_token reject-200" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com\n"
        )
        block = (
            "[Rewrite]\n"
            r"request if @URL@ ~= /^https?:\/\/c\.zhangle\.com\/pic\/mktg\/diversity\/.+\.jpg$/ then reject_dict(200)" + "\n"
            r"request if @URL@ ~= /^https?:\/\/live\.inst-service\.htsc\.com\/live/ then reject_dict(200)" + "\n"
            r"request if @URL@ ~= /^https?:\/\/geetest\.htsc\.com:8888\/pre_get_token/ then reject(200)" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com\n"
        ).replace("@URL@", "$"+"{url}")
        output, report = self.run_merge(base, block, return_provenance=True)
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, output)
        exclusions = [x for x in report["rewrite_exclusions"] if x.get("status") == "excluded_unused_app"]
        self.assertEqual(len(exclusions), 6)
        self.assertEqual({x["source"] for x in exclusions}, {"base", "block"})

        shared_base = base.replace("[Rewrite]\n", "[Rewrite]\n" + r"^https?:\/\/geetest\.htsc\.com\/health reject" + "\n")
        shared = self.run_merge(shared_base, block)
        shared_mitm = next(line for line in shared.splitlines() if line.strip().startswith("hostname ="))
        self.assertIn("geetest.htsc.com", shared_mitm)
        self.assertIn(r"geetest\.htsc\.com\/health", shared)

    def test_g1_163_madfeedback_matcher_escapes_literal_hostname_dots(self):
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/g1.163.com\/madfeedback reject" + "\n"
            + "[Script]\n[MITM]\nhostname = g1.163.com\n"
        )
        block = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https?:\/\/g1.163.com\/madfeedback/ then reject(404)" + "\n"
            + "[Script]\n[MITM]\nhostname = g1.163.com\n"
        )
        output, report = self.run_merge(base, block, return_provenance=True)
        rule = next(line for line in output.splitlines() if "madfeedback" in line)
        self.assertIn(r"g1\.163\.com", rule)
        self.assertNotIn("g1.163.com", rule.replace(r"g1\.163\.com", ""))
        matcher = rule.split()[0].replace(r"\/", "/")
        self.assertRegex("https://g1.163.com/madfeedback", matcher)
        self.assertNotRegex("https://g1x163xcom/madfeedback", matcher)
        self.assertEqual(
            {item["source"] for item in report["scope_adjustments"]
             if "g1.163.com" in item.get("reason", "")},
            {"base", "block"},
        )

    def test_targeted_ad_matchers_escape_literal_hostname_dots(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        dili_rule = (
            r"request if ${url} ~= /http:\/\/dili.sqcosmos.com"
            r"\/jiekou\/endpage\/ad/ then reject_dict(200)"
        )
        dili_block = (
            "[Rewrite]\n" + dili_rule + "\n"
            + "[Script]\n[MITM]\nhostname = dili.sqcosmos.com\n"
        )
        output, report = self.run_merge(empty, dili_block, return_provenance=True)
        dili_output = next(line for line in output.splitlines()
                           if line.startswith("request if") and "dili" in line)
        self.assertIn(r"dili\.sqcosmos\.com", dili_output)
        dili_matcher = re.search(r"~= /(.*)/ then ", dili_output).group(1).replace(r"\/", "/")
        self.assertRegex("http://dili.sqcosmos.com/jiekou/endpage/ad", dili_matcher)
        self.assertNotRegex("http://diliXsqcosmosYcom/jiekou/endpage/ad", dili_matcher)
        adjustments = [item for item in report["scope_adjustments"]
                       if "lookalike hosts" in item.get("reason", "")]
        self.assertEqual(len(adjustments), 1)
        self.assertEqual({item["source"] for item in adjustments}, {"block"})

    def test_xiaoyi_mobile_ads_matcher_escapes_literal_hostname_dots(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if ${url} ~= /^https?:\/\/api.xiaoyi.com"
            r"\/v5\/app\/mobile\/ads/ then reject(404)"
        )
        block = (
            "[Rewrite]\n" + rule + "\n"
            + "[Script]\n[MITM]\nhostname = api.xiaoyi.com\n"
        )
        output, report = self.run_merge(empty, block, return_provenance=True)
        result = next(line for line in output.splitlines()
                      if line.startswith("request if") and "xiaoyi" in line)
        self.assertIn(r"api\.xiaoyi\.com", result)
        matcher = re.search(r"~= /(.*)/ then ", result).group(1).replace(r"\/", "/")
        self.assertRegex("https://api.xiaoyi.com/v5/app/mobile/ads", matcher)
        self.assertNotRegex("https://apiXxiaoyiYcom/v5/app/mobile/ads", matcher)
        adjustments = [
            item for item in report["scope_adjustments"]
            if "api.xiaoyi.com" in item.get("reason", "")
        ]
        self.assertEqual(len(adjustments), 1)
        self.assertEqual({item["source"] for item in adjustments}, {"block"})
        self.assertEqual(adjustments[0]["original_line"], rule)
        self.assertEqual(adjustments[0]["output_line"], result)

    def test_xiaoyi_mobile_ads_matcher_fails_closed_on_action_drift(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if @@URL@@ ~= /^https?:\/\/api.xiaoyi.com"
            r"\/v5\/app\/mobile\/ads/ then reject_dict(200)"
        ).replace("@@URL@@", "$"+"{url}")
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[Script]\n[MITM]\nhostname = api.xiaoyi.com\n"
        )
        output = self.run_merge(empty, extra, expect_failure=True)
        self.assertIn("广告接口拦截动作已变化", output)


    def test_peopleapp_ad_image_extension_dot_is_literal_for_base_and_block_sources(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        cases = (
            (
                "base",
                r"request if @@URL@@ ~= /^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*.(?:jpg|png)/ then reject(200)",
            ),
            (
                "block",
                r"request if @@URL@@ ~= /^https?:\/\/adstatic\.peopleapp\.com\/upload\/AppLoad\/.*.(jpg|png)/ then reject(200)",
            ),
        )
        for source, template in cases:
            with self.subTest(source=source):
                rule = template.replace("@@URL@@", "$"+"{url}")
                base_text = (
                    "[Rewrite]\n" + (rule + "\n" if source == "base" else "")
                    + "[Script]\n[MITM]\nhostname = \n"
                )
                extra_text = (
                    "[Rewrite]\n" + (rule + "\n" if source == "block" else "")
                    + "[Script]\n[MITM]\nhostname = adstatic.peopleapp.com\n"
                )
                output, report = self.run_merge(
                    base_text, extra_text, return_provenance=True
                )
                result = next(
                    line for line in output.splitlines()
                    if line.startswith("request if") and "adstatic" in line
                )
                self.assertIn(r".*\.(?:jpg|png)" if source == "base"
                              else r".*\.(jpg|png)", result)
                matcher = re.search(r"~= /(.*)/ then ", result).group(1).replace(r"\/", "/")
                self.assertRegex(
                    "https://adstatic.peopleapp.com/upload/AppLoad/banner.jpg",
                    matcher,
                )
                self.assertRegex(
                    "https://adstatic.peopleapp.com/upload/AppLoad/banner.png",
                    matcher,
                )
                self.assertNotRegex(
                    "https://adstatic.peopleapp.com/upload/AppLoad/bannerxjpg",
                    matcher,
                )
                self.assertNotRegex(
                    "https://adstatic.peopleapp.com/upload/AppLoad/bannerxpng",
                    matcher,
                )
                adjustments = [
                    item for item in report["scope_adjustments"]
                    if "PeopleApp AppLoad ad-image" in item.get("reason", "")
                ]
                self.assertEqual(len(adjustments), 1)
                self.assertEqual({item["source"] for item in adjustments}, {source})
                self.assertEqual(adjustments[0]["original_line"], rule)
                self.assertEqual(adjustments[0]["output_line"], result)

    def test_known_ad_and_splash_image_extension_dots_are_literal_across_sources(self):
        base_lines = (
            r"^https?:\/\/static\.95508\.com\/icppweb\/images\/modelMaterial\/(advertising|accurate)\/202\d{5}\/.*.(?:png|jpg) reject-200",
            r"^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/2022\/0[4-9]{1}\/.*.jpg reject-200",
            r"^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/2022\/1[0-2]{1}\/.*.jpg reject-200",
            r"^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/202\d{1}\/\d{2}\/.*.jpg reject-200",
        )
        block_templates = (
            r"request if @@URL@@ ~= /^https?:\/\/img\.admobile\.top\/admobile-adRequest\/.*.(jpg|png)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/img\.gdoil\.cn\/upload\/ad\/.*.(jpg|png)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/img\.wukongtv\.com\/wkremote\/AD\/iOS\/.*.(jpg|png|jpeg)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/ads\.iconntech\.com\/resource-delivery\/*\/.*.(jpg|png)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/static\.xyzq\.cn\/image\/splash\/opera3.*.jpg/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/static\.95508\.com\/icppweb\/images\/modelMaterial\/accurate\/202\d{5}\/.*.(png|jpg)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/static\.95508\.com\/icppweb\/images\/modelMaterial\/advertising\/202\d{5}\/.*.(png|jpg)/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/2022\/0[4-9]{1}\/.*.jpg/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/2022\/1[0-2]{1}\/.*.jpg/ then reject(200)",
            r"request if @@URL@@ ~= /^https?:\/\/l[0-9]{1}\.51fanli\.net\/app\/images\/splash\/202\d{1}\/\d{2}\/.*.jpg/ then reject(200)",
        )
        block_lines = [
            template.replace("@@URL@@", "$" + "{url}")
            for template in block_templates
        ]
        base_text = (
            "[Rewrite]\n" + "\n".join(base_lines) + "\n"
            + "[Script]\n[MITM]\nhostname = \n"
        )
        extra_text = (
            "[Rewrite]\n" + "\n".join(block_lines) + "\n"
            + "[Script]\n[MITM]\nhostname = \n"
        )
        output, report = self.run_merge(
            base_text, extra_text, return_provenance=True
        )

        def matcher_for(fragment):
            line = next(
                line for line in output.splitlines()
                if (line.startswith("request if") or line.startswith("^https?"))
                and fragment in line.replace(r"\.", ".")
            )
            if line.startswith("request if"):
                matcher = re.search(r"~= /(.*)/ then ", line).group(1)
            else:
                matcher = line.split()[0]
            return re.compile(matcher)

        cases = (
            (
                "img.admobile.top",
                "https://img.admobile.top/admobile-adRequest/2026/banner.jpg",
                "https://img.admobile.top/admobile-adRequest/2026/bannerxjpg",
            ),
            (
                "img.gdoil.cn",
                "https://img.gdoil.cn/upload/ad/banner.png",
                "https://img.gdoil.cn/upload/ad/bannerxpng",
            ),
            (
                "img.wukongtv.com",
                "https://img.wukongtv.com/wkremote/AD/iOS/banner.jpeg",
                "https://img.wukongtv.com/wkremote/AD/iOS/bannerxjpeg",
            ),
            (
                "ads.iconntech.com",
                "https://ads.iconntech.com/resource-delivery/slot/banner.jpg",
                "https://ads.iconntech.com/resource-delivery/slot/bannerxjpg",
            ),
            (
                "static.xyzq.cn",
                "https://static.xyzq.cn/image/splash/opera3.abc.jpg",
                "https://static.xyzq.cn/image/splash/opera3.abcXjpg",
            ),
            (
                "static.95508.com",
                "https://static.95508.com/icppweb/images/modelMaterial/advertising/20261112/banner.png",
                "https://static.95508.com/icppweb/images/modelMaterial/advertising/20261112/bannerXpng",
            ),
            (
                "51fanli.net",
                "https://l1.51fanli.net/app/images/splash/2022/04/banner.jpg",
                "https://l1.51fanli.net/app/images/splash/2022/04/bannerXjpg",
            ),
        )
        for fragment, valid_url, invalid_url in cases:
            with self.subTest(target=fragment):
                matcher = matcher_for(fragment)
                self.assertRegex(valid_url, matcher)
                self.assertNotRegex(invalid_url, matcher)

        target_names = {
            "叮嗒出行 admobile 广告图片",
            "加油广东广告图片",
            "悟空遥控器 AD/iOS 图片",
            "杭州市民广告投放素材",
            "优理宝开屏图片",
            "广发银行 advertising/accurate 图片素材",
            "返利网开屏图片",
        }
        adjustments = [
            item for item in report["scope_adjustments"]
            if item.get("target") in target_names
        ]
        self.assertEqual(len(adjustments), 12, repr([(item["source"], item["target"], item["original_line"]) for item in adjustments]))
        self.assertEqual(sum(item["source"] == "base" for item in adjustments), 3)
        self.assertEqual(sum(item["source"] == "block" for item in adjustments), 9)
        for item in adjustments:
            self.assertIn(r".*\.", item["output_line"])
            self.assertNotEqual(item["original_line"], item["output_line"])

    def test_known_ad_image_extension_helper_is_idempotent_for_already_escaped_rules(self):
        base_text = (
            "[Rewrite]\n"
            + r"^https?:\/\/static\.95508\.com\/icppweb\/images\/modelMaterial\/advertising\/20261112\/.*\.(?:png|jpg) reject-200"
            + "\n[Script]\n[MITM]\nhostname = \n"
        )
        extra_text = (
            "[Rewrite]\n"
            + r"request if @@URL@@ ~= /^https?:\/\/img\.gdoil\.cn\/upload\/ad\/.*\.(jpg|png)/ then reject(200)"
            + "\n[Script]\n[MITM]\nhostname = \n"
        ).replace("@@URL@@", "$" + "{url}")
        _, report = self.run_merge(base_text, extra_text, return_provenance=True)
        target_adjustments = [
            item for item in report["scope_adjustments"]
            if item.get("target")
        ]
        self.assertEqual(target_adjustments, [])

    def test_known_ad_image_extension_guard_fails_closed_on_action_drift(self):
        base_text = (
            "[Rewrite]\n"
            + r"^https?:\/\/img\.gdoil\.cn\/upload\/ad\/.*.(jpg|png) reject-dict"
            + "\n[Script]\n[MITM]\nhostname = \n"
        )
        extra_text = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        output = self.run_merge(base_text, extra_text, expect_failure=True)
        self.assertIn("加油广东广告图片 图片规则动作已变化", output)


    def test_gamersky_list_response_filter_has_exact_host_and_path_scope(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        jq_action = (
            'then response.json.jq(' + chr(96)
            + '.listElements |= map(select(has("adCategory") | not))'
            + chr(96) + ')'
        )
        rule = (
            r'response if ${url} ~= /http:\/\/.+\.gamersky.com\/.+\/lists\/getListElements/ '
            + jq_action
        )
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output, report = self.run_merge(empty, extra, return_provenance=True)
        result = next(
            line for line in output.splitlines()
            if line.startswith("response if") and "getListElements" in line
        )
        self.assertIn(r"^http:\/\/", result)
        self.assertIn(r"gamersky\.com\/.+\/lists\/getListElements(?:\/|\?|#|$)", result)
        self.assertIn("response.json.jq(", result)
        self.assertIn('has("adCategory")', result)
        matcher = re.search(r"~= /(.*)/ then ", result).group(1).replace(r"\/", "/")
        for url in (
            "http://a.gamersky.com/api/v1/lists/getListElements",
            "http://a-b.gamersky.com/api/v1/lists/getListElements?channel=app",
            "http://a.b.gamersky.com/api/v1/lists/getListElements/items",
        ):
            self.assertRegex(url, matcher)
        for url in (
            "https://a.gamersky.com/api/v1/lists/getListElements",
            "http://gamersky.com/api/v1/lists/getListElements",
            "http://evilgamersky.com/api/v1/lists/getListElements",
            "http://a.gamerskyXcom/api/v1/lists/getListElements",
            "http://a.gamersky.com.evil.test/api/v1/lists/getListElements",
            "http://a..gamersky.com/api/v1/lists/getListElements",
            "http://a.gamersky.com/api/v1/lists/getListElementsExtra",
        ):
            self.assertNotRegex(url, matcher)
        changes = [
            item for item in report["scope_adjustments"]
            if "Gamersky list-ad response filter" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "block")
        self.assertEqual(changes[0]["original_line"], rule)
        self.assertEqual(changes[0]["output_line"], result)

    def test_gamersky_list_response_guard_fails_closed_on_source_drift(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        jq_action = (
            'then response.json.jq(' + chr(96)
            + '.listElements |= map(select(has("adCategory") | not))'
            + chr(96) + ')'
        )
        rule = (
            r'response if ${url} ~= /http:\/\/.+\.gamersky.com\/.+\/lists\/getListElements/ '
            + jq_action
        )
        changed = rule.replace('has("adCategory")', 'has("sponsored")')
        extra = (
            "[Rewrite]\n" + changed + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output = self.run_merge(empty, extra, expect_failure=True)
        self.assertIn("游民星空列表广告响应规则范围或过滤动作已变化", output)


    def test_gamersky_statistic_ad_rule_has_valid_regex_and_exact_scope(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if ${url} ~= /https:\/\/.+\.gamersky.com\/v1\/statisticAd/"
            r" then reject_dict(200)"
        )
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output, report = self.run_merge(empty, extra, return_provenance=True)
        result = next(
            line for line in output.splitlines()
            if line.startswith("request if") and "statisticAd" in line
        )
        self.assertIn(r"^https:\/\/", result)
        self.assertIn(r"gamersky\.com\/v1\/statisticAd(?:\/|\?|#|$)", result)
        matcher = re.search(r"~= /(.*)/ then ", result).group(1).replace(r"\/", "/")
        for url in (
            "https://a.gamersky.com/v1/statisticAd",
            "https://a-b.gamersky.com/v1/statisticAd?from=app",
            "https://a.gamersky.com/v1/statisticAd#source=app",
            "https://a.b.gamersky.com/v1/statisticAd/collect",
        ):
            self.assertRegex(url, matcher)
        for url in (
            "http://a.gamersky.com/v1/statisticAd",
            "https://gamersky.com/v1/statisticAd",
            "https://evilgamersky.com/v1/statisticAd",
            "https://a.gamerskyXcom/v1/statisticAd",
            "https://a.gamersky.com.evil.test/v1/statisticAd",
            "https://a..gamersky.com/v1/statisticAd",
            "https://a.gamersky.com/v1/statisticAdx",
            "https://a.gamersky.com/other/statisticAd",
        ):
            self.assertNotRegex(url, matcher)
        changes = [
            item for item in report["scope_adjustments"]
            if "Gamersky statisticAd" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "block")
        self.assertEqual(changes[0]["original_line"], rule)
        self.assertEqual(changes[0]["output_line"], result)

    def test_gamersky_statistic_ad_guard_fails_closed_on_action_drift(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if ${url} ~= /https:\/\/.+\.gamersky.com\/v1\/statisticAd/"
            r" then reject(404)"
        )
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output = self.run_merge(empty, extra, expect_failure=True)
        self.assertIn("游民星空 statisticAd 广告规则范围或动作已变化", output)


    def test_gamersky_ad_system_rule_is_limited_to_valid_declared_subdomains(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if ${url} ~= /^http:\/\/.+\.gamersky\.com\/.+"
            r"\/adSystem\/ad\/.+/ then reject_dict(200)"
        )
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output, report = self.run_merge(empty, extra, return_provenance=True)
        result = next(
            line for line in output.splitlines()
            if line.startswith("request if") and "gamersky" in line
            and "adSystem" in line
        )
        self.assertIn(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+", result)
        matcher = re.search(r"~= /(.*)/ then ", result).group(1).replace(r"\/", "/")
        for url in (
            "http://a.gamersky.com/api/adSystem/ad/banner",
            "http://a-b.gamersky.com/api/adSystem/ad/banner",
            "http://a.b.gamersky.com/api/adSystem/ad/banner",
        ):
            self.assertRegex(url, matcher)
        for url in (
            "http://gamersky.com/api/adSystem/ad/banner",
            "http://evilgamersky.com/api/adSystem/ad/banner",
            "http://a..gamersky.com/api/adSystem/ad/banner",
            "http://-bad.gamersky.com/api/adSystem/ad/banner",
            "http://a.gamersky.com.evil.test/api/adSystem/ad/banner",
            "https://a.gamersky.com/api/adSystem/ad/banner",
        ):
            self.assertNotRegex(url, matcher)
        changes = [
            item for item in report["scope_adjustments"]
            if "Gamersky adSystem endpoint" in item.get("reason", "")
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "block")
        self.assertEqual(changes[0]["original_line"], rule)
        self.assertEqual(changes[0]["output_line"], result)

    def test_gamersky_ad_system_guard_fails_closed_on_action_drift(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if ${url} ~= /^http:\/\/.+\.gamersky\.com\/.+"
            r"\/adSystem\/ad\/.+/ then reject(404)"
        )
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[MITM]\nhostname = api.gamersky.com\n"
        )
        output = self.run_merge(empty, extra, expect_failure=True)
        self.assertIn("游民星空 adSystem 广告规则范围或动作已变化", output)


    def test_peopleapp_ad_image_extension_guard_fails_closed_on_action_drift(self):
        empty = "[Rewrite]\n[Script]\n[MITM]\nhostname = \n"
        rule = (
            r"request if @@URL@@ ~= /^https?:\/\/adstatic\.peopleapp\.com"
            r"\/upload\/AppLoad\/.*.(jpg|png)/ then reject_dict(200)"
        ).replace("@@URL@@", "$"+"{url}")
        extra = (
            "[Rewrite]\n" + rule + "\n"
            + "[Script]\n[MITM]\nhostname = adstatic.peopleapp.com\n"
        )
        output = self.run_merge(empty, extra, expect_failure=True)
        self.assertIn("PeopleApp 图片广告拦截动作已变化", output)


    def test_qidian_magev6_ad_matchers_escape_literal_hostname_dots(self):
        qidian_paths = (
            "/argus/api/v1/client/iosad",
            "/argus/api/v1/bookshelf/getad",
            "/argus/api/v4/client/getsplashscreen?",
        )
        extra = (
            "[Rewrite]\n"
            "# > 起点读书\n"
            "# hostname = qidian.qpic.cn, mage.if.qidian.com, magev6.if.qidian.com\n"
            + "".join(
                "request if " + "$" + "{url} ~= /^https?:\/\/magev6.if.qidian.com"
                + path.replace("/", r"\/")
                + r"/ then reject(404)" + "\n"
                for path in qidian_paths
            )
            + "[MITM]\nhostname = magev6.if.qidian.com\n"
        )
        empty = "[Rule]\n[Rewrite]\n[MITM]\nhostname = \n"
        output = self.run_merge(empty, extra)
        qidian_rules = [
            line for line in output.splitlines()
            if line.startswith("request if ") and "magev6" in line
        ]
        self.assertEqual(len(qidian_rules), 3, repr(qidian_rules))
        url_paths = (
            "/argus/api/v1/client/iosad/",
            "/argus/api/v1/bookshelf/getad/",
            "/argus/api/v4/client/getsplashscreen",
        )
        for line, path in zip(qidian_rules, url_paths):
            self.assertIn(r"magev6\.if\.qidian\.com", line)
            self.assertNotIn("magev6.if.qidian.com", line.replace(
                r"magev6\.if\.qidian\.com", ""))
            matcher = line.split(" ~= /", 1)[1].split("/ then", 1)[0]
            matcher = matcher.replace(r"\/", "/")
            compiled = re.compile(matcher)
            self.assertIsNotNone(compiled.search("https://magev6.if.qidian.com" + path))
            self.assertIsNone(compiled.search("https://magev6XifYqidianZcom" + path))

    def test_bracketed_optional_https_scheme_is_parsed_for_mitm_pruning(self):
        # Some upstream Loon rules spell the scheme as http[s]? rather than https?.
        # The host extractor must identify the same HTTPS authority and not let
        # this unrelated Qidian matcher retain ZhangLe-only MITM hosts.
        base = (
            "[Rewrite]\n"
            r"^http[s]?://magev6\.if\.qidian\.com/argus/api/v1/bookshelf/refresh reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, magev6.if.qidian.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("magev6.if.qidian.com", mitm_line)

    def test_slash_inside_host_character_class_is_not_path_boundary(self):
        # The pangle matcher uses [^\s/] in its authority. The slash belongs
        # to the character class; parsing it as the path boundary produced an
        # invalid "[^\s" host regex and conservatively retained unrelated MITM.
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/[^\s/]*\.pangle\.cn\/advertisement\/ reject" + "\n"
            + "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, foo.pangle.cn\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("foo.pangle.cn", mitm_line)

    def test_leading_literal_closing_bracket_does_not_end_host_character_class(self):
        # In []/], the first closing bracket is a literal class member.
        # The slash remains inside the class until the final closing bracket.
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/[]/a-z]*\.pangle\.cn\/advertisement\/ reject" + "\n"
            + "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, foo.pangle.cn\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("foo.pangle.cn", mitm_line)

    def test_negated_class_with_leading_literal_closing_bracket_keeps_slash_inside(self):
        # In [^]/], ']' is also a literal first member after the negation.
        base = (
            "[Rewrite]\n"
            + r"^https?:\/\/[^]/]*\.pangle\.cn\/advertisement\/ reject" + "\n"
            + "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, foo.pangle.cn\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("foo.pangle.cn", mitm_line)

    def test_http_only_capture_group_does_not_disable_mitm_pruning(self):
        # A pure-HTTP redirect matcher with a capturing group cannot be parsed
        # by host_zone_from_regex. It must not be mistaken for HTTPS coverage.
        base = (
            "[Rewrite]\n"
            r'request if ' + '$' + '{url}' + r' ~= /^(http:\/\/www\.vgtime\.com\/app\/topic\/\d+\.jhtml\?.*?&close_ad=)false(&page=\d&sign=\w+&timestamp=\d+&font_size=\d$)/ then reject(404)' + "\n"
            r"^https?:\/\/other\.example\.com\/ad reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, other.example.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("other.example.com", mitm_line)

    # Protocol-specific authority captures exercise the exact production false-positive path.
    def test_http_only_authority_capture_group_does_not_keep_unrelated_mitm_hosts(self):
        # host_zone_from_regex can extract (.*) from ^http://(.*)/...
        # but HTTP-only rules do not require TLS interception.
        base = (
            "[Rewrite]\n"
            r"^http:\/\/(.*)\/ad reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)

    def test_https_authority_capture_group_keeps_mitm_hosts_conservatively(self):
        # The same broad authority capture is potentially HTTPS and must fail closed.
        base = (
            "[Rewrite]\n"
            r"^https:\/\/(.*)\/ad reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        self.assertIn("c.zhangle.com", mitm_line)

    def test_https_capture_group_still_fails_closed_for_mitm(self):
        # The same unparseable capture-group form is retained when its scheme
        # can match HTTPS; do not weaken the conservative safety boundary.
        base = (
            "[Rewrite]\n"
            r'request if ' + '$' + '{url}' + r' ~= /^(https:\/\/www\.example\.com\/path\/)(.*)$/ then reject(404)' + "\n"
            "[MITM]\nhostname = ads.example.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        self.assertIn("ads.example.com", mitm_line)

    def test_orphan_zhangle_mitm_hosts_are_removed_when_global_pruner_fails_closed(self):
        # ICU Unicode-property syntax is valid for Loon but not Python re, so the
        # generic MITM pruner conservatively keeps the full list. Only the three
        # exact ZhangLe hosts should be removed; unrelated hosts remain.
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/\p{L}+\.other\.example\.com\/ad reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, other.example.com\n"
        )
        output, report = self.run_merge(
            base, "[Rewrite]\n[MITM]\nhostname = \n",
            return_provenance=True,
        )
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("other.example.com", mitm_line)
        removed = {x["hostname"] for x in report.get("mitm_exclusions", [])
                   if x.get("source") == "merged_mitm"}
        self.assertEqual(removed, {
            "c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"
        })

    def test_escaped_path_separator_does_not_expand_host_zone(self):
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/(mkt-)?gateway\.tuhu\.cn(\/mkt)?\/mkt-cms\/circle\/recommend\/ reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, gateway.tuhu.cn\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("gateway.tuhu.cn", mitm_line)

    def test_icu_control_escape_cannot_match_dns_host_or_keep_unrelated_zhangle_mitm(self):
        # ICU \cX denotes a control character. The malformed KFC host zone
        # contains \cn, so it cannot match a valid DNS hostname; unlike broad
        # ICU constructs such as \p{L}, it must not retain unrelated MITM hosts.
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/res\.kfc\.com.\cn\/advertisement\/ reject" + "\n"
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)

    def test_zhangle_mitm_host_is_retained_if_unsupported_pattern_may_match_it(self):
        # The ICU matcher is not understood by Python re, but its literal suffix
        # proves it may target geetest.htsc.com; retain that MITM host.
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/\p{L}+\.htsc\.com\/health reject" + "\n"
            "[MITM]\nhostname = geetest.htsc.com, c.zhangle.com\n"
        )
        output = self.run_merge(base, "[Rewrite]\n[MITM]\nhostname = \n")
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        self.assertIn("geetest.htsc.com", mitm_line)
        self.assertNotIn("c.zhangle.com", mitm_line)

    def test_non_http_script_download_urls_do_not_keep_orphan_zhangle_mitm_hosts(self):
        # Generic/Cron/Network Changed script URLs are downloaded script sources,
        # not HTTP trigger matchers. They must not make unrelated MITM hosts look
        # referenced when the general pruner fails closed on ICU syntax.
        base = (
            "[Rewrite]\n"
            r"^https?:\/\/\p{L}+\.other\.example\.com\/ad reject" + "\n"
            "[Script]\n"
            'generic script-path=https://raw.githubusercontent.com/example/qunar.js,tag=Manual\n'
            'cron "0 * * * *" script-path=https://raw.githubusercontent.com/example/youtube.js,tag=Scheduled\n'
            'network-changed script-path=https://raw.githubusercontent.com/example/network.js,tag=Network\n'
            "[MITM]\nhostname = c.zhangle.com, live.inst-service.htsc.com, geetest.htsc.com, other.example.com\n"
        )
        output, report = self.run_merge(
            base, "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            return_provenance=True,
        )
        mitm_line = next(line for line in output.splitlines()
                         if line.strip().startswith("hostname ="))
        for host in ("c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"):
            self.assertNotIn(host, mitm_line)
        self.assertIn("other.example.com", mitm_line)
        removed = {x["hostname"] for x in report.get("mitm_exclusions", [])
                   if x.get("source") == "merged_mitm"}
        self.assertEqual(removed, {
            "c.zhangle.com", "live.inst-service.htsc.com", "geetest.htsc.com"
        })

    def test_zhangle_block_rule_drift_fails_closed(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        changed = (
            "[Rewrite]\n"
            r"request if @URL@ ~= /^https?:\/\/live\.inst-service\.htsc\.com\/live/ then reject(404)" + "\n"
            "[MITM]\nhostname = live.inst-service.htsc.com\n"
        ).replace("@URL@", "$"+"{url}")
        error = self.run_merge(base, changed, expect_failure=True)
        self.assertIn("涨乐财富通规则发生变化", error)

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
            r"request if ${url} ~= /^https?:\/\/display\.wting\.info\/.*.jpeg/ then reject(200)" + "\n"
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

    def test_thelong_provenance_tracks_origins_after_rewrite_filtering(self):
        base = (
            "[Rewrite]\n"
            r"^https?://api\.m\.jd\.com/client\.action\?functionId=lite_advertising reject" + "\n"
            "[Script]\n[MITM]\nhostname = api.m.jd.com, ads.example.com\n"
        )
        apps = {
            "a_jd_splash_ad_block.plugin": (
                "#!name=JD\n[Rewrite]\n"
                r"^https?://api\.m\.jd\.com/client\.action\?functionId=lite_advertising response-body-replace-regex jdLiteAdvertisingVO sooyaaabo" + "\n"
                "[MITM]\nhostname = api.m.jd.com\n"
            ),
            "z_sample_ad_block.plugin": (
                "#!name=Sample\n[Rewrite]\n"
                r"^https?://ads\.example\.com/launch reject" + "\n"
                "[MITM]\nhostname = ads.example.com\n"
            ),
        }
        _, report = self.run_merge(
            base, "[Rewrite]\n[Script]\n[MITM]\nhostname = \n",
            return_provenance=True, apps_files=apps,
        )
        record = next(x for x in report["rewrite"]
                      if "/launch" in x["output_line"])
        source = next(x for x in record["sources"] if x["source"] == "thelong")
        self.assertEqual(source["source_file"], "z_sample_ad_block.plugin")
        self.assertEqual(source["source_line_number"], 3)
        self.assertEqual(source["source_raw_line"], source["input_line"])
        self.assertEqual(source["input_line"], r"^https?://ads\.example\.com/launch reject")

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


    def test_tiantianjijin_start_image_preserves_response_envelope_over_request_rejects(self):
        matcher = r"^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg"
        base_reject = matcher + " reject"
        block_reject = (
            r"request if ${url} ~= /^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg/ "
            r"then reject(404)"
        )
        response_rule = matcher + " response-body-json-jq '.datas = []'"
        base = (
            "[Rewrite]\n" + base_reject + "\n"
            "[MITM]\nhostname = appactive.1234567.com.cn\n"
        )
        extra = (
            "[Rewrite]\n" + block_reject + "\n"
            "[MITM]\nhostname = appactive.1234567.com.cn\n"
        )
        apps_files = {
            "tiantianjijin_splash_ad_block.plugin": (
                "[Rewrite]\n"
                + response_rule + "\n"
                + "[MITM]\nhostname = appactive.1234567.com.cn\n"
            )
        }

        output, provenance = self.run_merge(
            base, extra, apps_files=apps_files, return_provenance=True
        )
        self.assertNotIn(base_reject, output)
        self.assertNotIn(block_reject, output)
        self.assertIn(response_rule, output)

        exclusions = [
            row for row in provenance["rewrite_exclusions"]
            if row.get("status") == "excluded_conflicting_request_reject"
        ]
        self.assertEqual({row["source"] for row in exclusions}, {"base", "block"})
        self.assertEqual(len(exclusions), 2)
        self.assertTrue(all(row["preserved_response_rule"] == response_rule
                            for row in exclusions))

    def test_tiantianjijin_start_image_keeps_request_reject_when_response_rule_is_absent(self):
        matcher = r"^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg"
        base_reject = matcher + " reject"
        base = "[Rewrite]\n" + base_reject + "\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        output = self.run_merge(base, extra)
        self.assertIn(base_reject, output)

    def test_tiantianjijin_start_image_action_drift_fails_closed(self):
        matcher = r"^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg"
        base = "[Rewrite]\n" + matcher + " reject\n[MITM]\nhostname = \n"
        changed_block = (
            r"request if ${url} ~= /^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg/ "
            r"then reject-dict"
        )
        extra = "[Rewrite]\n" + changed_block + "\n[MITM]\nhostname = \n"
        response_rule = matcher + " response-body-json-jq '.datas = []'"
        apps_files = {
            "tiantianjijin_splash_ad_block.plugin": (
                "[Rewrite]\n" + response_rule + "\n[MITM]\nhostname = \n"
            )
        }
        message = self.run_merge(
            base, extra, apps_files=apps_files, expect_failure=True
        )
        self.assertIn("天天基金 GetAppStartImg 请求动作发生变化", message)

    def test_tiantianjijin_start_image_response_rule_drift_fails_closed(self):
        matcher = r"^https?:\/\/appactive\.1234567\.com\.cn\/AppoperationApi\/OperationService\/GetAppStartImg"
        base = "[Rewrite]\n" + matcher + " reject\n[MITM]\nhostname = \n"
        extra = "[Rewrite]\n[MITM]\nhostname = \n"
        changed_response = matcher + " response-body-json-jq '.datas = {}'"
        apps_files = {
            "tiantianjijin_splash_ad_block.plugin": (
                "[Rewrite]\n" + changed_response + "\n[MITM]\nhostname = \n"
            )
        }
        message = self.run_merge(
            base, extra, apps_files=apps_files, expect_failure=True
        )
        self.assertIn("Thelong 天天基金 GetAppStartImg 响应规则发生变化", message)



    def test_bestv_advertising_v2_requires_endpoint_path_boundary(self):
        source_line = (
            r"request if ${url} ~= /^https:\/\/bp-api\.bestv\.com\.cn\/cms\/api\/free\/open\/advertisingV2/ then reject_dict(200)"
        )
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra = (
            "[Rewrite]\n# > 看东方（百视TV）\n"
            "# hostname = bp-api.bestv.com.cn, bp-api.bestv.cn\n"
            + source_line + "\n[MITM]\nhostname = \n"
        )
        output, provenance = self.run_merge(base, extra, return_provenance=True)
        line = next(line for line in output.splitlines() if "advertisingV2" in line)
        matcher = re.compile(line.split(" ~= ", 1)[1].split(" then ", 1)[0].strip().strip("/"))
        for url in (
            "https://bp-api.bestv.com.cn/cms/api/free/open/advertisingV2",
            "https://bp-api.bestv.com.cn/cms/api/free/open/advertisingV2?channel=home",
            "https://bp-api.bestv.com.cn/cms/api/free/open/advertisingV2/extra",
        ):
            with self.subTest(url=url):
                self.assertRegex(url, matcher)
        for url in (
            "https://bp-api.bestv.com.cn/cms/api/free/open/advertisingV2Extra",
            "https://bp-api.bestv.com.cn/cms/api/free/open/advertisingV20",
            "https://bp-api.bestvXcom.cn/cms/api/free/open/advertisingV2",
            "https://bp-api.bestv.cn/cms/api/free/open/advertisingV2",
        ):
            with self.subTest(url=url):
                self.assertNotRegex(url, matcher)
        self.assertTrue(line.endswith("then reject_dict(200)"))
        changes = [
            item for item in provenance["scope_adjustments"]
            if item.get("target") == "看东方（百视TV）advertisingV2 开屏接口路径边界"
        ]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source"], "blockAdsV2")
        self.assertEqual(changes[0]["original_line"], source_line)
        self.assertEqual(changes[0]["output_line"], line)

    def test_bestv_advertising_v2_guard_fails_closed_on_action_or_path_drift(self):
        base = "[Rewrite]\n[MITM]\nhostname = \n"
        extra_action = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https:\/\/bp-api\.bestv\.com\.cn\/cms\/api\/free\/open\/advertisingV2/ then reject(404)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_action, expect_failure=True)
        self.assertIn("看东方 advertisingV2 动作已变化", output)

        extra_path = (
            "[Rewrite]\n"
            + r"request if ${url} ~= /^https:\/\/bp-api\.bestv\.com\.cn\/cms\/api\/free\/open\/advertisingV2.*/ then reject_dict(200)"
            + "\n[MITM]\nhostname = \n"
        )
        output = self.run_merge(base, extra_path, expect_failure=True)
        self.assertIn("看东方 advertisingV2 matcher 已变化", output)



if __name__ == "__main__":
    unittest.main()
