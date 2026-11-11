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
    def test_rewrite_action_semantic_classification(self):
        from deep_audit import classify_rewrite_action
        self.assertEqual(classify_rewrite_action('reject(404)')['families'], ['block'])
        self.assertEqual(classify_rewrite_action('response.json.delete("data.ad")')['families'],
                         ['response_json_rewrite'])
        self.assertEqual(classify_rewrite_action('response.body.mock_file("json", "https://x")')['families'],
                         ['response_mock'])
        self.assertEqual(classify_rewrite_action('redirect(302, "https://x")')['families'],
                         ['redirect'])

        fixture = '''[Rewrite]
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad/ then reject(404)
response if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/config/ then response.json.delete("data.ad") | response.json.replace("data.banner", [])
response if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/bootstrap/ then response.body.mock_file("json", "https://cdn.example/config.json", 200)
response if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/payload/ then response.body.replace(/ad/, "")
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/submit/ then request-body-replace-regex ad clean
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/artist/ then redirect(302, "https://example.com")
^https:\\/\\/api\\.example\\.com\\/header response-header-add X-Test 1
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'actions.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        counts = report['summary']['rewrite_action_family_counts']
        self.assertEqual(counts['block'], 1)
        self.assertEqual(counts['response_json_rewrite'], 1)
        self.assertEqual(counts['response_mock'], 1)
        self.assertEqual(counts['response_body_rewrite'], 1)
        self.assertEqual(counts['request_body_rewrite'], 1)
        self.assertEqual(counts['redirect'], 1)
        self.assertEqual(counts['header_rewrite'], 1)
        self.assertEqual(report['summary']['rewrite_action_semantic_review_candidates'], 6)
        self.assertEqual(report['summary']['rewrite_unknown_action_candidates'], 0)
        self.assertTrue(any(x['review_priority'] == 'high_review'
                            for x in report['rewrite_action_semantic_review_candidates']))
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


    def test_rewrite_overlap_cross_action_and_same_family(self):
        from deep_audit import audit_rewrite_overlaps
        rows = [
            (1, r'request if ${url} ~= /^https:\/\/api\.example\.com\/ad/ then reject(404)'),
            (2, r'request if ${url} ~= /^https:\/\/api\.example\.com\/.*/ then redirect(302, "https://example.com")'),
            (3, r'response if ${url} ~= /^https:\/\/api\.example\.com\/ad/ then response.json.delete("ad")'),
        ]
        report = audit_rewrite_overlaps(rows)
        self.assertGreaterEqual(report['rewrite_overlap_sampled_rules'], 3)
        self.assertTrue(any(x['overlap_type'] == 'cross_action_overlap'
                            for x in report['rewrite_overlap_candidate_groups']))
        self.assertTrue(any(x['overlap_type'] == 'cross_phase_only'
                            for x in report['rewrite_overlap_candidate_groups']))

    def test_rewrite_overlap_same_action_family(self):
        from deep_audit import audit_rewrite_overlaps
        rows = [
            (1, r'request if ${url} ~= /^https:\/\/api\.example\.com\/ad/ then reject(404)'),
            (2, r'request if ${url} ~= /^https:\/\/api\.example\.com\/.*/ then reject(200)'),
        ]
        report = audit_rewrite_overlaps(rows)
        self.assertTrue(any(x['overlap_type'] == 'likely_duplicate_overlap'
                            for x in report['rewrite_overlap_candidate_groups']))

    def test_rewrite_overlap_complex_pattern_is_skipped_and_sample_cap(self):
        from deep_audit import audit_rewrite_overlaps
        rows = [
            (1, r'request if ${url} ~= /^https:\/\/api\.example\.com\/(a+)+$/ then reject'),
            (2, r'request if ${url} ~= /^https:\/\/api\.example\.com\/ad/ then reject'),
            (3, r'request if ${url} ~= /^https:\/\/api\.example\.com\/.*/ then reject'),
        ]
        report = audit_rewrite_overlaps(rows, sample_cap=1)
        self.assertEqual(report['rewrite_overlap_sample_cap'], 1)
        self.assertEqual(report['rewrite_overlap_sampled_urls'], 1)
        self.assertEqual(report['rewrite_overlap_skipped_rules'], 1)
        self.assertEqual(report['rewrite_overlap_manual_review_candidates'][0]['reason'],
                         'nested_quantifier')


if __name__ == '__main__':
    unittest.main()
