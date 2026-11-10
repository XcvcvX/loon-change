#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

from source_guard import (
    validate_source, validate_rstore_rewrite, validate_filter,
    validate_blockv2, validate_myblockads, check_clones, REQUIRED_ZMJDE,
)


class SourceGuardTests(unittest.TestCase):
    def test_rejects_html_error_page(self):
        with self.assertRaisesRegex(ValueError, "HTML"):
            validate_source("<!doctype html><html>error</html>" + " " * 300,
                            "fixture", min_bytes=100)

    def test_rejects_truncated_payload(self):
        with self.assertRaisesRegex(ValueError, "过小"):
            validate_source("[Rewrite]\nreject", "fixture", min_bytes=100)

    def test_rstore_rewrite_requires_real_rule_volume(self):
        text = "hostname = ads.example.com\n" + "\n".join(
            "^https://ads.example.com/%d url reject" % i for i in range(20))
        self.assertEqual(validate_rstore_rewrite(text)["url_rules"], 20)

    def test_filter_requires_parseable_rule_volume(self):
        text = "\n".join("host,ads%d.example.com,reject" % i for i in range(20))
        self.assertEqual(validate_filter(text)["rules"], 20)

    def test_filter_rejects_unconvertible_rows_even_when_csv_volume_is_high(self):
        text = "\n".join("unknown,ads%d.example.com,allow" % i for i in range(20))
        with self.assertRaisesRegex(ValueError, "可转换规则仅 0 条"):
            validate_filter(text)

    def test_fetch_validated_discards_invalid_response_and_tries_next(self):
        from source_guard import fetch_validated
        responses = {
            "bad": "<!doctype html><html>error</html>" + " " * 300,
            "good": "# " + "x" * 120 + "\\n" + "\\n".join(
                "^https://ads.example.com/%d url reject" % i for i in range(20))
                + "\\nhostname = ads.example.com\\n",
        }
        data, url, stats = fetch_validated(
            ["bad", "good"], lambda key: responses[key],
            lambda value: validate_rstore_rewrite(value), "fixture")
        self.assertEqual(url, "good")
        self.assertEqual(stats["url_rules"], 20)
        self.assertTrue(data.startswith("#"))

    def test_blockv2_requires_sections_and_rules(self):
        text = "[Rewrite]\n" + "\n".join("^https://a.example.com/%d reject" % i for i in range(5))
        text += "\n[MITM]\nhostname = a.example.com\n# " + "x" * 150
        self.assertEqual(validate_blockv2(text)["rule_entries"], 5)

    def test_myblockads_requires_rewrite_content(self):
        text = "[Rewrite]\n" + "\n".join("^https://a.example.com/%d reject" % i for i in range(5)) + "\n# " + "x" * 150
        self.assertEqual(validate_myblockads(text)["rule_entries"], 5)

    def test_clone_preflight_requires_all_expected_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tl, ao, zm, qx = (root / n for n in ("tl", "ao", "zm", "qx.conf"))
            tl.mkdir(); ao.mkdir(); (ao / "plugins").mkdir(); zm.mkdir(); (zm / "Plugin").mkdir()
            rule_fixture = "[Rewrite]\n" + "\n".join("^https://ads.example.com/%d reject" % i for i in range(10)) + "\n"
            (tl / "sample_ad_block.plugin").write_text(rule_fixture, encoding="utf-8")
            (ao / "plugins" / "sample.plugin").write_text(rule_fixture, encoding="utf-8")
            for name in REQUIRED_ZMJDE:
                (zm / "Plugin" / name).write_text(rule_fixture, encoding="utf-8")
            qx.write_text("hostname = ads.example.com\n^https://ads.example.com/ad url reject\n# " + "x" * 120, encoding="utf-8")
            report = check_clones(str(tl), str(ao), str(zm), str(qx))
            self.assertEqual(report["zmjde"]["required_plugins"], len(REQUIRED_ZMJDE))

            bad = tl / "broken_ad_block.plugin"
            bad.write_text("<!doctype html><html>rate limited</html>" + " " * 300,
                           encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTML"):
                check_clones(str(tl), str(ao), str(zm), str(qx))
            bad.unlink()

            (zm / "Plugin" / REQUIRED_ZMJDE[0]).write_text(
                "[Rewrite]\\n# empty plugin\\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "未发现有效"):
                check_clones(str(tl), str(ao), str(zm), str(qx))
            (zm / "Plugin" / REQUIRED_ZMJDE[0]).write_text(rule_fixture, encoding="utf-8")
            previous = root / "previous-report.json"
            previous.write_text(json.dumps({
                "thelongdarkorg": {"rule_lines": 100},
                "aoomee": {"rule_lines": 100},
                "zmjde": {"rule_lines": 100},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "下降超过 60%"):
                check_clones(str(tl), str(ao), str(zm), str(qx), str(previous))


if __name__ == "__main__":
    unittest.main()
