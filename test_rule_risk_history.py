#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from rule_risk_history import build_risk


class RuleRiskHistoryTests(unittest.TestCase):
    def setUp(self):
        self.health = {
            "status": "pass", "average_source_reliability_score": 100,
            "source_scores": {"alpha": {"score": 100}, "weak": {"score": 55}},
            "warnings": [], "blockers": [],
        }
        self.source_report = {}
        self.diff = {
            "current_upstream_revisions": {"alpha": {"commit": "a" * 40}},
            "upstream_revision_changes": [],
            "sections": {
                "rewrite": {
                    "added": [{"line": "new", "sources": ["alpha"]}],
                    "removed": [{"line": "old", "sources": ["alpha"]}],
                    "action_changed": [{
                        "before": {"line": "before", "sources": ["alpha"]},
                        "after": {"line": "after", "sources": ["alpha"]},
                    }],
                },
                "script": {"added": [], "removed": [], "action_changed": []},
                "rule": {"added": [], "removed": [], "action_changed": []},
            },
        }

    def test_additions_medium_removals_and_action_changes_high(self):
        risk, _ = build_risk(self.diff, self.health, self.source_report, {}, "1")
        self.assertEqual(risk["overall_risk"], "high")
        self.assertEqual(risk["risk_counts"], {"high": 2, "medium": 1, "low": 0})

    def test_proven_semantic_duplicate_removal_is_low_risk_only_with_exact_coverage(self):
        diff = {
            "sections": {
                "rewrite": {
                    "removed": [{
                        "line": "^https://a.example/ad reject-dict",
                        "sources": ["alpha"],
                    }]
                }
            },
            "current_upstream_revisions": {},
            "upstream_revision_changes": [],
        }
        provenance = {
            "rewrite_exclusions": [{
                "status": "excluded_semantic_duplicate",
                "source_raw_line": "^https://a.example/ad reject-dict",
                "covered_by": "^https://a.example/(?:ad|promo)",
                "reason": "same matcher and action",
            }]
        }
        risk, _ = build_risk(diff, self.health, {}, {}, "semantic", provenance)
        self.assertEqual(risk["risk_counts"], {"high": 0, "medium": 0, "low": 1})
        self.assertIn("covered_by", risk["events"][0]["semantic_duplicate_coverage"])

        # Similar wording or a different source line must not be enough.
        provenance["rewrite_exclusions"][0]["source_raw_line"] = "^https://a.example/other reject-dict"
        risk, _ = build_risk(diff, self.health, {}, {}, "uncovered", provenance)
        self.assertEqual(risk["risk_counts"]["high"], 1)

    def test_low_source_score_escalates_addition(self):
        self.diff["sections"]["rewrite"]["removed"] = []
        self.diff["sections"]["rewrite"]["action_changed"] = []
        self.diff["sections"]["rewrite"]["added"][0]["sources"] = ["weak"]
        risk, _ = build_risk(self.diff, self.health, self.source_report, {}, "2")
        self.assertEqual(risk["risk_counts"]["high"], 1)

    def test_history_is_bounded_to_thirty_snapshots(self):
        previous = {"snapshots": [{"run_id": str(i)} for i in range(35)]}
        _, history = build_risk(self.diff, self.health, self.source_report, previous, "new")
        self.assertEqual(len(history["snapshots"]), 30)
        self.assertEqual(history["snapshots"][-1]["run_id"], "new")

    def test_no_changes_is_low_risk(self):
        empty = {"sections": {}, "current_upstream_revisions": {},
                 "upstream_revision_changes": []}
        risk, history = build_risk(empty, self.health, self.source_report, {}, "3")
        self.assertEqual(risk["overall_risk"], "low")
        self.assertEqual(risk["risk_counts"]["high"], 0)
        self.assertEqual(len(history["snapshots"]), 1)

    def test_same_snapshot_is_not_duplicated(self):
        empty = {"sections": {}, "current_upstream_revisions": {},
                 "upstream_revision_changes": []}
        _, first = build_risk(empty, self.health, self.source_report, {}, "4")
        _, second = build_risk(empty, self.health, self.source_report, first, "4")
        self.assertEqual(len(second["snapshots"]), 1)


if __name__ == "__main__":
    unittest.main()
