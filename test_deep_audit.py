#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from deep_audit import audit_deep, broad_reasons, parse_rewrite


class DeepAuditTests(unittest.TestCase):
    def test_modern_rewrite_and_conflicting_actions(self):
        line = r'request if \${url} ~= /^https:\/\/api\.example\.com\/ad/ then reject'
        self.assertEqual(parse_rewrite(line)[0], 'request')
        fixture = '''[Rewrite]
request if \${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad/ then reject
request if \${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad/ then reject-dict
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['rewrite_action_conflict_groups'], 1)
        self.assertEqual(report['summary']['rewrite_duplicate_matcher_groups'], 1)

    def test_broad_match_candidate(self):
        self.assertTrue(broad_reasons('^https?://'))
        self.assertFalse(broad_reasons(r'^https://api\.example\.com/ad'))

    def test_mitm_and_script_candidates(self):
        fixture = '''[Rewrite]
^https://api.example.com/ad reject
[Script]
http-request ^https://api.example.com script-path=https://cdn.example/a.js
http-response ^https://api.example.com script-path=https://cdn.example/a.js
generic script-path=https://cdn.example/generic.js
[MITM]
hostname = *.example.com, api.example.com, unused.test
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['mitm_exact_hosts_covered_by_wildcards'], 1)
        self.assertEqual(report['summary']['script_urls_reused'], 1)
        self.assertIn('unused.test', report['mitm_without_obvious_literal_guard'])
        self.assertEqual(report['summary']['script_generic_trigger_candidates'], 1)
        self.assertTrue(any('只读' in x for x in report['safety_notes']))


if __name__ == '__main__':
    unittest.main()
