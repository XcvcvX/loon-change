#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
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


    def test_legacy_rewrite_preserves_full_action_arguments_for_duplicate_analysis(self):
        fixture = '''[Rewrite]
^https:\\/\\/api\\.example\\.com\\/feed response-body-json-jq '.data |= map(select(.type == "card"))'
^https:\\/\\/api\\.example\\.com\\/feed response-body-json-jq '.data |= map(select(.id != "ad"))'
^https:\\/\\/api\\.example\\.com\\/feed reject-dict
^https:\\/\\/api\\.example\\.com\\/feed reject-dict
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'legacy-actions.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)

        group = report['rewrite_duplicate_matcher_groups'][0]
        self.assertEqual(len(group['entries']), 4)
        self.assertEqual(len(group['actions']), 3)
        self.assertEqual(len(group['exact_duplicate_actions']), 1)
        self.assertEqual(report['summary']['rewrite_exact_duplicate_action_groups'], 1)
        self.assertEqual(report['summary']['rewrite_action_conflict_groups'], 1)
        self.assertEqual(report['summary']['rewrite_cross_family_conflict_groups'], 1)
        self.assertTrue(any(action.startswith('response-body-json-jq ') for action in group['actions']))

    def test_duplicate_json_delete_paths_are_reported_without_modifying_rules(self):
        fixture = '''[Rewrite]
response if ${url} ~= /api.example.com/ then response.json.delete(["data.ad", "data.banner", "data.ad"])
response if ${url} ~= /api.example.com/ then response.json.delete(["data.one", "data.two"])
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'duplicate-delete-paths.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['rewrite_json_delete_duplicate_paths'], 1)
        finding = report['rewrite_json_delete_duplicate_paths'][0]
        self.assertEqual(finding['duplicate_paths'], [{'path': 'data.ad', 'count': 2}])
        self.assertEqual(finding['paths'], ['data.ad', 'data.banner', 'data.ad'])
        self.assertEqual(report['summary']['rewrite_entries'], 2)

    def test_duplicate_delete_path_audit_ignores_single_path_and_non_delete_actions(self):
        fixture = '''[Rewrite]
response if ${url} ~= /api.example.com/ then response.json.delete("data.ad")
response if ${url} ~= /api.example.com/ then response.json.jq("del(.data.ad)")
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'no-duplicate-delete-paths.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)
        self.assertEqual(report['summary']['rewrite_json_delete_duplicate_paths'], 0)
        self.assertEqual(report['rewrite_json_delete_duplicate_paths'], [])

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
        self.assertEqual(parse_rewrite(numeric_legacy)[2], '302 https://example.com/data.json')

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

    def test_mitm_coverage_distinguishes_shared_pinning_skips_from_real_gaps(self):
        from deep_audit import audit_mitm_script_coverage, audit_mitm_necessity
        rewrite = [
            (10, r'request if %URL% ~= /^https:\/\/openapi\.boc\.cn\/unlogin\/app\/cbsp\/query_ad_list/ then reject(200)'),
            (11, r'request if %URL% ~= /^https:\/\/pv\.elife\.icbc\.com\.cn\/OFSTPV\/utm\.gif/ then reject(200)'),
            (12, r'request if %URL% ~= /^https:\/\/missing\.example\/ad/ then reject(404)'),
            (13, r'request if %URL% ~= /^https:\/\/ios\.chat\.openai\.com\/public-api/ then reject-dict'),
        ]
        rows = [(n, line.replace('%URL%', chr(36) + '{url}')) for n, line in rewrite]
        coverage = audit_mitm_script_coverage(rows, [], [])
        summary = coverage['mitm_script_coverage_summary']
        self.assertEqual(summary['intentionally_skipped_references'], 3)
        self.assertEqual(summary['missing_mitm_references'], 1)
        skipped = coverage['mitm_intentionally_skipped_references']
        self.assertEqual({x['mitm_skip_domain'] for x in skipped}, {
            'openapi.boc.cn', 'elife.icbc.com.cn', 'ios.chat.openai.com'
        })
        self.assertEqual(coverage['mitm_missing_rewrite_script_coverage'][0]['host'],
                         'missing.example')
        necessity = audit_mitm_necessity([], coverage, rows, [])
        self.assertEqual(
            necessity['mitm_necessity_summary']['intentionally_skipped_pinning_references'],
            3
        )
        self.assertEqual(
            necessity['mitm_necessity_summary']['https_literal_missing'], 1
        )


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
            (r'^https?:\/\/gateway\.example\.com:8080\/app',
             ('gateway.example.com', 'literal_host')),
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

    def test_same_matcher_body_and_header_rewrites_are_classified_as_complementary(self):
        fixture = '''[Rewrite]
