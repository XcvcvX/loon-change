import unittest

from compare_rule_provenance import build_diff


def rewrite(line, matcher, action):
    return {
        "output_line": line,
        "canonical_key": repr(("guarded", matcher, action)),
        "sources": [{"source": "fixture"}],
    }


def rule(line, source="fixture"):
    return {"status": "included", "output_line": line, "source": source}


def report(rewrite_rows=None, script_rows=None, rule_rows=None, revisions=None):
    return {
        "schema_version": 1,
        "upstream_revisions": revisions or {},
        "rewrite": rewrite_rows or [],
        "script": script_rows or [],
        "rule_events": rule_rows or [],
    }


class RuleProvenanceDiffTests(unittest.TestCase):
    def test_detects_added_and_removed_rewrite_and_script(self):
        old = report(
            [rewrite("^https://a.example/ad reject", "^https://a.example/ad", ("REJECT",))],
            [rewrite("http-response ^https://b.example script-path=x.js", "^https://b.example", ("script-path=x.js",))],
        )
        new = report(
            [rewrite("^https://c.example/ad reject", "^https://c.example/ad", ("REJECT",))],
        )
        result = build_diff(old, new)
        self.assertEqual(result["summary"]["rewrite"]["added"], 1)
        self.assertEqual(result["summary"]["rewrite"]["removed"], 1)
        self.assertEqual(result["summary"]["script"]["removed"], 1)

    def test_detects_unique_rewrite_action_change(self):
        old = report([rewrite("^https://a.example/ad reject", "^https://a.example/ad", ("REJECT",))])
        new = report([rewrite("^https://a.example/ad reject-200", "^https://a.example/ad", ("REJECT-200",))])
        result = build_diff(old, new)
        self.assertEqual(result["summary"]["rewrite"]["action_changed"], 1)
        self.assertEqual(result["summary"]["rewrite"]["added"], 0)
        self.assertEqual(result["summary"]["rewrite"]["removed"], 0)

    def test_detects_rule_action_change(self):
        old = report(rule_rows=[rule("DOMAIN,ads.example.com,REJECT")])
        new = report(rule_rows=[rule("DOMAIN,ads.example.com,DIRECT")])
        result = build_diff(old, new)
        self.assertEqual(result["summary"]["rule"]["action_changed"], 1)
        self.assertEqual(result["sections"]["rule"]["action_changed"][0]["before"]["line"], "DOMAIN,ads.example.com,REJECT")

    def test_ambiguous_multi_action_matcher_is_not_guessed(self):
        old = report([rewrite("one", "^https://a.example", ("REJECT",))])
        new = report([
            rewrite("one", "^https://a.example", ("REJECT",)),
            rewrite("two", "^https://a.example", ("reject-dict",)),
        ])
        result = build_diff(old, new)
        self.assertEqual(result["summary"]["rewrite"]["action_changed"], 0)
        self.assertEqual(result["summary"]["rewrite"]["added"], 1)

    def test_ignores_non_included_rule_events_and_tracks_upstream_revisions(self):
        old = report(rule_rows=[
            rule("DOMAIN,ads.example.com,REJECT"),
            {"status": "duplicate_exact", "output_line": "DOMAIN,ads.example.com,REJECT", "source": "other"},
        ], revisions={"sourceA": {"commit": "abc"}})
        new = report(rule_rows=[rule("DOMAIN,ads.example.com,REJECT")], revisions={"sourceA": {"commit": "def"}})
        result = build_diff(old, new)
        self.assertEqual(result["summary"]["total_changes"], 0)
        self.assertEqual(result["upstream_revision_changes"][0]["current_commit"], "def")


if __name__ == "__main__":
    unittest.main()
