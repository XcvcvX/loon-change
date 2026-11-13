#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
import validate_plugin as vp


class ValidatorTests(unittest.TestCase):
    def test_hostnames(self):
        self.assertIsNone(vp.check_hostname('ads.example.com'))
        self.assertIsNone(vp.check_hostname('*.example.com'))
        self.assertIsNone(vp.check_hostname('*spclient.spotify.com'))
        self.assertIsNone(vp.check_hostname('api-?spclient.spotify.com'))
        self.assertIsNone(vp.check_hostname('-ads.example.com'))
        self.assertIsNotNone(vp.check_hostname('*.com'))
        self.assertIsNotNone(vp.check_hostname('*.co.uk'))
        self.assertIsNotNone(vp.check_hostname('*.net.cn'))
        self.assertIsNotNone(vp.check_hostname('*.com.cn'))
        self.assertIsNone(vp.check_hostname('*.example.com.cn'))
        self.assertIsNone(vp.check_hostname('*.chelaile.net.cn'))
        self.assertIsNone(vp.check_hostname('*.hoopchina.com.cn'))
        self.assertIsNotNone(vp.check_hostname('*.example.*'))
        self.assertIsNone(vp.check_hostname('pic*.chelaile.net.cn'))
        self.assertIsNone(vp.check_hostname('i*.hoopchina.com.cn'))
        self.assertIsNone(vp.check_hostname('api*.futunn.com'))
        self.assertIsNone(vp.check_hostname('cupid.51job*.com'))
        self.assertIsNone(vp.check_hostname('appapi.51job*.com'))
        self.assertIsNotNone(vp.check_hostname('51job*.com'))
        self.assertIsNotNone(vp.check_hostname('pic*.net.cn'))
        self.assertIsNotNone(vp.check_hostname('foo.*.com'))
        self.assertIsNone(vp.check_hostname('bad*host.example.com'))
        self.assertIsNotNone(vp.check_hostname('bad*host..example.com'))
        self.assertIsNotNone(vp.check_hostname('103.37.155.60'))
        self.assertIsNotNone(vp.check_hostname('2001:db8::1'))
        self.assertIsNotNone(vp.check_hostname('[2001:db8::1]'))

    def test_extract_script_url_supports_both_syntaxes(self):
        path_line = 'http-response ^https://a.example.com script-path=https://cdn.example.com/a.js,tag=A'
        spaced_path_line = 'http-response ^https://b.example.com script-path = https://cdn.example.com/spaced.js,tag=B'
        call_line = 'response then script("https://cdn.example.com/b.js", {enabled})'
        self.assertEqual(vp.extract_script_url(path_line), 'https://cdn.example.com/a.js')
        self.assertEqual(vp.extract_script_url(spaced_path_line), 'https://cdn.example.com/spaced.js')
        self.assertEqual(vp.extract_script_url(call_line), 'https://cdn.example.com/b.js')
        self.assertIsNone(vp.extract_script_url('response then reject(404)'))

    def test_script_section_rejects_rewrite_action(self):
        hosts = ','.join(sorted(vp.REQUIRED_COVERED_HOSTS))
        fixture = "\n".join([
            "[Argument]",
            "[Rule]",
            "[Rewrite]",
            "[Script]",
            "request if ${url} ~= /^https://ads\\.example\\.com/ then reject_dict(200)",
            "[MITM]",
            "hostname = " + hosts,
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'invalid.plugin'
            path.write_text(fixture, encoding='utf-8')
            errors, _, _ = vp.inspect_plugin(path)
        self.assertTrue(any('Rewrite Action 而不是 Script 调用' in error for error in errors))

    def test_wildcard_coverage(self):
        self.assertTrue(vp.host_covered('a.b.example.com', {'*.example.com'}))
        self.assertFalse(vp.host_covered('example.com', {'*.example.com'}))
        self.assertTrue(vp.host_covered('foo-spclient.spotify.com', {'*spclient.spotify.com'}))
        self.assertFalse(vp.host_covered('example.net', {'*.example.com'}))
        self.assertFalse(vp.host_covered('a.example.com', {'-*.example.com'}))

    def test_duplicate_section(self):
        sections, duplicates = vp.parse_sections('[Rule]\nDOMAIN,a.example.com,REJECT\n[Rule]\n')
        self.assertEqual(len(sections['Rule']), 1)
        self.assertEqual(duplicates, [(3, 'Rule')])

    def test_readme_update_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'README.md'
            path.write_text('当前产物统计由工作流自动维护：\n', encoding='utf-8')
            stats = {'Argument':1,'Rule':2,'Rewrite':3,'Script':4,'mitm_hostnames':5,'unique_script_urls':6}
            vp.update_readme(path, stats)
            first = path.read_text(encoding='utf-8')
            vp.update_readme(path, stats)
            self.assertEqual(first, path.read_text(encoding='utf-8'))
            self.assertIn('| [Rule] | 2 |', first)


if __name__ == '__main__':
    unittest.main()