^https:\\/\\/api\\.example\\.com\\/home response-body-json-jq '.data.banners |= []'
^https:\\/\\/api\\.example\\.com\\/home response-header-del Content-MD5 ETag
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'complementary.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)

        self.assertEqual(report['summary']['rewrite_action_conflict_groups'], 1)
        self.assertEqual(report['summary']['rewrite_cross_layer_composable_groups'], 1)
        self.assertEqual(report['summary']['rewrite_cross_family_conflict_groups'], 0)
        group = report['rewrite_cross_layer_composable_groups'][0]
        self.assertEqual(
            group['classification'], 'complementary_response_body_and_header'
        )
        self.assertEqual(
            set(group['action_families']),
            {'header_rewrite', 'response_json_rewrite'}
        )

    def test_same_family_json_operations_are_reviewed_without_claiming_conflict(self):
        fixture = '''[Rewrite]
^https:\\/\\/api\\.example\\.com\\/feed response-body-json-jq '.data |= map(select(.type != "ad"))'
^https:\\/\\/api\\.example\\.com\\/feed response-body-json-del data.tracking
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ordered-json.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)

        self.assertEqual(report['summary']['rewrite_same_family_multi_operation_groups'], 1)
        self.assertEqual(report['summary']['rewrite_cross_family_conflict_groups'], 0)
        self.assertEqual(
            report['rewrite_same_family_multi_operation_groups'][0]['classification'],
            'same_layer_order_sensitive_review'
        )

    def test_block_action_variants_remain_conflict_candidates(self):
        fixture = '''[Rewrite]
