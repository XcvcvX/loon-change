#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from source_health_guard import build_health, provenance_coverage


def sources():
    return {
        "Amap": {"bytes": 1000, "entries": 40, "upstream_commit": "a" * 40,
                 "assets": {str(i): {"sha256": "b" * 64} for i in range(4)}},
        "thelongdarkorg": {"bytes": 1000, "rule_lines": 100, "commit": "c" * 40},
        "aoomee": {"bytes": 1000, "rule_lines": 100, "commit": "d" * 40},
        "zmjde": {"bytes": 1000, "rule_lines": 100, "commit": "e" * 40},
        "GuaZiVideoAds": {"bytes": 1000, "entries": 10},
    }


def provenance(count=100):
    return {
        "summary": {"rewrite_output_entries": count, "script_output_entries": 0,
                    "rule_output_entries": 0},
        "rewrite": [{"sources": [{"source": "base"}], "output_line": "line"} for _ in range(count)],
        "script": [],
        "rule_events": [],
    }


def diff(added=0, removed=0, changed=0):
    return {"summary": {
        "rewrite": {"added": added, "removed": removed, "action_changed": changed},
        "script": {"added": 0, "removed": 0, "action_changed": 0},
        "rule": {"added": 0, "removed": 0, "action_changed": 0},
    }}


class SourceHealthGuardTests(unittest.TestCase):
    def test_full_source_evidence_passes(self):
        report = build_health(sources(), sources(), provenance(), provenance(), diff())
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["deployment_allowed"])
        self.assertEqual(report["provenance_coverage"]["coverage_percent"], 100.0)

    def test_missing_source_blocks(self):
        current = sources()
        del current["aoomee"]
        with self.assertRaisesRegex(ValueError, "missing required sources"):
            build_health(sources(), current, provenance(), provenance(), diff())

    def test_cloned_plugin_sources_use_rule_lines_without_bytes(self):
        current = sources()
        for name in ("thelongdarkorg", "aoomee", "zmjde"):
            current[name].pop("bytes")
        report = build_health(sources(), current, provenance(), provenance(), diff())
        self.assertTrue(report["deployment_allowed"])
        self.assertEqual(report["source_scores"]["aoomee"]["evidence"]["content_volume"],
                         "present_rule_lines")

    def test_unattributed_provenance_blocks(self):
        current = provenance()
        current["rewrite"][0]["sources"] = []
        report = build_health(sources(), sources(), provenance(), current, diff())
        self.assertFalse(report["deployment_allowed"])
        self.assertIn("source attribution", " ".join(report["blockers"]))

    def test_large_rule_removal_holds_deployment(self):
        report = build_health(sources(), sources(), provenance(), provenance(60),
                              diff(removed=30))
        self.assertEqual(report["status"], "hold")
        self.assertFalse(report["deployment_allowed"])

    def test_action_change_spike_holds_deployment(self):
        report = build_health(sources(), sources(), provenance(), provenance(),
                              diff(changed=11))
        self.assertFalse(report["deployment_allowed"])

    def test_addition_spike_is_review_not_automatic_hold(self):
        report = build_health(sources(), sources(), provenance(), provenance(),
                              diff(added=110))
        self.assertEqual(report["status"], "review")
        self.assertTrue(report["deployment_allowed"])

    def test_coverage_counts_included_rule_events_only(self):
        p = provenance()
        p["rule_events"] = [{"status": "included", "source": "filter"},
                            {"status": "duplicate"}]
        self.assertEqual(provenance_coverage(p)["entries"], 101)


if __name__ == "__main__":
    unittest.main()
