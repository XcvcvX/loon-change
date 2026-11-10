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
