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
        phase_only = audit_rewrite_overlaps([rows[0], rows[2]])
        self.assertTrue(any(x['overlap_type'] == 'cross_phase_only'
                            for x in phase_only['rewrite_overlap_candidate_groups']))

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


    def test_rewrite_overlap_legacy_phase_is_ambiguous(self):
        from deep_audit import audit_rewrite_overlaps
        rows = [
            (1, r'^https:\/\/api\.example\.com\/ad header-add X-Test 1'),
            (2, r'request if %URL% ~= /^https:\/\/api\.example\.com\/ad/ then reject(404)'),
        ]
        report = audit_rewrite_overlaps([(n, line.replace("%URL%", "$"+"{url}")) for n, line in rows])
        self.assertTrue(any(x['overlap_type'] == 'phase_ambiguous_overlap'
                            for x in report['rewrite_overlap_candidate_groups']))


    def test_mitm_script_coverage_exact_wildcard_and_negative(self):
        from deep_audit import audit_mitm_script_coverage
        rewrite = [
            (10, r'request if %URL% ~= /^https:\/\/api\.covered\.test\/ad/ then reject(404)'),
            (11, r'request if %URL% ~= /^https:\/\/missing\.test\/ad/ then reject(404)'),
            (12, r'request if %URL% ~= /^https:\/\/excluded\.test\/ad/ then reject(404)'),
            (13, r'request if %URL% ~= /^http:\/\/plain\.test\/ad/ then reject(404)'),
            (14, r'request if %URL% ~= /^https:\/\/192\.0\.2\.1\/ad/ then reject(404)'),
        ]
        scripts = [
            (20, r'http-response ^https:\/\/script\.covered\.test\/api script-path=https://cdn.test/a.js'),
            (21, r'http-response ^https:\/\/m\d\.dynamic\.test\/api script-path=https://cdn.test/b.js'),
        ]
        mitm = [(30, 'hostname = *.covered.test, -excluded.test')]
        rows = [(n, line.replace('%URL%', chr(36) + '{url}')) for n, line in rewrite]
        report = audit_mitm_script_coverage(rows, scripts, mitm)
        summary = report['mitm_script_coverage_summary']
        self.assertEqual(summary['covered_references'], 2)
        self.assertEqual(summary['missing_mitm_references'], 1)
        self.assertEqual(summary['negative_excluded_references'], 1)
        self.assertEqual(summary['ambiguous_references'], 1)
        self.assertEqual(summary['dynamic_suffix_references'], 1)
        self.assertEqual(summary['http_only_references'], 1)
        self.assertEqual(summary['ip_literal_references'], 1)
        self.assertEqual(report['mitm_ambiguous_rewrite_script_references'][0]['reason'],
                         'regex_host_suffix_without_matching_wildcard')
        self.assertEqual(report['mitm_missing_rewrite_script_coverage'][0]['host'],
                         'missing.test')
        self.assertEqual(report['mitm_negative_excluded_rewrite_script_coverage'][0]['host'],
                         'excluded.test')

    def test_mitm_script_coverage_in_deep_audit_report(self):
        fixture = '''[Rewrite]
request if %URL% ~= /^https:\\/\\/api\\.example\\.test\\/ad/ then reject(404)
[Script]
http-response ^https:\\/\\/api\\.example\\.test\\/v1 script-path=https://cdn.example.test/a.js
[MITM]
hostname = *.example.test
'''
        fixture = fixture.replace('%URL%', chr(36) + '{url}')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertIn('mitm_missing_rewrite_script_coverage', report)
        self.assertEqual(report['summary']['missing_mitm_references'], 0)
        self.assertEqual(report['summary']['covered_references'], 2)


    def test_mitm_necessity_classification_is_conservative(self):
        from deep_audit import audit_mitm_script_coverage, audit_mitm_necessity
        rewrite = [
            (10, r'request if ${url} ~= /^https:\/\/api\.used\.test\/ad/ then reject(404)'),
            (11, r'request if ${url} ~= /^https:\/\/api\.used\.test\/config/ then reject(404)'),
            (12, r'request if ${url} ~= /^https:\/\/missing\.test\/ad/ then reject(404)'),
            (13, r'request if ${url} ~= /^http:\/\/plain\.test\/ad/ then reject(404)'),
            (14, r'request if ${url} ~= /^https:\/\/192\.0\.2\.9\/ad/ then reject(404)'),
        ]
        scripts = [
            (20, r'http-response ^https:\/\/api\.used\.test\/v1 script-path=https://cdn.test/a.js'),
            (21, 'generic script-path=https://cdn.test/generic.js'),
            (22, r'http-request ^https:\/\/m\\d\.dynamic\.test\/v1 script-path=https://cdn.test/d.js'),
        ]
        mitm = [
            (30, 'hostname = api.used.test, unused.test, *.wild.test, *.dynamic.test'),
            (31, 'hostname = -blocked.test'),
        ]
        coverage = audit_mitm_script_coverage(rewrite, scripts, mitm)
        report = audit_mitm_necessity(mitm, coverage, rewrite, scripts)
        by_host = {x['host']: x for x in report['mitm_necessity_classifications']}
        self.assertEqual(by_host['api.used.test']['classification'],
                         'referenced_by_literal_trigger')
        self.assertEqual(by_host['unused.test']['classification'],
                         'no_literal_reference_candidate')
        self.assertEqual(by_host['*.wild.test']['classification'],
                         'insufficient_dynamic_or_generic_evidence')
        self.assertEqual(by_host['*.dynamic.test']['classification'],
                         'referenced_by_literal_trigger')
        self.assertEqual(by_host['blocked.test']['classification'], 'negative_exclusion')
        self.assertEqual(report['mitm_necessity_summary']['https_literal_missing'], 1)
        self.assertEqual(report['mitm_necessity_summary']['scheme_or_matcher_ambiguous_missing'], 0)
        self.assertIn('不等于', report['mitm_necessity_safety_note'])

    def test_mitm_necessity_marks_embedded_host_as_indirect_not_required(self):
        from deep_audit import audit_mitm_script_coverage, audit_mitm_necessity
        rewrite = [(10, r'request if ${url} ~= /^https:\/\/api\.used\.test\/ad/ then reject(404)')]
        scripts = [(20, r'http-response ^https:\/\/other\.test script-path=https://cdn.only.test/a.js')]
        mitm = [(30, 'hostname = cdn.only.test, api.used.test')]
        coverage = audit_mitm_script_coverage(rewrite, scripts, mitm)
        report = audit_mitm_necessity(mitm, coverage, rewrite, scripts)
        by_host = {x['host']: x for x in report['mitm_necessity_classifications']}
        self.assertEqual(by_host['cdn.only.test']['classification'],
                         'possible_indirect_or_embedded_reference')
        self.assertEqual(by_host['api.used.test']['classification'],
                         'referenced_by_literal_trigger')



    def test_mitm_host_extractor_handles_ports_and_stable_regex_suffixes(self):
        from deep_audit import extract_literal_matcher_host

        cases = [
            (r'^https?:\/\/gateway\.example\.com(:\d+)?\/app',
             ('gateway.example.com', 'literal_host')),
            (r'^https?:\/\/gateway\.example\.com(?::443)?\/app',
             ('gateway.example.com', 'literal_host')),
            (r'^https?:\/\/gateway\.example\.com\:\w+\/app',
             ('gateway.example.com', 'literal_host')),
            (r'^https?:\/\/(?:api|www)\.example\.com\/ad',
             ('example.com', 'regex_host_suffix')),
            (r'^https?:\/\/(?:www\.)?youtube\.com\/api',
             ('youtube.com', 'regex_host_suffix')),
            (r'^https?:\/\/(?:[A-Za-z0-9-]+\.)*chelaile\.net\.cn\/ad',
             ('chelaile.net.cn', 'regex_host_suffix')),
            (r'^https?:\/\/api\d?\.futunn\.com\/ad',
             ('futunn.com', 'regex_host_suffix')),
            (r'^https?:\/\/(?:api|www).example\.com\/ad',
             (None, 'regex_host_authority')),
            (r'^https?:\/\/(?:a|b)\.com\.cn\/ad',
             (None, 'regex_host_authority')),
        ]
        for matcher, expected in cases:
            with self.subTest(matcher=matcher):
                self.assertEqual(extract_literal_matcher_host(matcher), expected)

    def test_mitm_host_extractor_keeps_complex_host_patterns_ambiguous(self):
        from deep_audit import extract_literal_matcher_host

        # A regex alternative inside a label with no stable domain suffix must
        # remain ambiguous; do not infer a broad public-suffix MITM entry.
        matcher = r'^https?:\/\/mrobot\.(?:pcauto|pconline)\.com\.cn\/ad'
        self.assertEqual(extract_literal_matcher_host(matcher),
                         (None, 'regex_host_authority'))

if __name__ == '__main__':
    unittest.main()
