#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from audit_plugin import audit_plugin, extract_script_url, is_global_udp_443, wildcard_covers


class RuntimeAuditTests(unittest.TestCase):
    def test_global_udp_443_detection(self):
        self.assertTrue(is_global_udp_443(
            'AND,((PROTOCOL,UDP),(DEST-PORT,443)),REJECT'))
        self.assertFalse(is_global_udp_443(
            'AND,((DOMAIN-SUFFIX,example.com),(PROTOCOL,UDP),(DEST-PORT,443)),REJECT'))

    def test_wildcard_covers_subdomains_not_apex(self):
        self.assertTrue(wildcard_covers('api.a.example.com', '*.example.com'))
        self.assertFalse(wildcard_covers('example.com', '*.example.com'))
        self.assertFalse(wildcard_covers('example.net', '*.example.com'))

    def test_extract_script_url_with_arguments(self):
        self.assertEqual(
            extract_script_url('response if ${url} ~= /x/ then script("https://cdn.example/a.js", {x=1})'),
            'https://cdn.example/a.js')
        self.assertEqual(
            extract_script_url('http-response ^https://a.example script-path = https://cdn.example/b.js,tag=A'),
            'https://cdn.example/b.js')

    def test_audit_report_is_read_only_and_counts_candidates(self):
        fixture = '''[Rule]
AND,((PROTOCOL,UDP),(DEST-PORT,443)),REJECT
AND,((DOMAIN-SUFFIX,example.com),(PROTOCOL,UDP),(DEST-PORT,443)),REJECT
[Script]
response if ${url} ~= /x/ then script("https://cdn.example/a.js", {x=1})
http-response ^https://a.example script-path=https://cdn.example/b.js,tag=A
[MITM]
hostname = *.example.com, api.example.com, example.net
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_plugin(path)
        self.assertEqual(report['summary']['global_udp_443_rules'], 1)
        self.assertEqual(report['summary']['mitm_exact_hosts_covered_by_wildcards'], 1)
        self.assertEqual(report['summary']['unique_remote_script_urls'], 2)
        self.assertEqual(report['summary']['script_path_lines'], 1)
        self.assertEqual(report['summary']['script_entries_without_script_action'], 1)
        self.assertEqual(report['summary']['script_lines_without_remote_url'], 1)
        self.assertEqual(report['mitm_wildcard_overlap_candidates'], ['api.example.com'])


if __name__ == '__main__':
    unittest.main()
