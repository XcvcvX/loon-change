#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from audit_runtime import audit_runtime, extract_regex_and_action, is_broad_reject


class RuntimeDeepAuditTests(unittest.TestCase):
    def test_broad_reject_requires_reject_action(self):
        self.assertTrue(is_broad_reject('.*', 'reject'))
        self.assertFalse(is_broad_reject('.*', '302'))
        self.assertFalse(is_broad_reject('^https://api.example.com/ad/', 'reject'))

    def test_extract_regex_action(self):
        self.assertEqual(
            extract_regex_and_action('url reject'),
            ('url', 'reject'))
        self.assertEqual(
            extract_regex_and_action('request  https://x.test/ ~= /^https?:\\/\\/x\\.test\\/ad/ then reject(200)'),
            ('^https?://x\\.test\\/ad', 'then'))

    def test_read_only_report_flags_candidates_not_rules(self):
        fixture = '''[Rewrite]
.* reject
^https://api.example.com/ad/ reject
^https://api.example.com/ad/ reject-200
[Script]
http-request ^https://api.example.com/ad script-path=https://cdn.example/a.js
http-request ^https://api.example.com/ad script-path=https://cdn.example/a.js
[MITM]
hostname = api.example.com, orphan.example.net
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_runtime(path)
        self.assertEqual(report['summary']['broad_reject_candidates'], 1)
        self.assertEqual(report['summary']['rewrite_conflict_patterns'], 1)
        self.assertEqual(report['summary']['duplicate_script_trigger_groups'], 1)
        self.assertEqual(report['mitm_without_literal_guard_candidates'], [
            {'line': 9, 'host': 'orphan.example.net'}
        ])
        self.assertTrue(any('不会修改' in note for note in report['notes']))


if __name__ == '__main__':
    unittest.main()