^https:\\/\\/api\\.example\\.com\\/ad reject
^https:\\/\\/api\\.example\\.com\\/ad reject-dict
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'block-variants.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)

        self.assertEqual(report['summary']['rewrite_block_action_variant_groups'], 1)
        self.assertEqual(report['summary']['rewrite_cross_family_conflict_groups'], 0)
        self.assertEqual(
            report['rewrite_block_action_variant_groups'][0]['classification'],
            'blocking_action_variant_review'
        )


    def test_action_classifier_ignores_operator_names_inside_arguments(self):
        from deep_audit import classify_rewrite_action

        action = '''response-body-json-jq '.data |= map(select(
            .kind != "reject" and .header != "header-del"
        ))' '''
        self.assertEqual(
            classify_rewrite_action(action),
            {'families': ['response_json_rewrite'],
             'operations': ['response-body-json-jq']}
        )

    def test_action_classifier_splits_pipeline_outside_quoted_jq(self):
        from deep_audit import classify_rewrite_action

        action = '''response-body-json-jq '.data |= map(select(
            .kind == "reject" | .name == "header-del"
        ))' | response-header-del Content-MD5'''
        self.assertEqual(
            classify_rewrite_action(action),
            {'families': ['header_rewrite', 'response_json_rewrite'],
             'operations': ['response-body-json-jq', 'response-header-del']}
        )

    def test_action_classifier_preserves_unknown_leading_operator(self):
        from deep_audit import classify_rewrite_action

        self.assertEqual(
            classify_rewrite_action('future-action "reject header-del"'),
            {'families': ['unknown'], 'operations': ['future-action']}
        )



    def test_action_classifier_keeps_backtick_jq_pipeline_as_argument(self):
        from deep_audit import classify_rewrite_action

        action = 'response.json.jq(`if (.data | map(select(.kind == "reject"))) then .data else [] end`)'
        self.assertEqual(
            classify_rewrite_action(action),
            {'families': ['response_json_rewrite'],
             'operations': ['response.json.jq']}
        )



    def test_action_classifier_keeps_unknown_pipeline_stage_with_known_action(self):
        from deep_audit import classify_rewrite_action

        self.assertEqual(
            classify_rewrite_action('response-header-del Content-MD5 | future-action value'),
            {'families': ['header_rewrite', 'unknown'],
             'operations': ['future-action', 'response-header-del']}
        )

    def test_action_classifier_keeps_known_pipeline_stage_with_unknown_first_action(self):
        from deep_audit import classify_rewrite_action

        self.assertEqual(
            classify_rewrite_action('future-action value | reject'),
            {'families': ['block', 'unknown'],
             'operations': ['future-action', 'reject']}
        )


    def test_unknown_action_is_automated_warning_without_user_review(self):
        fixture = '''[Rewrite]
request if ${url} ~= /^https:\\/\\/api\\.example\\.com\\/ad$/ then future-action value
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'unknown-action.plugin'
            path.write_text(fixture, encoding='utf-8')
            report = audit_deep(path)

        self.assertEqual(report['summary']['rewrite_unknown_action_candidates'], 1)
        self.assertEqual(report['summary']['rewrite_action_semantic_review_candidates'], 1)
        candidate = report['rewrite_action_semantic_review_candidates'][0]
        self.assertEqual(candidate['action_families'], ['unknown'])
        self.assertEqual(candidate['review_priority'], 'automated_warning')
        self.assertIn('不要求用户人工处理', candidate['reasons'][0])

    def test_markdown_report_never_assigns_manual_review_to_user(self):
        from deep_audit import render_markdown
        report = {
            'summary': {
                'rewrite_entries': 1, 'rewrite_unparsed': 0,
                'rewrite_broad_candidates': 0, 'rewrite_duplicate_matcher_groups': 0,
                'rewrite_action_conflict_groups': 0, 'rewrite_exact_duplicate_action_groups': 0,
                'rewrite_block_action_variant_groups': 0, 'rewrite_same_family_multi_operation_groups': 0,
                'rewrite_cross_layer_composable_groups': 0, 'rewrite_cross_family_conflict_groups': 0,
                'rewrite_unclassified_multi_action_groups': 0, 'rewrite_action_semantic_review_candidates': 0,
                'rewrite_unknown_action_candidates': 0, 'rewrite_overlap_candidate_groups': 0,
                'rewrite_overlap_manual_review_candidates': 0, 'mitm_positive_unique_hosts': 0,
                'mitm_wildcards': 0, 'mitm_exact_hosts_covered_by_wildcards': 0,
                'mitm_wildcard_apex_not_explicit': 0, 'mitm_without_obvious_literal_guard': 0,
                'script_entries': 0, 'script_unique_remote_urls': 0, 'script_urls_reused': 0,
                'script_entries_without_detected_url': 0, 'script_generic_trigger_candidates': 0,
                'literal_references': 0, 'covered_references': 0, 'http_only_references': 0,
                'ip_literal_references': 0, 'dynamic_suffix_references': 0,
                'missing_rewrite_references': 0, 'missing_script_trigger_references': 0,
                'missing_mitm_references': 0, 'intentionally_skipped_references': 0,
                'negative_excluded_references': 0, 'ambiguous_references': 0,
                'ambiguous_rewrite_references': 0, 'ambiguous_script_trigger_references': 0,
                'unreferenced_positive_entries': 0, 'rewrite_scope_counts': {},
                'rewrite_action_family_counts': {}
            },
            'rewrite_broad_candidates': [], 'rewrite_action_conflict_groups': [],
            'rewrite_block_action_variant_groups': [], 'rewrite_same_family_multi_operation_groups': [],
            'rewrite_cross_layer_composable_groups': [], 'rewrite_cross_family_conflict_groups': [],
            'rewrite_unclassified_multi_action_groups': [], 'rewrite_action_semantic_review_candidates': [],
            'rewrite_unknown_action_candidates': [], 'rewrite_overlap_candidate_groups': [],
            'rewrite_overlap_manual_review_candidates': [], 'mitm_without_obvious_literal_guard': [],
            'script_repeated_remote_urls': [], 'script_generic_trigger_candidates': [],
            'mitm_missing_rewrite_script_coverage': [], 'mitm_intentionally_skipped_references': [],
            'mitm_negative_excluded_rewrite_script_coverage': [], 'mitm_http_only_no_mitm_references': [],
            'mitm_ip_literal_not_for_mitm_references': [], 'mitm_ambiguous_rewrite_script_references': [],
            'mitm_unreferenced_positive_candidates': [], 'rewrite_overlap_sampled_rules': 0,
            'rewrite_overlap_sampled_urls': 0, 'rewrite_overlap_skipped_rules': 0,
            'rewrite_scope_review_candidates': [], 'safety_notes': []
        }
        rendered = render_markdown(report)
        self.assertIn('不要求用户人工处理', rendered)
        self.assertIn('自动诊断警告', rendered)
        self.assertNotIn('人工复核', rendered)
        self.assertNotIn('复核候选', rendered)
        self.assertNotIn('review_priority', rendered)
        self.assertNotIn('high_review', rendered)


    def test_automated_diagnostics_json_is_additive_and_uses_canonical_names(self):
        from deep_audit import build_automated_diagnostics

        legacy_candidate = {
            'line': 4, 'review_priority': 'high_review',
            'classification': 'blocking_action_variant_review'
        }
        report = {
            'summary': {
                'rewrite_scope_review_candidates': 2,
                'rewrite_action_semantic_review_candidates': 1,
                'rewrite_overlap_manual_review_candidates': 3
            },
            'rewrite_scope_review_candidates': [{'line': 1, 'scope': 'global_like'}],
            'rewrite_action_semantic_review_candidates': [legacy_candidate],
            'rewrite_overlap_manual_review_candidates': [{'line': 9, 'reason': 'nested_quantifier'}],
            'rewrite_block_action_variant_groups': [legacy_candidate],
            'rewrite_same_family_multi_operation_groups': [],
            'rewrite_unclassified_multi_action_groups': []
        }

        diagnostics = build_automated_diagnostics(report)
        self.assertEqual(report['rewrite_action_semantic_review_candidates'][0], legacy_candidate)
        self.assertEqual(diagnostics['schema_version'], 1)
        self.assertEqual(diagnostics['handling'], {
            'mode': 'informational_only',
            'user_action_required': False,
            'automatic_rule_changes': False,
            'uncertain_rules': 'preserve_original'
        })
        self.assertEqual(diagnostics['summary']['rewrite_scope_diagnostics'], 2)
        self.assertEqual(diagnostics['summary']['rewrite_action_semantic_diagnostics'], 1)
        candidate = diagnostics['candidates']['rewrite_action_semantics'][0]
        self.assertEqual(candidate['diagnostic_priority'], 'high')
        self.assertEqual(candidate['classification'], 'blocking_action_variant_diagnostic')
        serialized = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn('review_priority', serialized)
        self.assertNotIn('high_review', serialized)
        self.assertNotIn('review_candidates', serialized)


    def test_automated_diagnostics_markdown_uses_the_same_handling_contract(self):
        from deep_audit import automated_diagnostics_handling, render_automated_diagnostics_handling

        handling = automated_diagnostics_handling()
        rendered = '\n'.join(render_automated_diagnostics_handling())
        self.assertEqual(handling, {
            'mode': 'informational_only',
            'user_action_required': False,
            'automatic_rule_changes': False,
            'uncertain_rules': 'preserve_original'
        })
        self.assertIn('`informational_only`', rendered)
        self.assertIn('是否要求用户操作：否', rendered)
        self.assertIn('是否允许自动修改规则：否', rendered)
        self.assertIn('`preserve_original`', rendered)
        self.assertIn('不生成用户待办', rendered)

if __name__ == '__main__':
    unittest.main()
