#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from deep_audit import audit_deep, broad_reasons, parse_rewrite


class DeepAuditTests(unittest.TestCase):
    def test_modern_rewrite_and_conflicting_actions(self):
        line = r'request if ${url} ~= /^https:\/\/api\.example\.com\/ad/ then reject'
        self.assertEqual(parse_rewrite(line)[0], 'request')
        fixture = '''[Rewrite]
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad/ then reject
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad/ then reject-dict
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

    def test_rewrite_scope_normalizes_escaped_domains(self):
        from deep_audit import classify_rewrite_scope

        escaped_domain = r'^https?:\\/\\/api\\.example\\.com\\/ad\\/.*'
        wildcard_subdomain = r'^https?:\\/\\/.*\\.xima.*\\.com\\/ad'
        path_wildcard = r'^https?:\\/\\/api\\.example\\.com\\/assets\\/.*'
        self.assertFalse(broad_reasons(escaped_domain))
        self.assertEqual(classify_rewrite_scope(escaped_domain), 'domain_scoped_path_wildcard')
        self.assertEqual(classify_rewrite_scope(wildcard_subdomain),
                         'domain_scoped_subdomain_wildcard')
        self.assertEqual(classify_rewrite_scope(path_wildcard), 'domain_scoped_path_wildcard')
        self.assertTrue(broad_reasons('^https?://'))
        self.assertEqual(classify_rewrite_scope('^https?://'), 'url_without_domain')
        self.assertFalse(broad_reasons(r'^https?:\/\/ap\.(dongqiudi|dongdianqiu)\.com\/ad'))
        self.assertEqual(classify_rewrite_scope(r'^https?:\/\/ap\.(dongqiudi|dongdianqiu)\.com\/ad'),
                         'domain_scoped')
        self.assertFalse(broad_reasons(r'^https?:\/\/101\.91\.69\.26:8080\/ad'))
        self.assertEqual(classify_rewrite_scope(r'^https?:\/\/101\.91\.69\.26:8080\/ad'),
                         'domain_scoped')

        wildcard_tld = r'^https?:\/\/.*\.boohee\.(?:cn|com).*\/ad'
        class_slash = r'^https?:\/\/[^\s/]*\.pangle\.cn\/api\/ad'
        self.assertFalse(broad_reasons(wildcard_tld))
        self.assertEqual(classify_rewrite_scope(wildcard_tld),
                         'domain_scoped_subdomain_wildcard')
        self.assertFalse(broad_reasons(class_slash))
        self.assertEqual(classify_rewrite_scope(class_slash),
                         'domain_scoped_subdomain_wildcard')

        fixture = r'''[Rewrite]
^https?:\/\/api\.example\.com\/ad\/.* reject
^https?:\/\/.*\.xima.*\.com\/ad reject
^https?:\/\/api\.example\.com\/assets\/.* reject
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'scope.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['rewrite_broad_candidates'], 0)
        self.assertEqual(report['summary']['rewrite_scope_counts'].get(
            'domain_scoped_subdomain_wildcard'), 1)
        self.assertEqual(report['summary']['rewrite_scope_review_candidates'], 3)

    def test_modern_rewrite_with_unescaped_slashes_alias_and_conditions(self):
        unescaped = r'request if ${url} ~= /http://ssp\.dzh\.com\.cn/v2api/adgroupjson/ then reject(404)'
        parsed = parse_rewrite(unescaped)
        self.assertEqual(parsed[0], 'request')
        self.assertEqual(parsed[1], r'http://ssp\.dzh\.com\.cn/v2api/adgroupjson')
        self.assertEqual(parsed[2], 'reject(404)')

        alias = r'request if ${url} ~= /http:\/\/api\.example\.com\/artist\/(.*)/ as m then redirect(302, "${m.1}")'
        parsed_alias = parse_rewrite(alias)
        self.assertEqual(parsed_alias[1], r'http:\/\/api\.example\.com\/artist\/(.*)')
        self.assertTrue(parsed_alias[2].startswith('redirect(302'))

        compound = r'request if ${url} ~= /https:\/\/api\.example\.com\/ad/i && ${request.method} == "POST" then reject_video(200)'
        parsed_compound = parse_rewrite(compound)
        self.assertEqual(parsed_compound[1], r'https:\/\/api\.example\.com\/ad')
        self.assertEqual(parsed_compound[2], 'reject_video(200)')

        numeric_legacy = r'https:\/\/api\.example\.com\/ad 302 https://example.com/data.json'
        self.assertEqual(parse_rewrite(numeric_legacy)[2], '302')

        fixture = "[Rewrite]\n" + "\n".join([unescaped, alias, compound, numeric_legacy]) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'modern.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['rewrite_entries'], 4)
        self.assertEqual(report['summary']['rewrite_unparsed'], 0)
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
